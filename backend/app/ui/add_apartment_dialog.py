"""
Two dialogs:
  AddApartmentDialog  — register or edit a single apartment unit.
  AddPropertyDialog   — register a new property (building) in a city.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from decimal import Decimal

from app.db.database import SessionLocal
from app.db.models import Apartment, Property, City, ApartmentType, ApartmentStatus


APARTMENT_TYPES = [
    ("Studio",          "studio"),
    ("1 Bedroom",       "one_bed"),
    ("2 Bedroom",       "two_bed"),
    ("3 Bedroom",       "three_bed"),
    ("4 Bedroom",       "four_bed"),
]

APARTMENT_STATUSES = [
    ("Available",   "available"),
    ("Occupied",    "occupied"),
    ("Maintenance", "maintenance"),
    ("Inactive",    "inactive"),
]


class AddApartmentDialog(tb.Toplevel):
    """Modal dialog to add or edit an apartment unit."""

    def __init__(self, parent, user, apartment: Apartment | None = None):
        super().__init__(parent)
        self.user      = user
        self.apartment = apartment
        self.editing   = apartment is not None
        self.db        = SessionLocal()

        self.title("Edit Apartment" if self.editing else "Add New Apartment")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)
        if self.editing:
            self._populate(apartment)

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.geometry("460x520")
        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Edit Apartment" if self.editing else "Add New Apartment",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 16))

        # Property (building) selector
        self._lbl(f, "Property / Building *")
        properties = self._load_properties()
        self.v_property = tb.StringVar()
        self._property_map: dict[str, int] = {}
        for p in properties:
            label = f"{p.name} ({p.city.name if p.city else '?'})"
            self._property_map[label] = p.id
        self._prop_combo = tb.Combobox(
            f, textvariable=self.v_property,
            values=list(self._property_map.keys()),
            state="readonly", font=("Helvetica", 12),
        )
        self._prop_combo.pack(fill=X, pady=(2, 12))

        # Unit number and floor side by side
        row = tb.Frame(f)
        row.pack(fill=X, pady=(0, 12))
        left = tb.Frame(row)
        left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right = tb.Frame(row)
        right.pack(side=RIGHT, fill=X, expand=YES)

        self._lbl(left, "Unit Number *")
        self.v_unit = tb.Entry(left, font=("Helvetica", 12))
        self.v_unit.pack(fill=X, pady=(2, 0))

        self._lbl(right, "Floor")
        self.v_floor = tb.Entry(right, font=("Helvetica", 12))
        self.v_floor.pack(fill=X, pady=(2, 0))

        # Type and rooms side by side
        row2 = tb.Frame(f)
        row2.pack(fill=X, pady=(0, 12))
        left2 = tb.Frame(row2)
        left2.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right2 = tb.Frame(row2)
        right2.pack(side=RIGHT, fill=X, expand=YES)

        self._lbl(left2, "Apartment Type *")
        self.v_type = tb.StringVar(value=APARTMENT_TYPES[0][0])
        tb.Combobox(left2, textvariable=self.v_type,
                    values=[t[0] for t in APARTMENT_TYPES],
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 0))

        self._lbl(right2, "Number of Rooms *")
        self.v_rooms = tb.Entry(right2, font=("Helvetica", 12))
        self.v_rooms.pack(fill=X, pady=(2, 0))

        # Monthly rent
        self._lbl(f, "Monthly Rent (£) *")
        self.v_rent = tb.Entry(f, font=("Helvetica", 12))
        self.v_rent.pack(fill=X, pady=(2, 12))

        # Status (edit only / admin)
        self._lbl(f, "Status")
        self.v_status = tb.StringVar(value="Available")
        tb.Combobox(f, textvariable=self.v_status,
                    values=[s[0] for s in APARTMENT_STATUSES],
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 12))

        # Description
        self._lbl(f, "Description (optional)")
        self.v_desc = tb.Entry(f, font=("Helvetica", 12))
        self.v_desc.pack(fill=X, pady=(2, 0))

        # Buttons
        btn_row = tb.Frame(f)
        btn_row.pack(fill=X, pady=(20, 0))
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row,
                  text="Save Changes" if self.editing else "Add Apartment",
                  bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

    # ── Helpers ───────────────────────────────────────────────────────────
    def _lbl(self, parent, text):
        tb.Label(parent, text=text, font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=W)

    def _load_properties(self) -> list[Property]:
        from sqlalchemy.orm import joinedload
        return (
            self.db.query(Property)
            .options(joinedload(Property.city))
            .filter(Property.is_active == True)
            .order_by(Property.name)
            .all()
        )

    def _get_type_value(self, label: str) -> str:
        for lbl, val in APARTMENT_TYPES:
            if lbl == label:
                return val
        return "studio"

    def _get_status_value(self, label: str) -> str:
        for lbl, val in APARTMENT_STATUSES:
            if lbl == label:
                return val
        return "available"

    def _center(self, parent):
        self.update_idletasks()
        w, h = 460, 520
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    # ── Populate (edit mode) ──────────────────────────────────────────────
    def _populate(self, apt: Apartment):
        # Set property
        for label, pid in self._property_map.items():
            if pid == apt.property_id:
                self.v_property.set(label)
                break
        self.v_unit.insert(0, apt.unit_number or "")
        if apt.floor is not None:
            self.v_floor.insert(0, str(apt.floor))
        if apt.room_count:
            self.v_rooms.insert(0, str(apt.room_count))
        if apt.monthly_rent:
            self.v_rent.insert(0, str(apt.monthly_rent))
        if apt.description:
            self.v_desc.insert(0, apt.description)
        # Type
        for lbl, val in APARTMENT_TYPES:
            if apt.apartment_type and apt.apartment_type.value == val:
                self.v_type.set(lbl)
                break
        # Status
        for lbl, val in APARTMENT_STATUSES:
            if apt.status and apt.status.value == val:
                self.v_status.set(lbl)
                break

    # ── Submit ────────────────────────────────────────────────────────────
    def _submit(self):
        prop_label = self.v_property.get()
        unit       = self.v_unit.get().strip()
        floor_str  = self.v_floor.get().strip()
        rooms_str  = self.v_rooms.get().strip()
        rent_str   = self.v_rent.get().strip()
        type_lbl   = self.v_type.get()
        status_lbl = self.v_status.get()
        desc       = self.v_desc.get().strip()

        if not prop_label or prop_label not in self._property_map:
            Messagebox.show_warning("Please select a property.", title="Validation", parent=self)
            return
        if not unit:
            Messagebox.show_warning("Unit number is required.", title="Validation", parent=self)
            return
        if not rooms_str.isdigit():
            Messagebox.show_warning("Number of rooms must be a whole number.", title="Validation", parent=self)
            return
        if not rent_str:
            Messagebox.show_warning("Monthly rent is required.", title="Validation", parent=self)
            return
        try:
            rent = Decimal(rent_str)
        except Exception:
            Messagebox.show_warning("Monthly rent must be a valid number.", title="Validation", parent=self)
            return

        property_id  = self._property_map[prop_label]
        type_value   = self._get_type_value(type_lbl)
        status_value = self._get_status_value(status_lbl)
        floor        = int(floor_str) if floor_str.lstrip("-").isdigit() else None

        try:
            if self.editing:
                apt = self.db.query(Apartment).filter(Apartment.id == self.apartment.id).first()
                apt.property_id    = property_id
                apt.unit_number    = unit
                apt.floor          = floor
                apt.room_count     = int(rooms_str)
                apt.monthly_rent   = rent
                apt.apartment_type = ApartmentType(type_value)
                apt.status         = ApartmentStatus(status_value)
                apt.description    = desc or None
                self.db.commit()
                Messagebox.show_info("Apartment updated!", title="Success", parent=self)
                self.destroy()
            else:
                new_apt = Apartment(
                    property_id    = property_id,
                    unit_number    = unit,
                    floor          = floor,
                    room_count     = int(rooms_str),
                    monthly_rent   = rent,
                    apartment_type = ApartmentType(type_value),
                    status         = ApartmentStatus(status_value),
                    description    = desc or None,
                )
                self.db.add(new_apt)
                self.db.commit()
                Messagebox.show_info("Apartment added!", title="Success", parent=self)
            self.destroy()
        except Exception as exc:
            self.db.rollback()
            Messagebox.show_error(str(exc), title="Database Error", parent=self)


# ─────────────────────────────────────────────────────────────────────────────

class AddPropertyDialog(tb.Toplevel):
    """Modal dialog to register a new property (building) in a city."""

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()

        self.title("Add New Property")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("420x420")
        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Add New Property",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 16))

        def lbl(text):
            tb.Label(f, text=text, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        lbl("City *")
        cities = self.db.query(City).filter(City.is_active == True).order_by(City.name).all()
        self._city_map = {c.name: c.id for c in cities}
        self.v_city = tb.StringVar()
        tb.Combobox(f, textvariable=self.v_city,
                    values=list(self._city_map.keys()),
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 12))

        lbl("Property Name *  (e.g. Paragon Bristol Block A)")
        self.v_name = tb.Entry(f, font=("Helvetica", 12))
        self.v_name.pack(fill=X, pady=(2, 12))

        lbl("Address *")
        self.v_address = tb.Entry(f, font=("Helvetica", 12))
        self.v_address.pack(fill=X, pady=(2, 12))

        lbl("Postcode")
        self.v_postcode = tb.Entry(f, font=("Helvetica", 12))
        self.v_postcode.pack(fill=X, pady=(2, 0))

        btn_row = tb.Frame(f)
        btn_row.pack(fill=X, pady=(20, 0))
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Add Property", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

    def _center(self, parent):
        self.update_idletasks()
        w, h = 420, 420
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        city_name = self.v_city.get()
        name      = self.v_name.get().strip()
        address   = self.v_address.get().strip()
        postcode  = self.v_postcode.get().strip()

        if not city_name or city_name not in self._city_map:
            Messagebox.show_warning("Please select a city.", title="Validation", parent=self)
            return
        if not name:
            Messagebox.show_warning("Property name is required.", title="Validation", parent=self)
            return
        if not address:
            Messagebox.show_warning("Address is required.", title="Validation", parent=self)
            return

        try:
            prop = Property(
                city_id=self._city_map[city_name],
                name=name,
                address=address,
                postcode=postcode or None,
                is_active=True,
            )
            self.db.add(prop)
            self.db.commit()
            Messagebox.show_info(f"Property '{name}' added!", title="Success", parent=self)
            self.destroy()
        except Exception as exc:
            self.db.rollback()
            Messagebox.show_error(str(exc), title="Database Error", parent=self)