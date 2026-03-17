"""
app/ui/create_lease_dialog.py
==============================
Dialog for creating a new lease agreement.
Front-desk selects:
  - Tenant (searchable)
  - Apartment (available only)
  - Start date, end date
  - Agreed rent (pre-filled from apartment, editable)
  - Deposit
  - Notes
Business rules are enforced by lease_service.create_lease().
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import date, timedelta
from decimal import Decimal

from app.db.database import SessionLocal
from app.db.models import Tenant, Apartment, Property, City, ApartmentStatus
from app.services.lease_service import create_lease
from sqlalchemy.orm import joinedload


class CreateLeaseDialog(tb.Toplevel):
    """Modal dialog to create a lease agreement."""

    def __init__(self, parent, user, preselected_tenant_id: int | None = None):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()

        self.title("Create Lease Agreement")
        self.resizable(False, False)
        self.grab_set()

        self._tenant_map: dict[str, int]    = {}
        self._apartment_map: dict[str, int] = {}
        self._apartment_rents: dict[int, Decimal] = {}

        self._build_ui()
        self._center(parent)
        self._load_tenants(preselected_tenant_id)
        self._load_apartments()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.geometry("500x560")
        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="New Lease Agreement",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 4))
        tb.Label(f, text="A lease links one tenant to one available apartment.",
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(0, 16))

        def lbl(text):
            tb.Label(f, text=text, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        # Tenant
        lbl("Tenant *")
        self.v_tenant = tb.StringVar()
        self._tenant_combo = tb.Combobox(
            f, textvariable=self.v_tenant,
            state="readonly", font=("Helvetica", 12),
        )
        self._tenant_combo.pack(fill=X, pady=(2, 12))

        # Apartment
        lbl("Apartment (available only) *")
        self.v_apartment = tb.StringVar()
        self._apt_combo = tb.Combobox(
            f, textvariable=self.v_apartment,
            state="readonly", font=("Helvetica", 12),
        )
        self._apt_combo.pack(fill=X, pady=(2, 12))
        self._apt_combo.bind("<<ComboboxSelected>>", self._on_apartment_selected)

        # Dates row
        row = tb.Frame(f)
        row.pack(fill=X, pady=(0, 12))
        left = tb.Frame(row)
        left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right = tb.Frame(row)
        right.pack(side=RIGHT, fill=X, expand=YES)

        lbl_left = lambda t: tb.Label(left, text=t, font=("Helvetica", 10),
                                       bootstyle="secondary").pack(anchor=W)
        lbl_right = lambda t: tb.Label(right, text=t, font=("Helvetica", 10),
                                        bootstyle="secondary").pack(anchor=W)

        lbl_left("Start Date * (DD/MM/YYYY)")
        self.v_start = tb.Entry(left, font=("Helvetica", 12))
        self.v_start.insert(0, date.today().strftime("%d/%m/%Y"))
        self.v_start.pack(fill=X, pady=(2, 0))

        lbl_right("End Date * (DD/MM/YYYY)")
        self.v_end = tb.Entry(right, font=("Helvetica", 12))
        default_end = date.today() + timedelta(days=365)
        self.v_end.insert(0, default_end.strftime("%d/%m/%Y"))
        self.v_end.pack(fill=X, pady=(2, 0))

        # Rent and deposit row
        row2 = tb.Frame(f)
        row2.pack(fill=X, pady=(0, 12))
        left2 = tb.Frame(row2)
        left2.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right2 = tb.Frame(row2)
        right2.pack(side=RIGHT, fill=X, expand=YES)

        tb.Label(left2, text="Agreed Monthly Rent (£) *", font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=W)
        self.v_rent = tb.Entry(left2, font=("Helvetica", 12))
        self.v_rent.pack(fill=X, pady=(2, 0))

        tb.Label(right2, text="Deposit (£)", font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=W)
        self.v_deposit = tb.Entry(right2, font=("Helvetica", 12))
        self.v_deposit.pack(fill=X, pady=(2, 0))

        # Notes
        lbl("Notes (optional)")
        self.v_notes = tb.Text(f, font=("Helvetica", 12), height=4)
        self.v_notes.pack(fill=X, pady=(2, 0))

        # Buttons
        btn_row = tb.Frame(f)
        btn_row.pack(fill=X, pady=(16, 0))
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Create Lease", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

    # ── Data loading ──────────────────────────────────────────────────────
    def _load_tenants(self, preselect_id: int | None):
        from app.db.models import LeaseAgreement, LeaseStatus
        # Find tenants who already have an active lease
        active_tenant_ids = {
            row[0] for row in
            self.db.query(LeaseAgreement.tenant_id)
            .filter(LeaseAgreement.status == LeaseStatus.ACTIVE)
            .all()
        }
        tenants = (
            self.db.query(Tenant)
            .filter(Tenant.is_active == True)
            .order_by(Tenant.full_name)
            .all()
        )
        self._tenant_map = {}
        preselect_label = None
        for t in tenants:
            if t.id in active_tenant_ids:
                label = f"{t.full_name} — already leased"
                # Still add but mark as already leased so user knows
            else:
                label = f"{t.full_name} ({t.email})"
                self._tenant_map[label] = t.id
                if t.id == preselect_id:
                    preselect_label = label

        self._tenant_combo.configure(values=list(self._tenant_map.keys()))
        if preselect_label:
            self.v_tenant.set(preselect_label)
        elif preselect_id and preselect_id in active_tenant_ids:
            Messagebox.show_warning(
                "This tenant already has an active lease.",
                title="Cannot Create Lease", parent=self
            )

    def _load_apartments(self):
        apts = (
            self.db.query(Apartment)
            .options(joinedload(Apartment.property).joinedload(Property.city))
            .filter(Apartment.status == ApartmentStatus.AVAILABLE)
            .order_by(Apartment.unit_number)
            .all()
        )
        self._apartment_map   = {}
        self._apartment_rents = {}
        for apt in apts:
            city = apt.property.city.name if apt.property and apt.property.city else "?"
            prop = apt.property.name if apt.property else "?"
            label = f"{apt.unit_number} — {prop} ({city})  £{apt.monthly_rent:,.0f}/mo"
            self._apartment_map[label]        = apt.id
            self._apartment_rents[apt.id]     = apt.monthly_rent

        self._apt_combo.configure(values=list(self._apartment_map.keys()))

    def _on_apartment_selected(self, _event=None):
        """Pre-fill rent when apartment is selected."""
        label = self.v_apartment.get()
        if label in self._apartment_map:
            apt_id = self._apartment_map[label]
            rent   = self._apartment_rents.get(apt_id)
            if rent:
                self.v_rent.delete(0, END)
                self.v_rent.insert(0, str(rent))

    # ── Helpers ───────────────────────────────────────────────────────────
    def _parse_date(self, text: str) -> date | None:
        text = text.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                from datetime import datetime
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _center(self, parent):
        self.update_idletasks()
        w, h = 500, 560
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    # ── Submit ────────────────────────────────────────────────────────────
    def _submit(self):
        tenant_label = self.v_tenant.get()
        apt_label    = self.v_apartment.get()

        if not tenant_label or tenant_label not in self._tenant_map:
            Messagebox.show_warning("Please select a tenant.", title="Validation", parent=self)
            return
        if not apt_label or apt_label not in self._apartment_map:
            Messagebox.show_warning("Please select an apartment.", title="Validation", parent=self)
            return

        start = self._parse_date(self.v_start.get())
        end   = self._parse_date(self.v_end.get())

        if not start:
            Messagebox.show_warning("Invalid start date. Use DD/MM/YYYY.", title="Validation", parent=self)
            return
        if not end:
            Messagebox.show_warning("Invalid end date. Use DD/MM/YYYY.", title="Validation", parent=self)
            return

        try:
            rent = Decimal(self.v_rent.get().strip())
        except Exception:
            Messagebox.show_warning("Monthly rent must be a valid number.", title="Validation", parent=self)
            return

        deposit_str = self.v_deposit.get().strip()
        deposit = Decimal(deposit_str) if deposit_str else None
        notes   = self.v_notes.get("1.0", "end").strip() or None

        tenant_id = self._tenant_map[tenant_label]
        apt_id    = self._apartment_map[apt_label]

        lease, error = create_lease(
            self.db,
            tenant_id=tenant_id,
            apartment_id=apt_id,
            start_date=start,
            end_date=end,
            agreed_rent=rent,
            deposit=deposit,
            notes=notes,
            created_by_user_id=self.user.id,
        )

        if error:
            Messagebox.show_warning(error, title="Cannot Create Lease", parent=self)
            return

        Messagebox.show_info(
            f"Lease created successfully!\n\nTenant is now assigned to apartment {lease.apartment_id}.",
            title="Lease Created",
            parent=self,
        )
        self.destroy()