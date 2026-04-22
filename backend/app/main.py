# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/main.py
===========
Entry point for the Paragon desktop application.

Key change in Sprint 2:
  - The full User object (with role eagerly loaded) is now passed
    to MainWindow instead of just the role string.
  - Role name and permissions are read BEFORE the DB session closes
    so there are no DetachedInstanceError crashes.
"""

import ttkbootstrap as tb
from app.ui.login_window import LoginWindow
from app.db.database import SessionLocal
from app.auth.login_service import authenticate_user
from sqlalchemy.orm import joinedload

ctk_mode = "dark"


class ParagonApp(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Paragon — Property Management")
        self.resizable(True, True)
        self._current_frame = None
        self.show_login()

    # ── Login ──────────────────────────────────────────────────────────────
    def show_login(self):
        if self._current_frame:
            self._current_frame.destroy()
        self._center(440, 500)
        self.title("Paragon — Login")
        self._current_frame = LoginWindow(self, on_login_success=self._handle_login)

    def _handle_login(self, username: str, password: str, login_frame: LoginWindow):
        db = SessionLocal()
        try:
            # Eagerly load role so we can access it after session closes
            user = (
                db.query(authenticate_user.__globals__["User"] if False else __import__(
                    "app.db.models", fromlist=["User"]
                ).User)
                .options(joinedload(__import__(
                    "app.db.models", fromlist=["User"]
                ).User.role))
                .filter_by(username=username)
                .first()
            )

            # Use the existing authenticate function for password check
            from app.auth.login_service import authenticate_user as auth
            from app.db.models import User
            user = (
                db.query(User)
                .options(joinedload(User.role))
                .filter(User.username == username)
                .first()
            )

            if user is None:
                login_frame.show_error("Invalid username or password")
                return

            from app.auth.security import verify_password
            if not verify_password(password, user.password_hash):
                login_frame.show_error("Invalid username or password")
                return

            if not user.is_active:
                login_frame.show_error("This account has been deactivated.")
                return

            # Read everything we need while session is still open
            role_value    = user.role.name.value if user.role else "unknown"
            permissions   = user.role.permissions or "" if user.role else ""
            city_id       = user.city_id
            city_name     = user.city.name if user.city else None
            user_id       = user.id
            full_name     = user.full_name
            # For tenant role — find linked tenant record via Tenant.user_id
            # If not linked, auto-link by matching email or full_name
            from app.db.models import Tenant as _Tenant
            tenant_id = None
            if role_value == "tenant":
                # First try direct user_id link
                t = db.query(_Tenant).filter(_Tenant.user_id == user.id).first()
                if not t and user.email:
                    # Auto-link by email
                    t = db.query(_Tenant).filter(_Tenant.email == user.email).first()
                if not t and user.full_name:
                    # Auto-link by full name as last resort
                    t = db.query(_Tenant).filter(_Tenant.full_name == user.full_name).first()
                if t:
                    # Save the link so we don't need to look up again next time
                    if not t.user_id:
                        t.user_id = user.id
                        db.commit()
                    tenant_id = t.id

            # Build a lightweight session-independent user context object
            user_ctx = _UserContext(
                id=user_id,
                username=username,
                full_name=full_name,
                role_value=role_value,
                permissions=permissions,
                city_id=city_id,
                city_name=city_name,
                tenant_id=tenant_id,
            )

            # Audit log — record successful login
            try:
                from app.services.audit_service import log_action, AuditAction
                log_action(db, action=AuditAction.LOGIN,
                           user_id=user_id, username=username,
                           detail=f"Login from role: {role_value}")
            except Exception:
                pass

        finally:
            db.close()

        login_frame.destroy()
        self._open_dashboard(user_ctx)

    # ── Dashboard ──────────────────────────────────────────────────────────
    def _open_dashboard(self, user_ctx: "_UserContext"):
        from app.ui.main_window import MainWindow
        self._center(1050, 680)
        self.title(f"Paragon — {user_ctx.role_value.replace('_', ' ').title()} Dashboard")
        self._current_frame = MainWindow(
            self,
            user=user_ctx,
            show_login_callback=self.show_login,
        )

    # ── Helpers ────────────────────────────────────────────────────────────
    def _center(self, w: int, h: int):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


class _UserContext:
    """
    Lightweight, session-independent snapshot of the logged-in user.
    Passed around the UI layer so nothing needs a live DB session
    just to check who is logged in or what they are allowed to do.
    """
    def __init__(self, *, id, username, full_name, role_value,
                 permissions, city_id, city_name, tenant_id=None):
        self.id        = id
        self.username  = username
        self.full_name = full_name
        self.role_value = role_value          # e.g. "location_admin"
        self.city_id   = city_id
        self.city_name = city_name            # e.g. "Bristol" or None (cross-city)
        self.tenant_id = tenant_id            # set for tenant role accounts

        # Build permission set once
        self._permission_cache = set(
            p.strip() for p in permissions.split(",") if p.strip()
        )

    def has_permission(self, key: str) -> bool:
        return key in self._permission_cache

    def __repr__(self):
        return f"<UserContext {self.username!r} role={self.role_value!r}>"


def main():
    app = ParagonApp()
    app.mainloop()


if __name__ == "__main__":
    main()