"""
app/ui/maintenance_page.py
===========================
Maintenance ticket management page.
Lists tickets with priority colour badges, status filter,
and actions to create, assign, update status, and view detail.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import (
    MaintenanceTicket, MaintenancePriority, MaintenanceStatus,
    Apartment, Property, Tenant, User
)
from app.services.maintenance_service import get_all_tickets
from sqlalchemy.orm import joinedload


PRIORITY_COLORS = {
    "urgent": "#E74C3C",
    "high":   "#E67E22",
    "medium": "#3498DB",
    "low":    "#7F8C8D",
}

STATUS_COLORS = {
    "new":           "#E74C3C",
    "triaged":       "#E67E22",
    "scheduled":     "#3498DB",
    "in_progress":   "#2ECC71",
    "waiting_parts": "#9B59B6",
    "resolved":      "#27AE60",
    "closed":        "#7F8C8D",
}


class MaintenancePage(tb.Frame):
    """Maintenance ticket management page."""

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self._build_ui()
        self.load_tickets()

    def destroy(self):
        try:
            self.db.close()
        except Exception:
            pass
        super().destroy()

    def _refresh_db(self):
        """Close and recreate the session to avoid MySQL REPEATABLE READ caching."""
        try:
            self.db.close()
        except Exception:
            pass
        from app.db.database import SessionLocal
        self.db = SessionLocal()


    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        header = tb.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill=X)

        tb.Label(header, text="Maintenance",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)

        btn_bar = tb.Frame(header)
        btn_bar.pack(side=RIGHT)

        if self.user.has_permission("maintenance.create"):
            tb.Button(btn_bar, text="＋  New Ticket",
                      bootstyle="success", padding=(10, 6),
                      command=self._open_create_dialog).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("maintenance.update"):
            tb.Button(btn_bar, text="✎  Update Status",
                      bootstyle="secondary", padding=(10, 6),
                      command=self._open_update_dialog).pack(side=LEFT, padx=(0, 6))

            tb.Button(btn_bar, text="👤  Assign",
                      bootstyle="info", padding=(10, 6),
                      command=self._assign_selected).pack(side=LEFT, padx=(0, 6))

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=20)

        # Filters
        filter_bar = tb.Frame(self, padding=(20, 10, 20, 4))
        filter_bar.pack(fill=X)

        tb.Label(filter_bar, text="Status:", font=("Helvetica", 11)).pack(side=LEFT)
        self._status_var = tb.StringVar(value="All")
        tb.Combobox(filter_bar, textvariable=self._status_var,
                    values=["All", "New", "Triaged", "Scheduled",
                            "In Progress", "Waiting Parts", "Resolved", "Closed"],
                    state="readonly", font=("Helvetica", 11), width=14).pack(side=LEFT, padx=(6, 16))
        self._status_var.trace_add("write", lambda *_: self.load_tickets())

        tb.Label(filter_bar, text="Priority:", font=("Helvetica", 11)).pack(side=LEFT)
        self._priority_var = tb.StringVar(value="All")
        tb.Combobox(filter_bar, textvariable=self._priority_var,
                    values=["All", "Urgent", "High", "Medium", "Low"],
                    state="readonly", font=("Helvetica", 11), width=10).pack(side=LEFT, padx=(6, 0))
        self._priority_var.trace_add("write", lambda *_: self.load_tickets())

        # Table
        tbl = tb.Frame(self, padding=(20, 8, 20, 0))
        tbl.pack(fill=BOTH, expand=YES)

        cols = ("id", "title", "apartment", "tenant", "priority", "status", "assigned", "created")
        self.tree = tb.Treeview(tbl, columns=cols, show="headings",
                                bootstyle="dark", selectmode="browse")

        col_cfg = [
            ("id",        "ID",        50,  CENTER),
            ("title",     "Title",     220, W),
            ("apartment", "Unit",      80,  CENTER),
            ("tenant",    "Tenant",    160, W),
            ("priority",  "Priority",  90,  CENTER),
            ("status",    "Status",    110, CENTER),
            ("assigned",  "Assigned",  140, W),
            ("created",   "Created",   120, CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self.tree.heading(cid, text=heading, anchor=anchor)
            self.tree.column(cid, width=width, anchor=anchor, minwidth=40)

        for prio, color in PRIORITY_COLORS.items():
            self.tree.tag_configure(f"prio_{prio}", foreground=color)

        sb = tb.Scrollbar(tbl, orient=VERTICAL, command=self.tree.yview, bootstyle="round-dark")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        self.tree.bind("<Double-1>", lambda _: self._open_detail_panel())

        self._count_var = tb.StringVar()
        tb.Label(self, textvariable=self._count_var,
                 font=("Helvetica", 10), bootstyle="secondary").pack(
            anchor=E, padx=24, pady=(4, 10))

    # ── Data ──────────────────────────────────────────────────────────────
    def load_tickets(self, *_):
        self._refresh_db()
        for row in self.tree.get_children():
            self.tree.delete(row)

        status_val   = self._status_var.get()
        priority_val = self._priority_var.get()

        status_map = {
            "New": "new", "Triaged": "triaged", "Scheduled": "scheduled",
            "In Progress": "in_progress", "Waiting Parts": "waiting_parts",
            "Resolved": "resolved", "Closed": "closed",
        }
        priority_map = {
            "Urgent": "urgent", "High": "high", "Medium": "medium", "Low": "low"
        }

        tickets = get_all_tickets(
            self.db,
            status=status_map.get(status_val),
            priority=priority_map.get(priority_val),
            city_id=self.user.city_id if self.user.city_id else None,
        )

        # Batch load related data
        apt_ids    = list({t.apartment_id for t in tickets if t.apartment_id})
        tenant_ids = list({t.tenant_id for t in tickets if t.tenant_id})
        user_ids   = list({t.assigned_to for t in tickets if t.assigned_to})

        apts    = {a.id: a for a in self.db.query(Apartment).filter(Apartment.id.in_(apt_ids)).all()}
        tenants = {t.id: t for t in self.db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()}
        users   = {u.id: u for u in self.db.query(User).filter(User.id.in_(user_ids)).all()}

        for t in tickets:
            apt    = apts.get(t.apartment_id)
            tenant = tenants.get(t.tenant_id) if t.tenant_id else None
            staff  = users.get(t.assigned_to) if t.assigned_to else None
            prio   = t.priority.value if t.priority else "medium"
            tag    = f"prio_{prio}"

            self.tree.insert("", END, tags=(tag,), values=(
                t.id,
                t.title,
                apt.unit_number if apt else "—",
                tenant.full_name if tenant else "—",
                prio.title(),
                t.status.value.replace("_", " ").title() if t.status else "—",
                staff.full_name if staff else "Unassigned",
                t.created_at.strftime("%d %b %Y") if t.created_at else "—",
            ))

        self._count_var.set(f"{len(tickets)} ticket(s)")

    def _selected_ticket_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    # ── Actions ───────────────────────────────────────────────────────────
    def _open_create_dialog(self):
        from app.ui.create_ticket_dialog import CreateTicketDialog
        dlg = CreateTicketDialog(self, user=self.user)
        self.wait_window(dlg)
        self.load_tickets()

    def _open_update_dialog(self):
        tid = self._selected_ticket_id()
        if tid is None:
            Messagebox.show_warning("Please select a ticket to update.", title="No Selection")
            return
        from app.ui.ticket_detail_panel import TicketDetailPanel
        dlg = TicketDetailPanel(self, user=self.user, ticket_id=tid)
        self.wait_window(dlg)
        self.load_tickets()

    def _open_detail_panel(self):
        tid = self._selected_ticket_id()
        if not tid:
            return
        from app.ui.ticket_detail_panel import TicketDetailPanel
        dlg = TicketDetailPanel(self, user=self.user, ticket_id=tid)
        self.wait_window(dlg)
        self.load_tickets()

    def _assign_selected(self):
        tid = self._selected_ticket_id()
        if tid is None:
            Messagebox.show_warning("Please select a ticket to assign.", title="No Selection")
            return
        from app.ui.ticket_detail_panel import AssignDialog
        dlg = AssignDialog(self, user=self.user, ticket_id=tid)
        self.wait_window(dlg)
        self.load_tickets()