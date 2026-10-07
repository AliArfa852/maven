"""Role, clearance and capability model (plan v2 §3, decisions D-2-2, D-2-8).

A user holds one or more roles. Their capabilities are the union of their
roles' capabilities; their clearance is an admin-set override, or else the
highest default clearance among their roles.

The Admin role is not stored here: ``is_admin`` on the auth record stays the
single source of truth so every existing ``require_admin`` gate keeps its
meaning. ``effective_roles`` folds it in.

Pure functions only; no I/O. core/auth.py stores roles and clearance.
"""
from __future__ import annotations

from typing import Iterable, Optional

BASIC = "basic"
ADVANCED = "advanced"
MANAGER = "manager"
GENERAL_MANAGER = "general_manager"
COMPLIANCE_OFFICER = "compliance_officer"
ADMIN = "admin"

# Display order, lowest to highest authority.
ROLES = (BASIC, ADVANCED, MANAGER, GENERAL_MANAGER, COMPLIANCE_OFFICER, ADMIN)

ROLE_LABELS = {
    BASIC: "Basic",
    ADVANCED: "Advanced",
    MANAGER: "Manager",
    GENERAL_MANAGER: "General Manager",
    COMPLIANCE_OFFICER: "Compliance Officer",
    ADMIN: "Admin",
}

# Clearance levels, lowest to highest.
CLEARANCES = ("public", "internal", "confidential", "restricted")

# Default clearance per role (D-2-2). Admin gets Internal on purpose: running
# the system does not grant reading everyone's sensitive data.
ROLE_DEFAULT_CLEARANCE = {
    BASIC: "internal",
    ADVANCED: "internal",
    MANAGER: "confidential",
    GENERAL_MANAGER: "restricted",
    COMPLIANCE_OFFICER: "restricted",
    ADMIN: "internal",
}

# Admin console capabilities, enforced by core.middleware.require_capability.
ADMIN_VIEW = "admin.view"          # open the admin console, read-only
ADMIN_MANAGE = "admin.manage"      # change users, roles, clearance, settings
COMPLIANCE_REVIEW = "compliance.review"  # work the flagged-conversation queue

ROLE_CAPABILITIES = {
    BASIC: frozenset(),
    ADVANCED: frozenset(),
    MANAGER: frozenset({ADMIN_VIEW}),
    GENERAL_MANAGER: frozenset({ADMIN_VIEW}),
    COMPLIANCE_OFFICER: frozenset({ADMIN_VIEW, COMPLIANCE_REVIEW}),
    # Separation of duties: Admin does not review flagged conversations.
    ADMIN: frozenset({ADMIN_VIEW, ADMIN_MANAGE}),
}


def normalize_roles(roles: Optional[Iterable[str]]) -> list[str]:
    """Known roles only, de-duplicated, in ROLES order. Unknown names are dropped."""
    wanted = {str(r or "").strip().lower() for r in (roles or [])}
    return [r for r in ROLES if r in wanted]


def invalid_roles(roles: Optional[Iterable[str]]) -> list[str]:
    """Names in ``roles`` that are not known roles."""
    return sorted({str(r or "").strip().lower() for r in (roles or [])} - set(ROLES))


def effective_roles(stored_roles: Optional[Iterable[str]], is_admin: bool) -> list[str]:
    """Stored roles plus Admin when ``is_admin``; everyone holds at least Basic."""
    roles = set(normalize_roles(stored_roles))
    roles.discard(ADMIN)  # only is_admin grants Admin
    if is_admin:
        roles.add(ADMIN)
    roles.add(BASIC)
    return [r for r in ROLES if r in roles]


def capabilities_for(roles: Iterable[str]) -> list[str]:
    caps: set[str] = set()
    for role in normalize_roles(roles):
        caps |= ROLE_CAPABILITIES[role]
    return sorted(caps)


def is_valid_clearance(value: Optional[str]) -> bool:
    return value in CLEARANCES


def default_clearance(roles: Iterable[str]) -> str:
    """Highest default clearance among ``roles`` (Basic's when none)."""
    levels = [CLEARANCES.index(ROLE_DEFAULT_CLEARANCE[r]) for r in normalize_roles(roles)]
    return CLEARANCES[max(levels)] if levels else ROLE_DEFAULT_CLEARANCE[BASIC]


def effective_clearance(roles: Iterable[str], override: Optional[str]) -> str:
    """The admin-set override when valid, else the roles' default."""
    return override if is_valid_clearance(override) else default_clearance(roles)


def clearance_allows(user_clearance: str, label: str) -> bool:
    """True when a user at ``user_clearance`` may see data labelled ``label``.

    Unknown values fail closed.
    """
    if not is_valid_clearance(user_clearance) or not is_valid_clearance(label):
        return False
    return CLEARANCES.index(user_clearance) >= CLEARANCES.index(label)
