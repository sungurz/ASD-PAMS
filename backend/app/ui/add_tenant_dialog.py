"""
app/ui/add_tenant_dialog.py
============================
Full tenant registration / edit dialog.
Uses a tabbed layout to keep the form manageable:
  Tab 1 — Personal Details
  Tab 2 — Employment & Income
  Tab 3 — Preferences & Requirements
  Tab 4 — References (up to 2)
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import date

from app.db.database import SessionLocal
from app.db.models import Tenant, ApartmentType
from app.services.tenant_service import (
    register_tenant, update_tenant, email_exists
)


APARTMENT_TYPE_OPTIONS = [
    "Any",
    "studio", "one_bed", "two_bed", "three_bed", "four_bed"
]

REFERENCE_TYPES = ["Previous Landlord", "Employer", "Personal", "Character"]


class AddTenantDialog(tb.Toplevel):
    """
    Modal dialog for registering or editing a tenant.
    Pass tenant=<Tenant object> to open in edit mode.
    """

    def __init__(self, parent, user, tenant: Tenant | None = None):
        super().__init__(parent)
        self.user    = user
        self.tenant  = tenant          # None = create mode
        self.editing = tenant is not None
        self.db      = SessionLocal()

        self.title("Edit Tenant" if self.editing else "Register New Tenant")
        self.resizable(True, True)
        self.grab_set()

        self._build_ui()
        self._center(parent)

        if self.editing:
            self._populate(tenant)

    # ── Layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.geometry("620x600")

        # Notebook (tabs)
        self.nb = tb.Notebook(self, bootstyle="primary")
        self.nb.pack(fill=BOTH, expand=YES, padx=16, pady=(16, 8))

        self._tab_personal    = tb.Frame(self.nb, padding=16)
        self._tab_employment  = tb.Frame(self.nb, padding=16)
        self._tab_preferences = tb.Frame(self.nb, padding=16)
        self._tab_references  = tb.Frame(self.nb, padding=16)

        self.nb.add(self._tab_personal,    text="  Personal  ")
        self.nb.add(self._tab_employment,  text="  Employment  ")
        self.nb.add(self._tab_preferences, text="  Preferences  ")
        self.nb.add(self._tab_references,  text="  References  ")

        self._build_personal_tab()
        self._build_employment_tab()
        self._build_preferences_tab()
        self._build_references_tab()

        # Bottom buttons
        btn_row = tb.Frame(self, padding=(16, 0, 16, 16))
        btn_row.pack(fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(
            btn_row,
            text="Save Changes" if self.editing else "Register Tenant",
            bootstyle="success",
            command=self._submit,
        ).pack(side=RIGHT)

    # ── Tab 1: Personal ───────────────────────────────────────────────────
    def _build_personal_tab(self):
        f = self._tab_personal
        self._lbl_field(f, "Full Name *")
        self.v_full_name = tb.Entry(f, font=("Helvetica", 12))
        self.v_full_name.pack(fill=X, pady=(2, 10))

        row = tb.Frame(f)
        row.pack(fill=X, pady=(0, 10))
        left = tb.Frame(row)
        left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right = tb.Frame(row)
        right.pack(side=RIGHT, fill=X, expand=YES)

        self._lbl_field(left, "Email *")
        self.v_email = tb.Entry(left, font=("Helvetica", 12))
        self.v_email.pack(fill=X, pady=(2, 0))

        self._lbl_field(right, "Phone *")
        self.v_phone = tb.Entry(right, font=("Helvetica", 12))
        self.v_phone.pack(fill=X, pady=(2, 0))

        row2 = tb.Frame(f)
        row2.pack(fill=X, pady=(0, 10))
        left2 = tb.Frame(row2)
        left2.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right2 = tb.Frame(row2)
        right2.pack(side=RIGHT, fill=X, expand=YES)

        self._lbl_field(left2, "Date of Birth (DD/MM/YYYY)")
        self.v_dob = tb.Entry(left2, font=("Helvetica", 12))
        self.v_dob.pack(fill=X, pady=(2, 0))

        # NI Number — shown only if user has permission
        if self.user.has_permission("tenant.view_ni") or not self.editing:
            self._lbl_field(right2, "NI Number (stored masked)")
            self.v_ni = tb.Entry(right2, font=("Helvetica", 12))
            self.v_ni.pack(fill=X, pady=(2, 0))
        else:
            self.v_ni = None
            self._lbl_field(right2, "NI Number")
            tb.Label(right2, text="[Restricted]", bootstyle="secondary",
                     font=("Helvetica", 11)).pack(anchor=W, pady=(2, 0))

        self._lbl_field(f, "Emergency Contact Name")
        self.v_ec_name = tb.Entry(f, font=("Helvetica", 12))
        self.v_ec_name.pack(fill=X, pady=(2, 10))

        self._lbl_field(f, "Emergency Contact Phone")
        self.v_ec_phone = tb.Entry(f, font=("Helvetica", 12))
        self.v_ec_phone.pack(fill=X, pady=(2, 0))

    # ── Tab 2: Employment ─────────────────────────────────────────────────
    def _build_employment_tab(self):
        f = self._tab_employment

        self._lbl_field(f, "Occupation")
        self.v_occupation = tb.Entry(f, font=("Helvetica", 12))
        self.v_occupation.pack(fill=X, pady=(2, 10))

        row = tb.Frame(f)
        row.pack(fill=X, pady=(0, 10))
        left = tb.Frame(row)
        left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right = tb.Frame(row)
        right.pack(side=RIGHT, fill=X, expand=YES)

        self._lbl_field(left, "Employer Name")
        self.v_employer = tb.Entry(left, font=("Helvetica", 12))
        self.v_employer.pack(fill=X, pady=(2, 0))

        self._lbl_field(right, "Employer Phone")
        self.v_employer_phone = tb.Entry(right, font=("Helvetica", 12))
        self.v_employer_phone.pack(fill=X, pady=(2, 0))

        self._lbl_field(f, "Annual Income (£)")
        self.v_income = tb.Entry(f, font=("Helvetica", 12))
        self.v_income.pack(fill=X, pady=(2, 0))

    # ── Tab 3: Preferences ────────────────────────────────────────────────
    def _build_preferences_tab(self):
        f = self._tab_preferences

        row = tb.Frame(f)
        row.pack(fill=X, pady=(0, 10))
        left = tb.Frame(row)
        left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right = tb.Frame(row)
        right.pack(side=RIGHT, fill=X, expand=YES)

        self._lbl_field(left, "Preferred Apartment Type")
        self.v_apt_type = tb.StringVar(value="Any")
        tb.Combobox(left, textvariable=self.v_apt_type,
                    values=APARTMENT_TYPE_OPTIONS,
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 0))

        self._lbl_field(right, "Preferred Lease (months)")
        self.v_lease_months = tb.Entry(right, font=("Helvetica", 12))
        self.v_lease_months.pack(fill=X, pady=(2, 0))

        self._lbl_field(f, "Preferred Move-in Date (DD/MM/YYYY)")
        self.v_move_in = tb.Entry(f, font=("Helvetica", 12))
        self.v_move_in.pack(fill=X, pady=(2, 10))

        self._lbl_field(f, "Additional Requirements")
        self.v_requirements = tb.Text(f, font=("Helvetica", 12), height=5)
        self.v_requirements.pack(fill=BOTH, expand=YES, pady=(2, 0))

    # ── Tab 4: References ─────────────────────────────────────────────────
    def _build_references_tab(self):
        f = self._tab_references

        tb.Label(f, text="Up to 2 references. At least one recommended.",
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(0, 12))

        self._ref_widgets = []
        for i in range(2):
            grp = tb.LabelFrame(f, text=f"Reference {i + 1}")
            grp.pack(fill=X, pady=(0, 10))

            row1 = tb.Frame(grp)
            row1.pack(fill=X, pady=(0, 6))
            left = tb.Frame(row1)
            left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
            right = tb.Frame(row1)
            right.pack(side=RIGHT, fill=X, expand=YES)

            self._lbl_field(left, "Full Name")
            name = tb.Entry(left, font=("Helvetica", 11))
            name.pack(fill=X, pady=(2, 0))

            self._lbl_field(right, "Type")
            ref_type_var = tb.StringVar(value=REFERENCE_TYPES[0])
            tb.Combobox(right, textvariable=ref_type_var,
                        values=REFERENCE_TYPES, state="readonly",
                        font=("Helvetica", 11)).pack(fill=X, pady=(2, 0))

            row2 = tb.Frame(grp)
            row2.pack(fill=X, pady=(0, 6))
            left2 = tb.Frame(row2)
            left2.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
            right2 = tb.Frame(row2)
            right2.pack(side=RIGHT, fill=X, expand=YES)

            self._lbl_field(left2, "Phone")
            phone = tb.Entry(left2, font=("Helvetica", 11))
            phone.pack(fill=X, pady=(2, 0))

            self._lbl_field(right2, "Email")
            email = tb.Entry(right2, font=("Helvetica", 11))
            email.pack(fill=X, pady=(2, 0))

            self._lbl_field(grp, "Relation / Notes")
            notes = tb.Entry(grp, font=("Helvetica", 11))
            notes.pack(fill=X, pady=(2, 0))

            self._ref_widgets.append({
                "name": name,
                "ref_type_var": ref_type_var,
                "phone": phone,
                "email": email,
                "notes": notes,
            })

    # ── Helpers ───────────────────────────────────────────────────────────
    def _lbl_field(self, parent, text):
        tb.Label(parent, text=text, font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=W)

    def _parse_date(self, text: str) -> date | None:
        text = text.strip()
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                from datetime import datetime
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _center(self, parent):
        self.update_idletasks()
        w, h = 620, 600
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    # ── Populate (edit mode) ──────────────────────────────────────────────
    def _populate(self, t: Tenant):
        self.v_full_name.insert(0, t.full_name or "")
        self.v_email.insert(0, t.email or "")
        self.v_phone.insert(0, t.phone or "")
        if t.date_of_birth:
            self.v_dob.insert(0, t.date_of_birth.strftime("%d/%m/%Y"))
        self.v_ec_name.insert(0,  t.emergency_contact_name  or "")
        self.v_ec_phone.insert(0, t.emergency_contact_phone or "")
        self.v_occupation.insert(0,    t.occupation    or "")
        self.v_employer.insert(0,      t.employer_name  or "")
        self.v_employer_phone.insert(0,t.employer_phone or "")
        if t.annual_income:
            self.v_income.insert(0, str(t.annual_income))
        if t.preferred_lease_months:
            self.v_lease_months.insert(0, str(t.preferred_lease_months))
        if t.preferred_move_in_date:
            self.v_move_in.insert(0, t.preferred_move_in_date.strftime("%d/%m/%Y"))
        if t.additional_requirements:
            self.v_requirements.insert("1.0", t.additional_requirements)
        if t.preferred_apartment_type:
            self.v_apt_type.set(t.preferred_apartment_type.value)

        # NI shown masked in edit mode for authorised roles
        if self.v_ni and t.ni_number_masked:
            self.v_ni.insert(0, t.ni_number_masked)

    # ── Submit ────────────────────────────────────────────────────────────
    def _submit(self):
        full_name = self.v_full_name.get().strip()
        email     = self.v_email.get().strip()
        phone     = self.v_phone.get().strip()

        if not full_name:
            Messagebox.show_warning("Full name is required.", title="Validation", parent=self)
            self.nb.select(0)
            return
        if not email:
            Messagebox.show_warning("Email is required.", title="Validation", parent=self)
            self.nb.select(0)
            return
        if not phone:
            Messagebox.show_warning("Phone is required.", title="Validation", parent=self)
            self.nb.select(0)
            return

        # Email uniqueness
        exclude_id = self.tenant.id if self.editing else None
        if email_exists(self.db, email, exclude_id=exclude_id):
            Messagebox.show_warning(
                "A tenant with this email already exists.", title="Duplicate", parent=self
            )
            self.nb.select(0)
            return

        dob      = self._parse_date(self.v_dob.get())
        move_in  = self._parse_date(self.v_move_in.get())
        ni_raw   = self.v_ni.get().strip() if self.v_ni else None

        try:
            income = float(self.v_income.get()) if self.v_income.get().strip() else None
        except ValueError:
            income = None

        try:
            lease_months = int(self.v_lease_months.get()) if self.v_lease_months.get().strip() else None
        except ValueError:
            lease_months = None

        apt_type_str = self.v_apt_type.get()
        apt_type = None
        if apt_type_str and apt_type_str != "Any":
            try:
                apt_type = ApartmentType(apt_type_str)
            except ValueError:
                apt_type = None

        # Collect references
        references = []
        for ref in self._ref_widgets:
            name = ref["name"].get().strip()
            if name:
                references.append({
                    "full_name":      name,
                    "reference_type": ref["ref_type_var"].get(),
                    "phone":          ref["phone"].get().strip(),
                    "email":          ref["email"].get().strip(),
                    "notes":          ref["notes"].get().strip(),
                })

        try:
            if self.editing:
                update_tenant(
                    self.db, self.tenant.id,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    occupation=self.v_occupation.get().strip() or None,
                    employer_name=self.v_employer.get().strip() or None,
                    employer_phone=self.v_employer_phone.get().strip() or None,
                    annual_income=income,
                    emergency_contact_name=self.v_ec_name.get().strip() or None,
                    emergency_contact_phone=self.v_ec_phone.get().strip() or None,
                    additional_requirements=self.v_requirements.get("1.0", "end").strip() or None,
                )
                Messagebox.show_info("Tenant updated successfully!", title="Success", parent=self)
            else:
                register_tenant(
                    self.db,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    date_of_birth=dob,
                    ni_number=ni_raw,
                    occupation=self.v_occupation.get().strip() or None,
                    employer_name=self.v_employer.get().strip() or None,
                    employer_phone=self.v_employer_phone.get().strip() or None,
                    annual_income=income,
                    emergency_contact_name=self.v_ec_name.get().strip() or None,
                    emergency_contact_phone=self.v_ec_phone.get().strip() or None,
                    preferred_apartment_type=apt_type,
                    preferred_move_in_date=move_in,
                    preferred_lease_months=lease_months,
                    additional_requirements=self.v_requirements.get("1.0", "end").strip() or None,
                    references=references,
                )
                Messagebox.show_info("Tenant registered successfully!", title="Success", parent=self)

            self.destroy()

        except Exception as exc:
            self.db.rollback()
            Messagebox.show_error(str(exc), title="Database Error", parent=self)