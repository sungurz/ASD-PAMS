"""
app/ui/create_ticket_dialog.py
================================
Dialog to create a new maintenance ticket.
Apartments are scoped to the logged-in user's city.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import Apartment, Property, City
from app.services.maintenance_service import create_ticket
from sqlalchemy.orm import joinedload


class CreateTicketDialog(tb.Toplevel):

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self.title("New Maintenance Ticket")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("500x520")

        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Create Ticket", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="New Maintenance Ticket",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 16))

        def lbl(text):
            tb.Label(f, text=text, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        # Apartment selector — scoped to user's city
        lbl("Apartment / Unit *")
        q = (
            self.db.query(Apartment, Property)
            .join(Property, Apartment.property_id == Property.id)
        )
        city_id = getattr(self.user, "city_id", None)
        if city_id:
            q = q.filter(Property.city_id == city_id)
        apts = q.order_by(Property.name, Apartment.unit_number).all()

        self._apt_map: dict[str, int] = {}
        for apt, prop in apts:
            label = f"{prop.name} — Unit {apt.unit_number}"
            self._apt_map[label] = apt.id

        self.v_apt = tb.StringVar()
        self._apt_combo = tb.Combobox(f, textvariable=self.v_apt,
                                       values=list(self._apt_map.keys()),
                                       state="readonly", font=("Helvetica", 12))
        self._apt_combo.pack(fill=X, pady=(2, 12))
        self._apt_combo.bind("<<ComboboxSelected>>", self._on_apt_selected)

        # Tenant selector (populated when apartment is chosen)
        lbl("Tenant (optional)")
        self.v_tenant = tb.StringVar()
        self._tenant_combo = tb.Combobox(f, textvariable=self.v_tenant,
                                          state="readonly", font=("Helvetica", 12))
        self._tenant_combo.pack(fill=X, pady=(2, 12))

        # Title
        lbl("Title *")
        self.v_title = tb.Entry(f, font=("Helvetica", 12))
        self.v_title.pack(fill=X, pady=(2, 12))

        # Priority
        lbl("Priority")
        self.v_priority = tb.StringVar(value="Medium")
        tb.Combobox(f, textvariable=self.v_priority,
                    values=["Low", "Medium", "High", "Urgent"],
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 12))

        # Description
        lbl("Description (optional)")
        self.v_desc = tb.Entry(f, font=("Helvetica", 12))
        self.v_desc.pack(fill=X, pady=(2, 0))

    def _on_apt_selected(self, _=None):
        label = self.v_apt.get()
        if label not in self._apt_map:
            return
        apt_id = self._apt_map[label]
        from app.db.models import LeaseAgreement, LeaseStatus
        leases = (
            self.db.query(LeaseAgreement)
            .options(joinedload(LeaseAgreement.tenant))
            .filter(
                LeaseAgreement.apartment_id == apt_id,
                LeaseAgreement.status == LeaseStatus.ACTIVE,
            )
            .all()
        )
        self._tenant_map: dict[str, int] = {"— None —": 0}
        for lease in leases:
            if lease.tenant:
                self._tenant_map[lease.tenant.full_name] = lease.tenant.id
        self._tenant_combo.configure(values=list(self._tenant_map.keys()))
        self.v_tenant.set("— None —")

    def _center(self, parent):
        self.update_idletasks()
        w, h = 500, 520
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        apt_label = self.v_apt.get()
        title     = self.v_title.get().strip()
        priority  = self.v_priority.get().lower()
        desc      = self.v_desc.get().strip()

        if not apt_label or apt_label not in self._apt_map:
            Messagebox.show_warning("Please select an apartment.", title="Validation", parent=self)
            return
        if not title:
            Messagebox.show_warning("Title is required.", title="Validation", parent=self)
            return

        apt_id    = self._apt_map[apt_label]
        tenant_id = None
        if hasattr(self, "_tenant_map"):
            t_label   = self.v_tenant.get()
            tenant_id = self._tenant_map.get(t_label) or None

        ticket, err = create_ticket(
            self.db,
            apartment_id=apt_id,
            title=title,
            description=desc or None,
            priority=priority,
            tenant_id=tenant_id,
            raised_by_user_id=self.user.id,
        )
        if err:
            Messagebox.show_warning(err, title="Error", parent=self)
            return

        Messagebox.show_info(f"Ticket #{ticket.id} created.", title="Success", parent=self)
        self.destroy()