# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/main_window.py
=====================
Main dashboard shell.

Sprint 2 changes:
  - Accepts a UserContext object instead of a raw role string.
  - Sidebar is built dynamically from SIDEBAR_MODULES using
    user.has_permission() — no more hardcoded role checks.
  - City and username shown in the sidebar header.
  - Pages are only instantiated if the user can see them,
    keeping startup fast.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from app.auth.permissions import SIDEBAR_MODULES


class MainWindow(tb.Frame):
    """Main dashboard window."""

    SIDEBAR_W = 220

    def __init__(self, parent, user, show_login_callback):
        super().__init__(parent)
        self.user = user                          # _UserContext
        self.show_login_callback = show_login_callback
        self.pack(fill=BOTH, expand=YES)

        self._pages: dict[str, tb.Frame] = {}
        self._nav_buttons: dict[str, tb.Button] = {}

        self._build_sidebar()
        self._build_content()
        self._build_pages()

        # Tenants go straight to their dashboard, staff go to home
        if self.user.role_value == "tenant":
            self._show_page("dashboard")
        else:
            self._show_page("home")

        # Session timeout — auto-logout after 30 min inactivity
        from app.ui.session_manager import SessionManager
        self._session = SessionManager(self, timeout_minutes=30,
                                       on_timeout=self._logout)

    # ── Sidebar ───────────────────────────────────────────────────────────
    def _build_sidebar(self):
        self.sidebar = tb.Frame(self, bootstyle="dark", width=self.SIDEBAR_W)
        self.sidebar.pack(side=LEFT, fill=Y)
        self.sidebar.pack_propagate(False)

        # Brand
        brand = tb.Frame(self.sidebar, bootstyle="dark", padding=(16, 20, 16, 10))
        brand.pack(fill=X)
        tb.Label(brand, text="PARAGON",
                 font=("Georgia", 18, "bold"), bootstyle="inverse-dark").pack(anchor=W)
        tb.Label(brand, text="Property Management",
                 font=("Helvetica", 9), bootstyle="secondary").pack(anchor=W)

        tb.Separator(self.sidebar, orient=HORIZONTAL).pack(fill=X, pady=(0, 6))

        # User info pill
        info = tb.Frame(self.sidebar, bootstyle="dark", padding=(16, 4, 16, 10))
        info.pack(fill=X)
        tb.Label(info, text=self.user.full_name,
                 font=("Helvetica", 10, "bold"), bootstyle="inverse-dark").pack(anchor=W)

        role_display = self.user.role_value.replace("_", " ").title()
        city_display = f"  {self.user.city_name}" if self.user.city_name else "  All Cities"
        tb.Label(info, text=f"{role_display}  |{city_display}",
                 font=("Helvetica", 8), bootstyle="secondary").pack(anchor=W)

        tb.Separator(self.sidebar, orient=HORIZONTAL).pack(fill=X, pady=(0, 8))

        # Nav — only show modules this user has permission to see
        for label, key, required_permission in SIDEBAR_MODULES:
            # None = always visible (Home, Settings)
            if required_permission and not self.user.has_permission(required_permission):
                continue

            btn = tb.Button(
                self.sidebar, text=label,
                bootstyle="secondary-outline",
                width=24, padding=(10, 7),
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill=X, padx=10, pady=2)
            self._nav_buttons[key] = btn

        # Logout — pinned to bottom
        tb.Separator(self.sidebar, orient=HORIZONTAL).pack(side=BOTTOM, fill=X)
        tb.Button(
            self.sidebar, text="⬅   Logout",
            bootstyle="danger-outline",
            width=24, padding=(10, 7),
            command=self._logout,
        ).pack(side=BOTTOM, fill=X, padx=10, pady=10)

    # ── Content area ──────────────────────────────────────────────────────
    def _build_content(self):
        self.content = tb.Frame(self, bootstyle="default")
        self.content.pack(side=RIGHT, fill=BOTH, expand=YES)

    # ── Pages ─────────────────────────────────────────────────────────────
    def _build_pages(self):
        # Home — built for staff only, tenants use Dashboard
        if self.user.role_value != "tenant":
            from app.ui.home_page import HomePage
            self._pages["home"] = HomePage(self.content, user=self.user)

        # Settings — always built
        self._pages["settings"] = self._make_settings()

        # Users — permission gated
        if self.user.has_permission("user.view"):
            from app.ui.users_page import UsersPage
            self._pages["users"] = UsersPage(self.content, user=self.user)

        # Tenants — Sprint 3
        if self.user.has_permission("tenant.view"):
            from app.ui.tenants_page import TenantsPage
            self._pages["tenants"] = TenantsPage(self.content, user=self.user)

        # Apartments — Sprint 3
        if self.user.has_permission("apartment.view"):
            from app.ui.apartments_page import ApartmentsPage
            self._pages["apartments"] = ApartmentsPage(self.content, user=self.user)

        # Finance — Sprint 4
        if self.user.has_permission("invoice.view"):
            from app.ui.finance_page import FinancePage
            self._pages["finance"] = FinancePage(self.content, user=self.user)

        # Maintenance — Sprint 5
        if self.user.has_permission("maintenance.view"):
            from app.ui.maintenance_page import MaintenancePage
            self._pages["maintenance"] = MaintenancePage(self.content, user=self.user)

        # Complaints — Sprint 5
        if self.user.has_permission("complaint.view"):
            from app.ui.complaints_page import ComplaintsPage
            self._pages["complaints"] = ComplaintsPage(self.content, user=self.user)

        # Reports — Sprint 6
        if self.user.has_permission("report.local") or self.user.has_permission("report.crosscity") or self.user.has_permission("report.finance"):
            from app.ui.reports_page import ReportsPage
            self._pages["reports"] = ReportsPage(self.content, user=self.user)

        # Tenant dashboard — Sprint 6
        if self.user.has_permission("dashboard.view"):
            from app.ui.tenant_dashboard import TenantDashboard
            self._pages["dashboard"] = TenantDashboard(self.content, user=self.user)

        # Audit log — Sprint 7
        if self.user.has_permission("audit_log.view"):
            self._pages["audit_log"] = self._make_audit_log_page()



    def _make_home(self) -> tb.Frame:
        page = tb.Frame(self.content)
        inner = tb.Frame(page)
        inner.place(relx=0.5, rely=0.44, anchor="center")

        role_display = self.user.role_value.replace("_", " ").title()
        tb.Label(inner, text=f"Welcome, {self.user.full_name}!",
                 font=("Georgia", 26, "bold")).pack()
        tb.Label(inner, text=role_display,
                 font=("Helvetica", 13), bootstyle="primary").pack(pady=(4, 0))
        if self.user.city_name:
            tb.Label(inner, text=f"📍 {self.user.city_name}",
                     font=("Helvetica", 11), bootstyle="secondary").pack(pady=(2, 0))
        tb.Label(inner, text="Select a module from the sidebar to get started.",
                 font=("Helvetica", 11), bootstyle="secondary").pack(pady=(16, 0))
        return page

    def _make_audit_log_page(self) -> tb.Frame:
        """Audit log viewer — only for roles with audit_log.view."""
        page = tb.Frame(self.content, padding=(24, 20))

        tb.Label(page, text="Audit Log",
                 font=("Georgia", 20, "bold")).pack(anchor=W, pady=(0, 16))

        filter_bar = tb.Frame(page)
        filter_bar.pack(fill=X, pady=(0, 10))

        tb.Label(filter_bar, text="Filter:", font=("Helvetica", 11)).pack(side=LEFT)
        filter_var = tb.StringVar(value="All")
        tb.Combobox(filter_bar, textvariable=filter_var,
                    values=["All", "auth.login", "lease.create", "lease.terminate",
                            "payment.record", "invoice.void", "tenant.register",
                            "ticket.create", "complaint.create"],
                    state="readonly", font=("Helvetica", 11), width=20).pack(side=LEFT, padx=6)

        cols = ("time", "user", "action", "entity", "detail")
        tree = tb.Treeview(page, columns=cols, show="headings",
                           bootstyle="dark", selectmode="browse")
        col_cfg = [
            ("time",   "Time",    140, CENTER),
            ("user",   "User",    120, W),
            ("action", "Action",  150, W),
            ("entity", "Entity",  100, CENTER),
            ("detail", "Detail",  320, W),
        ]
        for cid, heading, width, anchor in col_cfg:
            tree.heading(cid, text=heading, anchor=anchor)
            tree.column(cid, width=width, anchor=anchor)

        sb = tb.Scrollbar(page, orient=VERTICAL, command=tree.yview, bootstyle="round-dark")
        tree.configure(yscrollcommand=sb.set)

        def load_logs(*_):
            for row in tree.get_children():
                tree.delete(row)
            from app.db.database import SessionLocal
            from app.services.audit_service import get_audit_logs
            db = SessionLocal()
            try:
                action_filter = filter_var.get()
                logs = get_audit_logs(db,
                    action=action_filter if action_filter != "All" else None,
                    limit=300)
                for log in logs:
                    dt = log["created_at"]
                    time_str = dt.strftime("%d %b %Y %H:%M") if dt else "—"
                    tree.insert("", END, values=(
                        time_str,
                        log["username"],
                        log["action"],
                        log["entity"],
                        log["detail"],
                    ))
            finally:
                db.close()

        filter_var.trace_add("write", load_logs)

        btn_bar = tb.Frame(page)
        btn_bar.pack(fill=X, pady=(0, 6))
        tb.Button(btn_bar, text="↻  Refresh", bootstyle="secondary",
                  padding=(8, 4), command=load_logs).pack(side=LEFT)

        tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        load_logs()
        return page

    def _make_settings(self) -> tb.Frame:
        page = tb.Frame(self.content, padding=(24, 20))

        tb.Label(page, text="Settings",
                 font=("Georgia", 20, "bold")).pack(anchor=W, pady=(0, 4))
        tb.Label(page, text=f"Logged in as {self.user.full_name or self.user.username}  —  "
                            f"{self.user.role_value.replace('_',' ').title()}"
                            f"{'  —  ' + self.user.city_name if self.user.city_name else ''}",
                 font=("Helvetica", 11), bootstyle="secondary").pack(anchor=W, pady=(0, 20))

        tb.Separator(page, orient=HORIZONTAL).pack(fill=X, pady=(0, 20))

        # Change password section
        tb.Label(page, text="Change Password",
                 font=("Georgia", 14, "bold")).pack(anchor=W, pady=(0, 10))

        pw_frame = tb.Frame(page)
        pw_frame.pack(anchor=W)

        def lbl(p, t):
            tb.Label(p, text=t, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        lbl(pw_frame, "New Password")
        v_new_pw = tb.Entry(pw_frame, font=("Helvetica", 12), show="•", width=28)
        v_new_pw.pack(pady=(2, 8))

        lbl(pw_frame, "Confirm Password")
        v_confirm_pw = tb.Entry(pw_frame, font=("Helvetica", 12), show="•", width=28)
        v_confirm_pw.pack(pady=(2, 8))

        def change_password():
            from ttkbootstrap.dialogs import Messagebox
            new_pw  = v_new_pw.get()
            conf_pw = v_confirm_pw.get()
            if not new_pw:
                Messagebox.show_warning("Please enter a new password.", title="Validation")
                return
            if new_pw != conf_pw:
                Messagebox.show_warning("Passwords do not match.", title="Validation")
                return
            if len(new_pw) < 6:
                Messagebox.show_warning("Password must be at least 6 characters.", title="Validation")
                return
            from app.db.database import SessionLocal
            from app.db.models import User
            from app.auth.security import hash_password
            db = SessionLocal()
            try:
                u = db.query(User).filter(User.id == self.user.id).first()
                if u:
                    u.password_hash = hash_password(new_pw)
                    db.commit()
                    v_new_pw.delete(0, END)
                    v_confirm_pw.delete(0, END)
                    Messagebox.show_info("Password changed successfully.", title="Done")
            finally:
                db.close()

        tb.Button(pw_frame, text="Update Password", bootstyle="success",
                  padding=(10, 5), command=change_password).pack(anchor=W)

        # Manager-only: City Management
        if self.user.role_value == "manager":
            tb.Separator(page, orient=HORIZONTAL).pack(fill=X, pady=(24, 20))
            tb.Label(page, text="Business Expansion",
                     font=("Georgia", 14, "bold")).pack(anchor=W, pady=(0, 6))
            tb.Label(page, text="Add new cities to expand Paragon's operations.",
                     font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(0, 10))
            tb.Button(page, text="🏙  Manage Cities",
                      bootstyle="info", padding=(12, 6),
                      command=lambda: self._open_city_management()).pack(anchor=W)

        return page

    def _open_city_management(self):
        from app.ui.city_management_page import CityManagementPage
        dlg = CityManagementPage(self, user=self.user)
        self.wait_window(dlg)

    def _make_placeholder(self, title: str, sprint: str) -> tb.Frame:
        """Temporary placeholder for modules not yet built."""
        page = tb.Frame(self.content)
        inner = tb.Frame(page)
        inner.place(relx=0.5, rely=0.46, anchor="center")
        tb.Label(inner, text=title,
                 font=("Georgia", 24, "bold")).pack()
        tb.Label(inner, text=f"Coming in {sprint}",
                 font=("Helvetica", 12), bootstyle="secondary").pack(pady=(8, 0))
        return page

    # ── Navigation ────────────────────────────────────────────────────────
    _LOAD_METHODS = {
        "home":        "load_dashboard",
        "dashboard":   "load_dashboard",
        "reports":     "load_reports",
        "tenants":     "load_tenants",
        "apartments":  "load_apartments",
        "users":       "load_users",
        "finance":     "load_invoices",
        "maintenance": "load_tickets",
        "complaints":  "load_complaints",
    }

    def _show_page(self, name: str):
        for page in self._pages.values():
            page.pack_forget()

        for key, btn in self._nav_buttons.items():
            if key == name:
                btn.configure(bootstyle="primary")
            else:
                btn.configure(bootstyle="secondary-outline")

        if name in self._pages:
            page = self._pages[name]
            page.pack(fill=BOTH, expand=YES)
            load_fn = self._LOAD_METHODS.get(name)
            if load_fn and hasattr(page, load_fn):
                try:
                    getattr(page, load_fn)()
                except Exception:
                    pass

    # ── Logout ────────────────────────────────────────────────────────────
    def _logout(self):
        self.destroy()
        self.show_login_callback()