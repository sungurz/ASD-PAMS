# Ahmet (24034408) 
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import User


def has_permission(user: "User", permission: str) -> bool:
    """
    Return True if the logged-in user has the given permission key.

    Permissions are stored as a comma-separated string on the Role
    row, e.g. "tenant.create,tenant.view,lease.create".

    The parsed set is cached on _permission_cache so it is only
    computed once per login session.
    """
    if user is None:
        return False

    # Use cached set if already computed
    if not hasattr(user, "_permission_cache"):
        raw = ""
        if user.role and user.role.permissions:
            raw = user.role.permissions
        user._permission_cache = set(p.strip() for p in raw.split(",") if p.strip())

    return permission in user._permission_cache


def get_permissions(user: "User") -> set[str]:
    """Return the full set of permission keys for this user."""
    if not hasattr(user, "_permission_cache"):
        has_permission(user, "__init__")   # trigger cache build
    return user._permission_cache


# ── Sidebar module definitions ───────────────────────────────────────────────
# Each entry: (label, page_key, required_permission)
# main_window.py iterates this list and only adds buttons the user can see.

SIDEBAR_MODULES = [
    ("🏠   Home",         "home",        None),               # always visible (hidden for tenants in main_window)
    ("👥   Users",        "users",       "user.view"),
    ("🏢   Tenants",      "tenants",     "tenant.view"),
    ("🏠   Apartments",   "apartments",  "apartment.view"),
    ("💷   Finance",      "finance",     "invoice.view"),
    ("🔧   Maintenance",  "maintenance", "maintenance.view"),
    ("📋   Complaints",   "complaints",  "complaint.view"),
    ("📊   Reports",      "reports",     "report.local"),
    ("🖥   My Dashboard", "dashboard",   "dashboard.view"),
    ("📋   Audit Log",    "audit_log",   "audit_log.view"),
    ("⚙️   Settings",     "settings",    None),               # always visible
]