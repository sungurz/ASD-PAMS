# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/complaints_page.py
==========================
Complaints management page.
Lists complaints by category and status, with actions
to create new complaints and update their status.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import Complaint, ComplaintStatus, ComplaintCategory, Tenant, User
from app.services.complaint_service import get_all_complaints, update_complaint_status


STATUS_COLORS = {
    "open":         "#E74C3C",
    "under_review": "#E67E22",
    "resolved":     "#2ECC71",
    "closed":       "#7F8C8D",
}


class ComplaintsPage(tb.Frame):

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self._build_ui()
        self.load_complaints()

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


    def _build_ui(self):
        header = tb.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill=X)

        tb.Label(header, text="Complaints",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)

        btn_bar = tb.Frame(header)
        btn_bar.pack(side=RIGHT)

        if self.user.has_permission("complaint.create"):
            tb.Button(btn_bar, text="＋  New Complaint",
                      bootstyle="success", padding=(10, 6),
                      command=self._open_create_dialog).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("complaint.update"):
            tb.Button(btn_bar, text="✎  Update Status",
                      bootstyle="secondary", padding=(10, 6),
                      command=self._open_update_dialog).pack(side=LEFT)

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=20)

        # Filters
        filter_bar = tb.Frame(self, padding=(20, 10, 20, 4))
        filter_bar.pack(fill=X)

        tb.Label(filter_bar, text="Status:", font=("Helvetica", 11)).pack(side=LEFT)
        self._status_var = tb.StringVar(value="All")
        tb.Combobox(filter_bar, textvariable=self._status_var,
                    values=["All", "Open", "Under Review", "Resolved", "Closed"],
                    state="readonly", font=("Helvetica", 11), width=14).pack(side=LEFT, padx=(6, 16))
        self._status_var.trace_add("write", lambda *_: self.load_complaints())

        tb.Label(filter_bar, text="Category:", font=("Helvetica", 11)).pack(side=LEFT)
        self._cat_var = tb.StringVar(value="All")
        tb.Combobox(filter_bar, textvariable=self._cat_var,
                    values=["All", "Noise", "Maintenance", "Neighbour",
                            "Billing", "Staff Conduct", "Other"],
                    state="readonly", font=("Helvetica", 11), width=14).pack(side=LEFT, padx=(6, 0))
        self._cat_var.trace_add("write", lambda *_: self.load_complaints())

        # Table
        tbl = tb.Frame(self, padding=(20, 8, 20, 0))
        tbl.pack(fill=BOTH, expand=YES)

        cols = ("id", "tenant", "category", "subject", "status", "assigned")
        self.tree = tb.Treeview(tbl, columns=cols, show="headings",
                                bootstyle="dark", selectmode="browse")

        col_cfg = [
            ("id",       "ID",        50,  CENTER),
            ("tenant",   "Tenant",    180, W),
            ("category", "Category",  120, CENTER),
            ("subject",  "Subject",   240, W),
            ("status",   "Status",    110, CENTER),
            ("assigned", "Assigned",  140, W),
        ]
        for cid, heading, width, anchor in col_cfg:
            self.tree.heading(cid, text=heading, anchor=anchor)
            self.tree.column(cid, width=width, anchor=anchor, minwidth=40)

        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(status, foreground=color)

        sb = tb.Scrollbar(tbl, orient=VERTICAL, command=self.tree.yview, bootstyle="round-dark")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        self._count_var = tb.StringVar()
        tb.Label(self, textvariable=self._count_var,
                 font=("Helvetica", 10), bootstyle="secondary").pack(
            anchor=E, padx=24, pady=(4, 10))

    def load_complaints(self, *_):
        self._refresh_db()
        for row in self.tree.get_children():
            self.tree.delete(row)

        status_map = {
            "Open": "open", "Under Review": "under_review",
            "Resolved": "resolved", "Closed": "closed",
        }
        cat_map = {
            "Noise": "noise", "Maintenance": "maintenance",
            "Neighbour": "neighbour", "Billing": "billing",
            "Staff Conduct": "staff_conduct", "Other": "other",
        }

        complaints = get_all_complaints(
            self.db,
            status=status_map.get(self._status_var.get()),
            category=cat_map.get(self._cat_var.get()),
        )

        tenant_ids = list({c.tenant_id for c in complaints})
        user_ids   = list({c.assigned_to for c in complaints if c.assigned_to})
        tenants    = {t.id: t for t in self.db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()}
        users      = {u.id: u for u in self.db.query(User).filter(User.id.in_(user_ids)).all()}

        for c in complaints:
            tenant   = tenants.get(c.tenant_id)
            assigned = users.get(c.assigned_to) if c.assigned_to else None
            tag      = c.status.value if c.status else "open"

            self.tree.insert("", END, tags=(tag,), values=(
                c.id,
                tenant.full_name if tenant else "—",
                c.category.value.replace("_", " ").title() if c.category else "—",
                c.subject,
                c.status.value.replace("_", " ").title() if c.status else "—",
                assigned.full_name if assigned else "Unassigned",
            ))

        self._count_var.set(f"{len(complaints)} complaint(s)")

    def _selected_complaint_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _open_create_dialog(self):
        from app.ui.create_complaint_dialog import CreateComplaintDialog
        dlg = CreateComplaintDialog(self, user=self.user)
        self.wait_window(dlg)
        self.load_complaints()

    def _open_update_dialog(self):
        cid = self._selected_complaint_id()
        if cid is None:
            Messagebox.show_warning("Please select a complaint.", title="No Selection")
            return
        from app.ui.create_complaint_dialog import UpdateComplaintDialog
        dlg = UpdateComplaintDialog(self, user=self.user, complaint_id=cid)
        self.wait_window(dlg)
        self.load_complaints()