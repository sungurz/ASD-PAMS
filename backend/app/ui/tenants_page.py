"""
Tenant management page — lists all tenants with search,
shows their current lease status, and provides actions
for registering, editing, and archiving tenants.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import Tenant
from app.services.tenant_service import search_tenants, archive_tenant
from sqlalchemy.orm import joinedload


STATUS_COLORS = {
    "Active":   "success",
    "Inactive": "secondary",
    "Leased":   "primary",
}


class TenantsPage(tb.Frame):
    """Tenant management page."""

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self._build_ui()
        self.load_tenants()

    # ── UI 
    def _build_ui(self):
        # ── Header ──
        header = tb.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill=X)

        tb.Label(header, text="Tenants",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)

        btn_bar = tb.Frame(header)
        btn_bar.pack(side=RIGHT)

        if self.user.has_permission("tenant.create"):
            tb.Button(btn_bar, text="＋  Register Tenant",
                      bootstyle="success", padding=(10, 6),
                      command=self._open_add_dialog).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("lease.create"):
            tb.Button(btn_bar, text="📄  New Lease",
                      bootstyle="primary", padding=(10, 6),
                      command=self._open_lease_dialog).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("tenant.update"):
            tb.Button(btn_bar, text="✎  Edit",
                      bootstyle="secondary", padding=(10, 6),
                      command=self._edit_selected).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("tenant.archive"):
            tb.Button(btn_bar, text="🗃  Archive",
                      bootstyle="warning", padding=(10, 6),
                      command=self._archive_selected).pack(side=LEFT)

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=20)

        # ── Search bar ──
        search_bar = tb.Frame(self, padding=(20, 10, 20, 4))
        search_bar.pack(fill=X)

        tb.Label(search_bar, text="🔍", font=("Helvetica", 13)).pack(side=LEFT, padx=(0, 6))
        self._search_var = tb.StringVar()
        self._search_var.trace_add("write", lambda *_: self.load_tenants())
        tb.Entry(search_bar, textvariable=self._search_var,
                 font=("Helvetica", 12), width=36).pack(side=LEFT)

        # Show inactive toggle
        self._show_inactive = tb.BooleanVar(value=False)
        tb.Checkbutton(
            search_bar, text="Show inactive",
            variable=self._show_inactive, bootstyle="round-toggle",
            command=self.load_tenants,
        ).pack(side=LEFT, padx=(16, 0))

        # ── Table ──
        table_frame = tb.Frame(self, padding=(20, 6, 20, 0))
        table_frame.pack(fill=BOTH, expand=YES)

        cols = ("id", "full_name", "email", "phone", "lease_status", "apartment")
        self.tree = tb.Treeview(
            table_frame, columns=cols, show="headings",
            bootstyle="dark", selectmode="browse",
        )

        col_cfg = [
            ("id",           "ID",            50,  CENTER),
            ("full_name",    "Full Name",      200, W),
            ("email",        "Email",          200, W),
            ("phone",        "Phone",          120, CENTER),
            ("lease_status", "Lease Status",   120, CENTER),
            ("apartment",    "Unit",           120, CENTER),
        ]
        for col_id, heading, width, anchor in col_cfg:
            self.tree.heading(col_id, text=heading, anchor=anchor)
            self.tree.column(col_id, width=width, anchor=anchor, minwidth=40)

        # Tag colours for lease status
        self.tree.tag_configure("leased",   foreground="#2ECC71")
        self.tree.tag_configure("unleased", foreground="#7F8C8D")
        self.tree.tag_configure("inactive", foreground="#E74C3C")

        scrollbar = tb.Scrollbar(table_frame, orient=VERTICAL,
                                 command=self.tree.yview, bootstyle="round-dark")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Double-click to view detail
        self.tree.bind("<Double-1>", lambda _: self._view_selected())

        # Footer
        self._count_var = tb.StringVar()
        tb.Label(self, textvariable=self._count_var,
                 font=("Helvetica", 10), bootstyle="secondary").pack(
            anchor=E, padx=24, pady=(4, 10)
        )

    # ── Data 
    def load_tenants(self, *_):
        self.db.close()
        self.db=SessionLocal()
        for row in self.tree.get_children():
            self.tree.delete(row)

        query     = self._search_var.get().strip()
        active_only = not self._show_inactive.get()

        tenants = search_tenants(self.db, query=query, active_only=active_only)

        # Eager-load leases for each tenant efficiently
        if tenants:
            ids = [t.id for t in tenants]
            from app.db.models import LeaseAgreement, LeaseStatus, Apartment
            active_leases = {
                la.tenant_id: la
                for la in self.db.query(LeaseAgreement)
                .options(joinedload(LeaseAgreement.apartment))
                .filter(
                    LeaseAgreement.tenant_id.in_(ids),
                    LeaseAgreement.status == LeaseStatus.ACTIVE,
                )
                .all()
            }
        else:
            active_leases = {}

        for t in tenants:
            lease = active_leases.get(t.id)
            if not t.is_active:
                status_text = "Inactive"
                unit_text   = "—"
                tag         = "inactive"
            elif lease:
                status_text = "Leased"
                unit_text   = lease.apartment.unit_number if lease.apartment else "—"
                tag         = "leased"
            else:
                status_text = "No Lease"
                unit_text   = "—"
                tag         = "unleased"

            self.tree.insert("", END, tags=(tag,), values=(
                t.id,
                t.full_name,
                t.email,
                t.phone,
                status_text,
                unit_text,
            ))

        self._count_var.set(f"{len(tenants)} tenant(s)")

    def _selected_tenant_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    # ── Actions
    def _open_add_dialog(self):
        from app.ui.add_tenant_dialog import AddTenantDialog
        dlg = AddTenantDialog(self, user=self.user)
        self.wait_window(dlg)
        self.load_tenants()

    def _edit_selected(self):
        tid = self._selected_tenant_id()
        if tid is None:
            Messagebox.show_warning("Please select a tenant to edit.", title="No Selection")
            return
        from app.ui.add_tenant_dialog import AddTenantDialog
        tenant = self.db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            return
        dlg = AddTenantDialog(self, user=self.user, tenant=tenant)
        self.wait_window(dlg)
        self.load_tenants()

    def _open_lease_dialog(self):
        tid = self._selected_tenant_id()
        from app.ui.create_lease_dialog import CreateLeaseDialog
        dlg = CreateLeaseDialog(self, user=self.user, preselected_tenant_id=tid)
        self.wait_window(dlg)
        self.load_tenants()

    def _archive_selected(self):
        tid = self._selected_tenant_id()
        if tid is None:
            Messagebox.show_warning("Please select a tenant to archive.", title="No Selection")
            return
        confirm = Messagebox.yesno(
            "Archive this tenant? They will be hidden from active lists but their records are kept.",
            title="Confirm Archive",
        )
        if confirm == "Yes":
            archive_tenant(self.db, tid)
            self.load_tenants()

    def _view_selected(self):
        """Double-click — open edit dialog for now (detail view in later sprint)."""
        tid = self._selected_tenant_id()
        if tid is None:
            return
        if self.user.has_permission("tenant.update"):
            self._edit_selected()