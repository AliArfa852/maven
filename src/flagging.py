"""Conversation flagging, rules v1 (plan v2 §6, requirement R19).

Checks each user message against simple, explainable rules and records a
ConversationFlag for Compliance Officers to review. Rules, not a model:
predictable, cheap, local, and easy to explain to an employee. A small local
classifier for abuse and misuse is planned for Phase 6.

Never blocks or alters the chat: scan_and_record() swallows its own errors.
Stores only a short excerpt around the match, with secrets masked.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from src.brand import maven_env

logger = logging.getLogger(__name__)

CATEGORIES = {
    "secret": "Credential or secret pasted into chat",
    "prompt_injection": "Attempt to override the assistant's instructions",
    "bulk_export": "Request to export sensitive data in bulk",
    "access_beyond_role": "Request for other people's data",
    "personal_data": "Large amount of personal data pasted",
    "keyword": "Company watch-list keyword",
}

EXCERPT_RADIUS = 80
MAX_SCAN_CHARS = 20_000  # long pastes: scan the start; flags are about intent


@dataclass(frozen=True)
class Finding:
    category: str
    rule: str
    severity: str
    start: int
    end: int


_I = re.IGNORECASE

# Secrets: the match itself is masked in the stored excerpt.
_SECRET_RULES = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("password_assignment", re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*\S{6,}", _I)),
]

_PATTERN_RULES = [
    ("prompt_injection", "ignore_instructions", "medium", re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+|your\s+)?"
        r"(?:previous|prior|above|earlier|system)\s+(?:instructions|rules|prompts?)", _I)),
    ("prompt_injection", "reveal_system_prompt", "medium", re.compile(
        r"\b(?:reveal|show|print|repeat)\s+(?:me\s+)?(?:your|the)\s+(?:system|hidden)\s+prompt", _I)),
    ("prompt_injection", "jailbreak_persona", "medium", re.compile(
        r"\b(?:developer|god|dan|jailbreak)\s+mode\b|\byou\s+are\s+now\s+DAN\b", _I)),
    ("bulk_export", "export_all_sensitive", "medium", re.compile(
        r"\b(?:export|dump|download|extract|send\s+me|list|give\s+me)\s+"
        r"(?:all|every|the\s+(?:entire|whole|full))\s+(?:of\s+the\s+)?"
        r"(?:customer|client|employee|staff|user|salary|salaries|payroll|password|contract|"
        r"financial|bank|credit\s+card|email|personal)\w*", _I)),
    ("access_beyond_role", "others_private_data", "medium", re.compile(
        r"\b(?:other|another|every(?:one)?'?s?|all)\s+(?:people|users|employees|colleagues|staff)'?s?\s+"
        r"(?:chats?|conversations?|messages?|emails?|salar(?:y|ies)|files|documents)", _I)),
    ("access_beyond_role", "salary_of_others", "medium", re.compile(
        r"\b(?:salary|salaries|pay|compensation)\s+(?:of|for)\s+(?:all|every(?:one)?|the\s+whole)\b", _I)),
]

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_PERSONAL_DATA_EMAILS = 10  # this many distinct addresses in one message


def _luhn_ok(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(nums)):
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _keywords() -> list[str]:
    raw = maven_env("MAVEN_AI_FLAG_KEYWORDS", "") or ""
    return [k.strip() for k in raw.split(",") if k.strip()]


def scan(text: str) -> list[Finding]:
    """All rule matches in ``text``, at most one per rule."""
    if not isinstance(text, str) or not text.strip():
        return []
    text = text[:MAX_SCAN_CHARS]
    found: list[Finding] = []
    for rule, rx in _SECRET_RULES:
        m = rx.search(text)
        if m:
            found.append(Finding("secret", rule, "high", m.start(), m.end()))
    for category, rule, severity, rx in _PATTERN_RULES:
        m = rx.search(text)
        if m:
            found.append(Finding(category, rule, severity, m.start(), m.end()))
    for m in _CARD.finditer(text):
        if _luhn_ok(m.group()):
            found.append(Finding("personal_data", "payment_card_number", "high", m.start(), m.end()))
            break
    emails = list(_EMAIL.finditer(text))
    if len({e.group().lower() for e in emails}) >= _PERSONAL_DATA_EMAILS:
        found.append(Finding("personal_data", "many_email_addresses", "medium",
                             emails[0].start(), emails[-1].end()))
    for word in _keywords():
        m = re.search(r"\b" + re.escape(word) + r"\b", text, _I)
        if m:
            found.append(Finding("keyword", f"keyword:{word.lower()}", "low", m.start(), m.end()))
    return found


def _mask(fragment: str) -> str:
    """Mask everything that looks secret or personal in a stored excerpt."""
    for _, rx in _SECRET_RULES:
        fragment = rx.sub(lambda m: m.group()[:4] + "…[masked]", fragment)
    fragment = _CARD.sub(lambda m: "[card masked]" if _luhn_ok(m.group()) else m.group(), fragment)
    return _EMAIL.sub(lambda m: m.group()[0] + "…@" + m.group().split("@", 1)[1], fragment)


def excerpt(text: str, finding: Finding) -> str:
    start = max(0, finding.start - EXCERPT_RADIUS)
    end = min(len(text), min(finding.end, finding.start + 200) + EXCERPT_RADIUS)
    snippet = text[start:end].replace("\n", " ")
    return ("…" if start else "") + _mask(snippet) + ("…" if end < len(text) else "")


DEFAULT_MONITORING_NOTICE = (
    "Messages you send may be checked automatically for security and policy "
    "risks, such as pasted passwords or requests for other people's data. "
    "Matches are reviewed by your organisation's compliance team."
)


def monitoring_notice() -> str:
    """Notice shown to employees when flagging is on ("" when it is off).

    Telling people their use is monitored is a legal requirement in many
    places. Companies can word it themselves with MAVEN_AI_MONITORING_NOTICE.
    """
    if not flagging_enabled():
        return ""
    return (maven_env("MAVEN_AI_MONITORING_NOTICE", "") or "").strip() or DEFAULT_MONITORING_NOTICE


def flagging_enabled() -> bool:
    return (maven_env("MAVEN_AI_FLAGGING", "1") or "1").strip().lower() not in {"0", "false", "no", "off"}


def scan_and_record(session_id: str, message_id: str | None, owner: str | None, text: str) -> int:
    """Scan one user message and store a flag per finding. Returns the count.

    Never raises: flagging must not break or slow down chat on failure.
    """
    try:
        if not flagging_enabled():
            return 0
        findings = scan(text)
        if not findings:
            return 0
        from core.database import ConversationFlag, SessionLocal
        db = SessionLocal()
        try:
            for f in findings:
                db.add(ConversationFlag(
                    id=str(uuid.uuid4()), session_id=session_id, message_id=message_id,
                    owner=owner, category=f.category, rule=f.rule, severity=f.severity,
                    excerpt=excerpt(text[:MAX_SCAN_CHARS], f), status="open",
                ))
            db.commit()
        finally:
            db.close()
        logger.info("Flagged message in session %s: %s", session_id,
                    ", ".join(sorted({f.rule for f in findings})))
        return len(findings)
    except Exception:
        logger.exception("Conversation flagging failed; the message itself was saved")
        return 0
