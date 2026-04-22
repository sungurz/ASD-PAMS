# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/create_complaint_dialog.py
===================================
Two dialogs:
  CreateComplaintDialog  — raise a new complaint on behalf of a tenant.
  UpdateComplaintDialog  — update status and add resolution notes.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import Tenant, User, Role, RoleName
from app.services.complaint_service import create_complaint, update_complaint_status


CATEGORIES = [
    ("Noise",         "noise"),
    ("Maintenance",   "maintenance"),
    ("Neighbour",     "neighbour"),
    ("Billing",       "billing"),
    ("Staff Conduct", "staff_conduct"),
    ("Other",         "other"),
]

STATUSES = [
    ("Open",         "open"),
    ("Under Review", "under_review"),
    ("Resolved",     "resolved"),
    ("Closed",       "closed"),
]


class CreateComplaintDialog(tb.Toplevel):

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self.title("New Complaint")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("480x480")

        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Submit Complaint", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="New Complaint",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 16))

        def lbl(text):
            tb.Label(f, text=text, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        # Tenant selector
        lbl("Tenant *")
        tenants = self.db.query(Tenant).filter(Tenant.is_active == True).order_by(Tenant.full_name).all()
        self._tenant_map = {t.full_name: t.id for t in tenants}
        self.v_tenant = tb.StringVar()
        tb.Combobox(f, textvariable=self.v_tenant,
                    values=list(self._tenant_map.keys()),
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 12))

        # Category
        lbl("Category *")
        self.v_category = tb.StringVar(value=CATEGORIES[0][0])
        tb.Combobox(f, textvariable=self.v_category,
                    values=[c[0] for c in CATEGORIES],
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 12))

        # Subject
        lbl("Subject *")
        self.v_subject = tb.Entry(f, font=("Helvetica", 12))
        self.v_subject.pack(fill=X, pady=(2, 12))

        # Description
        lbl("Description (optional)")
        self.v_desc = tb.Entry(f, font=("Helvetica", 12))
        self.v_desc.pack(fill=X, pady=(2, 0))

    def _center(self, parent):
        self.update_idletasks()
        w, h = 480, 480
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        tenant_label = self.v_tenant.get()
        cat_label    = self.v_category.get()
        subject      = self.v_subject.get().strip()
        desc         = self.v_desc.get().strip()

        if not tenant_label or tenant_label not in self._tenant_map:
            Messagebox.show_warning("Please select a tenant.", title="Validation", parent=self)
            return
        if not subject:
            Messagebox.show_warning("Subject is required.", title="Validation", parent=self)
            return

        cat_value = next((v for lbl, v in CATEGORIES if lbl == cat_label), "other")
        tenant_id = self._tenant_map[tenant_label]

        complaint, err = create_complaint(
            self.db,
            tenant_id=tenant_id,
            category=cat_value,
            subject=subject,
            description=desc or None,
            raised_by_user_id=self.user.id,
        )
        if err:
            Messagebox.show_warning(err, title="Error", parent=self)
            return

        Messagebox.show_info(f"Complaint #{complaint.id} submitted.", title="Success", parent=self)
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────

class UpdateComplaintDialog(tb.Toplevel):

    def __init__(self, parent, user, complaint_id: int):
        super().__init__(parent)
        self.user         = user
        self.db           = SessionLocal()
        self.complaint_id = complaint_id
        self.title("Update Complaint")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._load_complaint()
        self._center(parent)

    def _build_ui(self):
        self.geometry("460x440")

        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Save", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Update Complaint",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 4))

        self._info_var = tb.StringVar(value="")
        tb.Label(f, textvariable=self._info_var, font=("Helvetica", 10),
                 bootstyle="info").pack(anchor=W, pady=(0, 12))

        def lbl(text):
            tb.Label(f, text=text, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        # Status
        lbl("New Status *")
        self.v_status = tb.StringVar()
        tb.Combobox(f, textvariable=self.v_status,
                    values=[s[0] for s in STATUSES],
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 12))

        # Assign to — only staff who handle complaints
        lbl("Assign To (optional)")
        from app.db.models import Role, RoleName
        # Only front_desk, location_admin, manager can handle complaints
        allowed_roles = self.db.query(Role).filter(
            Role.name.in_([
                RoleName.FRONT_DESK,
                RoleName.LOCATION_ADMIN,
                RoleName.MANAGER,
            ])
        ).all()
        allowed_role_ids = {r.id for r in allowed_roles}
        staff_q = self.db.query(User).filter(
            User.is_active == True,
            User.role_id.in_(allowed_role_ids),
        )
        # City scoping — location admins only see staff from their city
        city_id = getattr(self.user, "city_id", None)
        if city_id:
            staff_q = staff_q.filter(
                (User.city_id == city_id) | (User.city_id == None)
            )
        staff = staff_q.order_by(User.full_name).all()
        self._staff_map = {"— Unassigned —": 0}
        for u in staff:
            self._staff_map[u.full_name or u.username] = u.id
        self.v_assigned = tb.StringVar(value="— Unassigned —")
        tb.Combobox(f, textvariable=self.v_assigned,
                    values=list(self._staff_map.keys()),
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 12))

        # Resolution notes
        lbl("Resolution Notes (optional)")
        self.v_notes = tb.Entry(f, font=("Helvetica", 12))
        self.v_notes.pack(fill=X, pady=(2, 0))

    def _load_complaint(self):
        from app.db.models import Complaint
        c = self.db.query(Complaint).filter(Complaint.id == self.complaint_id).first()
        if c:
            self._info_var.set(f"#{c.id} — {c.subject}  |  Current: {c.status.value.replace('_', ' ').title()}")
            current_label = next((lbl for lbl, val in STATUSES if val == c.status.value), "Open")
            self.v_status.set(current_label)
            if c.resolution_notes:
                self.v_notes.insert(0, c.resolution_notes)

    def _center(self, parent):
        self.update_idletasks()
        w, h = 460, 440
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        status_label = self.v_status.get()
        status_value = next((v for lbl, v in STATUSES if lbl == status_label), None)
        if not status_value:
            Messagebox.show_warning("Please select a status.", title="Validation", parent=self)
            return

        assigned_label = self.v_assigned.get()
        assigned_id    = self._staff_map.get(assigned_label) or None

        ok, err = update_complaint_status(
            self.db,
            self.complaint_id,
            status_value,
            resolution_notes=self.v_notes.get().strip() or None,
            assigned_to_user_id=assigned_id,
            updated_by_user_id=self.user.id,
        )
        if err:
            Messagebox.show_warning(err, title="Error", parent=self)
            return

        Messagebox.show_info("Complaint updated.", title="Success", parent=self)
        self.destroy()