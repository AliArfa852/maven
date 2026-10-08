"""Audit log v1 (plan v2 §3, Phase 2: "everything is auditable").

record() appends one AuditEvent. Rows form a hash chain: each row's hash
covers its own fields plus the previous row's hash, so changing or deleting
an earlier row is detected by verify_chain(). Deleting the newest rows is
not detectable from the chain alone; note the head hash (shown in the Admin
Console) somewhere outside Maven if that matters to you.

What is recorded: who, what, when, from where, and whether it worked. Never
request bodies, passwords or message content.

record() never raises: auditing must not break the action it describes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_PG_LOCK_KEY = 0x6D6176656E  # "maven"; serialises writers across processes on PostgreSQL

# Mutating requests under these paths are recorded by AuditMiddleware.
AUDITED_PREFIXES = (
    "/api/auth/",          # users, roles, clearance, passwords, 2FA, settings
    "/api/compliance/",    # flag decisions and flagging rules
    "/api/admin",          # wipe and other admin actions
    "/api/vault",
    "/api/tokens",
    "/api/webhooks",
    "/api/model-endpoints",
    "/api/mcp",
    "/api/import",
)
# Reads that matter on their own (bulk data leaving the system).
AUDITED_READS = ("/api/export",)
# Recorded explicitly by the route with more detail.
_SKIP = ("/api/auth/login",)
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def should_audit(method: str, path: str) -> bool:
    if path.startswith(_SKIP):
        return False
    if method in MUTATING and path.startswith(AUDITED_PREFIXES):
        return True
    return method == "GET" and path.startswith(AUDITED_READS)


def _digest(prev: str, at: datetime, actor, action, target, outcome, ip, detail) -> str:
    payload = json.dumps(
        [prev, at.isoformat(timespec="microseconds"), actor, action, target, outcome, ip, detail],
        separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clip(value: Any, n: int = 300) -> str | None:
    if value is None:
        return None
    return str(value)[:n]


def record(action: str, *, actor: str | None = None, target: str | None = None,
           outcome: str = "ok", ip: str | None = None, detail: dict | None = None) -> bool:
    """Append one event. Returns False (and logs) if it could not be stored."""
    try:
        from sqlalchemy import text

        from core.database import AuditEvent, SessionLocal

        detail_json = json.dumps(detail, separators=(",", ":"), default=str)[:2000] if detail else None
        actor, target, ip = _clip(actor, 120), _clip(target), _clip(ip, 64)
        action, outcome = _clip(action, 80), _clip(outcome, 20)
        with _lock:
            db = SessionLocal()
            try:
                if db.get_bind().dialect.name == "postgresql":
                    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _PG_LOCK_KEY})
                last = db.query(AuditEvent.hash).order_by(AuditEvent.id.desc()).first()
                prev = last[0] if last else ""
                at = datetime.utcnow()
                db.add(AuditEvent(at=at, actor=actor, action=action, target=target, outcome=outcome,
                                  ip=ip, detail=detail_json, prev_hash=prev,
                                  hash=_digest(prev, at, actor, action, target, outcome, ip, detail_json)))
                db.commit()
            finally:
                db.close()
        return True
    except Exception:
        logger.exception("Could not write audit event %s", action)
        return False


def verify_chain(batch: int = 1000) -> dict:
    """Walk the whole log. ok=False names the first row that does not fit."""
    from core.database import AuditEvent, SessionLocal

    db = SessionLocal()
    try:
        prev, count, last_id = "", 0, 0
        while True:
            rows = (db.query(AuditEvent).filter(AuditEvent.id > last_id)
                    .order_by(AuditEvent.id).limit(batch).all())
            if not rows:
                return {"ok": True, "count": count, "head": prev or None}
            for r in rows:
                expected = _digest(prev, r.at, r.actor, r.action, r.target, r.outcome, r.ip, r.detail)
                if r.prev_hash != prev or r.hash != expected:
                    return {"ok": False, "count": count, "first_bad_id": r.id,
                            "reason": "link broken (a row before it was removed or changed)"
                            if r.prev_hash != prev else "row changed after it was written"}
                prev, count, last_id = r.hash, count + 1, r.id
    finally:
        db.close()


def client_ip(request) -> str | None:
    client = getattr(request, "client", None)
    return getattr(client, "host", None)


def event_dict(e) -> dict:
    try:
        detail = json.loads(e.detail) if e.detail else None
    except ValueError:
        detail = e.detail
    return {"id": e.id, "at": e.at.isoformat() + "Z" if e.at else None, "actor": e.actor,
            "action": e.action, "target": e.target, "outcome": e.outcome, "ip": e.ip,
            "detail": detail}
