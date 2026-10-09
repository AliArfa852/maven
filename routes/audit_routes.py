"""Audit log viewing (src/audit.py). Read only: nobody can change the log here.

Admins, Managers, General Managers (admin.view) and Compliance Officers
(compliance.review) may read it. It holds who did what and when, never
message content.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from core.database import AuditEvent, SessionLocal
from core.middleware import require_capability
from src import access, audit

MAX_PAGE = 500


def _require_reader(request: Request) -> None:
    try:
        require_capability(request, access.ADMIN_VIEW)
    except HTTPException:
        require_capability(request, access.COMPLIANCE_REVIEW)


def setup_audit_routes() -> APIRouter:
    router = APIRouter(prefix="/api/audit", tags=["audit"])

    @router.get("/events")
    def list_events(request: Request, limit: int = 100, before_id: Optional[int] = None,
                    actor: Optional[str] = None, action: Optional[str] = None,
                    outcome: Optional[str] = None):
        _require_reader(request)
        limit = max(1, min(int(limit or 100), MAX_PAGE))
        db = SessionLocal()
        try:
            q = db.query(AuditEvent)
            if before_id:
                q = q.filter(AuditEvent.id < before_id)
            if actor:
                q = q.filter(AuditEvent.actor == actor.strip().lower())
            if action:
                q = q.filter(AuditEvent.action.startswith(action.strip()))
            if outcome:
                q = q.filter(AuditEvent.outcome == outcome.strip())
            rows = q.order_by(AuditEvent.id.desc()).limit(limit).all()
            return {"events": [audit.event_dict(e) for e in rows],
                    "next_before_id": rows[-1].id if len(rows) == limit else None}
        finally:
            db.close()

    @router.get("/verify")
    def verify(request: Request):
        _require_reader(request)
        return audit.verify_chain()

    return router
