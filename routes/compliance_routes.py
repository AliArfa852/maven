"""Flagged-conversation review for Compliance Officers (plan v2 §6, R19).

Only users whose roles grant ``compliance.review`` may list or decide flags.
Admins and Managers do not have it (separation of duties, D-2-2). Reviewers
see the masked excerpt stored with each flag, not the whole conversation.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.database import ConversationFlag, SessionLocal
from core.middleware import require_capability
from src import access
from src.auth_helpers import get_current_user
from src import flagging
from src.flagging import CATEGORIES, retention_days

STATUSES = ("open", "dismissed", "warned", "escalated")
DECISIONS = {"dismiss": "dismissed", "warn": "warned", "escalate": "escalated"}
MAX_PAGE = 200


class FlagSettings(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    disabled_rules: list[str] = Field(default_factory=list)


class FlagDecision(BaseModel):
    decision: str = Field(..., description="dismiss, warn or escalate")
    note: Optional[str] = Field(default="", max_length=2000)


def _flag_dict(f: ConversationFlag) -> dict:
    return {
        "id": f.id,
        "session_id": f.session_id,
        "owner": f.owner,
        "category": f.category,
        "category_label": CATEGORIES.get(f.category, f.category),
        "rule": f.rule,
        "severity": f.severity,
        "excerpt": f.excerpt,
        "status": f.status,
        "created_at": f.created_at.isoformat() + "Z" if f.created_at else None,
        "reviewed_by": f.reviewed_by,
        "reviewed_at": f.reviewed_at.isoformat() + "Z" if f.reviewed_at else None,
        "review_note": f.review_note,
    }


def setup_compliance_routes() -> APIRouter:
    router = APIRouter(prefix="/api/compliance", tags=["compliance"])

    @router.get("/flags")
    def list_flags(request: Request, status: str = "open", limit: int = 100):
        require_capability(request, access.COMPLIANCE_REVIEW)
        if status not in STATUSES and status != "all":
            raise HTTPException(400, f"status must be one of: all, {', '.join(STATUSES)}")
        limit = max(1, min(int(limit or 100), MAX_PAGE))
        db = SessionLocal()
        try:
            q = db.query(ConversationFlag)
            if status != "all":
                q = q.filter(ConversationFlag.status == status)
            rows = q.order_by(ConversationFlag.created_at.desc()).limit(limit).all()
            counts = {s: db.query(ConversationFlag).filter(ConversationFlag.status == s).count()
                      for s in STATUSES}
            return {"flags": [_flag_dict(f) for f in rows], "counts": counts,
                    "retention_days": retention_days()}
        finally:
            db.close()

    @router.post("/flags/{flag_id}/decision")
    def decide_flag(flag_id: str, body: FlagDecision, request: Request):
        require_capability(request, access.COMPLIANCE_REVIEW)
        status = DECISIONS.get((body.decision or "").strip().lower())
        if not status:
            raise HTTPException(400, "decision must be dismiss, warn or escalate")
        db = SessionLocal()
        try:
            flag = db.query(ConversationFlag).filter(ConversationFlag.id == flag_id).first()
            if flag is None:
                raise HTTPException(404, "Flag not found")
            flag.status = status
            flag.reviewed_by = get_current_user(request)
            flag.reviewed_at = datetime.utcnow()
            flag.review_note = (body.note or "").strip() or None
            db.commit()
            return {"ok": True, "flag": _flag_dict(flag)}
        finally:
            db.close()

    def _settings_view() -> dict:
        saved = flagging.load_settings()
        return {
            "keywords": saved["keywords"],
            "env_keywords": flagging.env_keywords(),
            "disabled_rules": saved["disabled_rules"],
            "rules": flagging.rule_catalogue(),
            "updated_by": saved.get("updated_by"),
            "updated_at": saved.get("updated_at"),
            "flagging_enabled": flagging.flagging_enabled(),
            "max_keywords": flagging.MAX_KEYWORDS,
        }

    @router.get("/settings")
    def get_settings(request: Request):
        require_capability(request, access.COMPLIANCE_REVIEW)
        return _settings_view()

    @router.put("/settings")
    def put_settings(body: FlagSettings, request: Request):
        require_capability(request, access.COMPLIANCE_REVIEW)
        try:
            flagging.save_settings(body.keywords, body.disabled_rules, get_current_user(request))
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return _settings_view()

    return router
