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

        # Show home by default
        self._show_page("home")

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
        # Home — always built
        self._pages["home"] = self._make_home()

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

        # Reports — permission gated (Sprint 6)
        if self.user.has_permission("report.local"):
            self._pages["reports"] = self._make_placeholder("Reports", "Sprint 6")

        # Tenant dashboard — permission gated (Sprint 6)
        if self.user.has_permission("dashboard.view"):
            self._pages["dashboard"] = self._make_placeholder("My Dashboard", "Sprint 6")

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

    def _make_settings(self) -> tb.Frame:
        page = tb.Frame(self.content)
        tb.Label(page, text="Settings",
                 font=("Georgia", 26, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        return page

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
    # Map of page name -> load method name
    _LOAD_METHODS = {
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
            # Refresh data every time the page is shown
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