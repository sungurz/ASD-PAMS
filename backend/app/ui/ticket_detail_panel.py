"""
app/ui/ticket_detail_panel.py
==============================
Ticket detail view — shows full info, update timeline,
and lets staff update status, add notes, log cost/time.
Also contains AssignDialog.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from decimal import Decimal

from app.db.database import SessionLocal
from app.db.models import (
    MaintenanceTicket, MaintenanceUpdate, MaintenanceStatus,
    Apartment, Tenant, User
)
from app.services.maintenance_service import update_status, assign_ticket
from sqlalchemy.orm import joinedload


STATUS_OPTIONS = [
    "new", "triaged", "scheduled", "in_progress",
    "waiting_parts", "resolved", "closed"
]

STATUS_COLORS = {
    "new":           "#E74C3C",
    "triaged":       "#E67E22",
    "scheduled":     "#3498DB",
    "in_progress":   "#2ECC71",
    "waiting_parts": "#9B59B6",
    "resolved":      "#27AE60",
    "closed":        "#7F8C8D",
}


class TicketDetailPanel(tb.Toplevel):

    def __init__(self, parent, user, ticket_id: int):
        super().__init__(parent)
        self.user      = user
        self.db        = SessionLocal()
        self.ticket_id = ticket_id
        self.title("Ticket Detail")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._load_ticket()
        self._center(parent)

    def _build_ui(self):
        self.geometry("560x620")

        # Buttons first
        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Close", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        if self.user.has_permission("maintenance.update"):
            tb.Button(btn_row, text="Save Update", bootstyle="success",
                      command=self._submit_update).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        # Info card
        self._info_var = tb.StringVar(value="Loading...")
        tb.Label(f, textvariable=self._info_var, font=("Helvetica", 11),
                 bootstyle="info", justify=LEFT).pack(anchor=W, pady=(0, 12))

        tb.Separator(f, orient=HORIZONTAL).pack(fill=X, pady=(0, 12))

        # Update form
        if self.user.has_permission("maintenance.update"):
            tb.Label(f, text="Update Status",
                     font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 8))

            row = tb.Frame(f)
            row.pack(fill=X, pady=(0, 8))

            left = tb.Frame(row)
            left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
            right = tb.Frame(row)
            right.pack(side=RIGHT, fill=X, expand=YES)

            tb.Label(left, text="New Status", font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)
            self.v_status = tb.StringVar()
            tb.Combobox(left, textvariable=self.v_status,
                        values=[s.replace("_", " ").title() for s in STATUS_OPTIONS],
                        state="readonly", font=("Helvetica", 11)).pack(fill=X, pady=(2, 0))

            tb.Label(right, text="Material Cost (£)", font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)
            self.v_cost = tb.Entry(right, font=("Helvetica", 11))
            self.v_cost.pack(fill=X, pady=(2, 0))

            row2 = tb.Frame(f)
            row2.pack(fill=X, pady=(0, 8))
            tb.Label(row2, text="Note", font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)
            self.v_note = tb.Entry(row2, font=("Helvetica", 11))
            self.v_note.pack(fill=X, pady=(2, 0))

            tb.Separator(f, orient=HORIZONTAL).pack(fill=X, pady=(8, 12))

        # Timeline
        tb.Label(f, text="Update History",
                 font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 6))

        tbl_frame = tb.Frame(f)
        tbl_frame.pack(fill=BOTH, expand=YES)

        cols = ("date", "by", "old", "new", "note")
        self.upd_tree = tb.Treeview(tbl_frame, columns=cols, show="headings",
                                     bootstyle="dark", height=6)
        col_cfg = [
            ("date", "Date",       120, CENTER),
            ("by",   "By",         120, W),
            ("old",  "From",       100, CENTER),
            ("new",  "To",         100, CENTER),
            ("note", "Note",       180, W),
        ]
        for cid, heading, width, anchor in col_cfg:
            self.upd_tree.heading(cid, text=heading, anchor=anchor)
            self.upd_tree.column(cid, width=width, anchor=anchor, minwidth=40)

        sb = tb.Scrollbar(tbl_frame, orient=VERTICAL, command=self.upd_tree.yview,
                          bootstyle="round-dark")
        self.upd_tree.configure(yscrollcommand=sb.set)
        self.upd_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

    def _load_ticket(self):
        ticket = (
            self.db.query(MaintenanceTicket)
            .filter(MaintenanceTicket.id == self.ticket_id)
            .first()
        )
        if not ticket:
            return

        apt    = self.db.query(Apartment).filter(Apartment.id == ticket.apartment_id).first()
        tenant = self.db.query(Tenant).filter(Tenant.id == ticket.tenant_id).first() if ticket.tenant_id else None

        info = (
            f"#{ticket.id}  {ticket.title}\n"
            f"Unit: {apt.unit_number if apt else '—'}   "
            f"Tenant: {tenant.full_name if tenant else '—'}   "
            f"Priority: {ticket.priority.value.title() if ticket.priority else '—'}\n"
            f"Status: {ticket.status.value.replace('_', ' ').title() if ticket.status else '—'}   "
            f"Created: {ticket.created_at.strftime('%d %b %Y') if ticket.created_at else '—'}"
        )
        self._info_var.set(info)

        if hasattr(self, "v_status") and ticket.status:
            self.v_status.set(ticket.status.value.replace("_", " ").title())

        # Load updates timeline
        updates = (
            self.db.query(MaintenanceUpdate)
            .filter(MaintenanceUpdate.ticket_id == self.ticket_id)
            .order_by(MaintenanceUpdate.created_at.desc())
            .all()
        )
        user_ids = list({u.updated_by for u in updates if u.updated_by})
        users    = {u.id: u for u in self.db.query(User).filter(User.id.in_(user_ids)).all()}

        for upd in updates:
            staff = users.get(upd.updated_by)
            self.upd_tree.insert("", END, values=(
                upd.created_at.strftime("%d %b %Y %H:%M") if upd.created_at else "—",
                staff.full_name if staff else "System",
                upd.old_status.value.replace("_", " ").title() if upd.old_status else "—",
                upd.new_status.value.replace("_", " ").title() if upd.new_status else "—",
                upd.note or "—",
            ))

    def _center(self, parent):
        self.update_idletasks()
        w, h = 560, 620
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit_update(self):
        status_label = self.v_status.get()
        status_value = status_label.lower().replace(" ", "_")
        note         = self.v_note.get().strip()
        cost_str     = self.v_cost.get().strip()

        actual_cost = None
        if cost_str:
            try:
                actual_cost = Decimal(cost_str)
            except Exception:
                Messagebox.show_warning("Invalid cost value.", title="Validation", parent=self)
                return

        ok, err = update_status(
            self.db,
            self.ticket_id,
            status_value,
            note=note or None,
            updated_by_user_id=self.user.id,
            material_cost=actual_cost,
        )
        if err:
            Messagebox.show_warning(err, title="Error", parent=self)
            return

        Messagebox.show_info("Ticket updated.", title="Success", parent=self)
        self.destroy()


# ── Assign Dialog ─────────────────────────────────────────────────────────────

class AssignDialog(tb.Toplevel):

    def __init__(self, parent, user, ticket_id: int):
        super().__init__(parent)
        self.user      = user
        self.db        = SessionLocal()
        self.ticket_id = ticket_id
        self.title("Assign Ticket")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("380x280")

        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Assign", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Assign Ticket",
                 font=("Georgia", 15, "bold")).pack(anchor=W, pady=(0, 16))

        tb.Label(f, text="Assign to Staff Member",
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

        # Load maintenance staff — scoped to the ticket's apartment city
        from app.db.models import Role, RoleName, MaintenanceTicket, Apartment, Property
        ticket = self.db.query(MaintenanceTicket).filter(
            MaintenanceTicket.id == self.ticket_id
        ).first()
        apt = self.db.query(Apartment).filter(
            Apartment.id == ticket.apartment_id
        ).first() if ticket else None
        prop = self.db.query(Property).filter(
            Property.id == apt.property_id
        ).first() if apt else None
        city_id = prop.city_id if prop else None

        maint_role = self.db.query(Role).filter(
            Role.name == RoleName.MAINTENANCE_STAFF
        ).first()

        self._staff_map: dict[str, int] = {}
        if maint_role:
            q = self.db.query(User).filter(
                User.role_id == maint_role.id,
                User.is_active == True,
            )
            if city_id:
                q = q.filter(User.city_id == city_id)
            for s in q.all():
                label = (s.full_name or s.username)
                self._staff_map[label] = s.id

        self.v_staff = tb.StringVar()
        tb.Combobox(f, textvariable=self.v_staff,
                    values=list(self._staff_map.keys()),
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 0))

        if not self._staff_map:
            tb.Label(f, text="No maintenance staff found.",
                     font=("Helvetica", 10), bootstyle="warning").pack(anchor=W, pady=(8, 0))

    def _center(self, parent):
        self.update_idletasks()
        w, h = 380, 280
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        label = self.v_staff.get()
        if not label or label not in self._staff_map:
            Messagebox.show_warning("Please select a staff member.", title="Validation", parent=self)
            return

        user_id = self._staff_map[label]
        ok, err = assign_ticket(
            self.db, self.ticket_id, user_id,
            updated_by_user_id=self.user.id
        )
        if err:
            Messagebox.show_warning(err, title="Error", parent=self)
            return

        Messagebox.show_info("Ticket assigned.", title="Success", parent=self)
        self.destroy()