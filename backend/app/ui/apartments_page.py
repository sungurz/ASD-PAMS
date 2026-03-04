"""
app/ui/apartments_page.py
==========================
Apartment inventory management page.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import Apartment, Property, City, ApartmentStatus
from sqlalchemy.orm import joinedload


STATUS_STYLE = {
    ApartmentStatus.AVAILABLE:   ("Available",   "#2ECC71"),
    ApartmentStatus.OCCUPIED:    ("Occupied",     "#3498DB"),
    ApartmentStatus.MAINTENANCE: ("Maintenance",  "#E67E22"),
    ApartmentStatus.INACTIVE:    ("Inactive",     "#7F8C8D"),
}


class ApartmentsPage(tb.Frame):
    """Apartment inventory page."""

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self._selected_city = tb.StringVar(value="All Cities")
        self._build_ui()
        self.load_apartments()

    def destroy(self):
        try:
            self.db.close()
        except Exception:
            pass
        super().destroy()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        header = tb.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill=X)

        tb.Label(header, text="Apartments",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)

        btn_bar = tb.Frame(header)
        btn_bar.pack(side=RIGHT)

        if self.user.has_permission("apartment.create"):
            tb.Button(btn_bar, text="＋  Add Apartment",
                      bootstyle="success", padding=(10, 6),
                      command=self._open_add_dialog).pack(side=LEFT, padx=(0, 6))
            tb.Button(btn_bar, text="🏢  Add Property",
                      bootstyle="secondary", padding=(10, 6),
                      command=self._open_add_property_dialog).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("apartment.update"):
            tb.Button(btn_bar, text="✎  Edit",
                      bootstyle="secondary", padding=(10, 6),
                      command=self._edit_selected).pack(side=LEFT, padx=(0, 6))

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=20)

        filter_bar = tb.Frame(self, padding=(20, 10, 20, 4))
        filter_bar.pack(fill=X)

        tb.Label(filter_bar, text="City:", font=("Helvetica", 11)).pack(side=LEFT)
        cities = self._load_city_names()
        self._city_combo = tb.Combobox(
            filter_bar, textvariable=self._selected_city,
            values=["All Cities"] + cities,
            state="readonly", font=("Helvetica", 11), width=18,
        )
        self._city_combo.pack(side=LEFT, padx=(6, 16))
        self._city_combo.bind("<<ComboboxSelected>>", lambda _: self.load_apartments())

        self._status_var = tb.StringVar(value="All")
        tb.Label(filter_bar, text="Status:", font=("Helvetica", 11)).pack(side=LEFT)
        tb.Combobox(
            filter_bar, textvariable=self._status_var,
            values=["All", "Available", "Occupied", "Maintenance", "Inactive"],
            state="readonly", font=("Helvetica", 11), width=14,
        ).pack(side=LEFT, padx=(6, 0))
        self._status_var.trace_add("write", lambda *_: self.load_apartments())

        table_frame = tb.Frame(self, padding=(20, 8, 20, 0))
        table_frame.pack(fill=BOTH, expand=YES)

        cols = ("id", "property", "city", "unit", "floor", "type", "status", "rooms", "rent")
        self.tree = tb.Treeview(
            table_frame, columns=cols, show="headings",
            bootstyle="dark", selectmode="browse",
        )

        col_cfg = [
            ("id",       "ID",       50,  CENTER),
            ("property", "Property", 180, W),
            ("city",     "City",     100, CENTER),
            ("unit",     "Unit",     70,  CENTER),
            ("floor",    "Floor",    55,  CENTER),
            ("type",     "Type",     100, CENTER),
            ("status",   "Status",   100, CENTER),
            ("rooms",    "Rooms",    55,  CENTER),
            ("rent",     "Rent/mo",  90,  CENTER),
        ]
        for col_id, heading, width, anchor in col_cfg:
            self.tree.heading(col_id, text=heading, anchor=anchor)
            self.tree.column(col_id, width=width, anchor=anchor, minwidth=40)

        self.tree.tag_configure("available",   foreground="#2ECC71")
        self.tree.tag_configure("occupied",    foreground="#3498DB")
        self.tree.tag_configure("maintenance", foreground="#E67E22")
        self.tree.tag_configure("inactive",    foreground="#7F8C8D")

        scrollbar = tb.Scrollbar(table_frame, orient=VERTICAL,
                                 command=self.tree.yview, bootstyle="round-dark")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        self._count_var = tb.StringVar()
        tb.Label(self, textvariable=self._count_var,
                 font=("Helvetica", 10), bootstyle="secondary").pack(
            anchor=E, padx=24, pady=(4, 10)
        )

    # ── Data ──────────────────────────────────────────────────────────────
    def _load_city_names(self) -> list[str]:
        cities = self.db.query(City).filter(City.is_active == True).order_by(City.name).all()
        return [c.name for c in cities]

    def load_apartments(self, *_):
        self.db.expire_all()
        for row in self.tree.get_children():
            self.tree.delete(row)

        q = (
            self.db.query(Apartment, Property, City)
            .join(Property, Apartment.property_id == Property.id)
            .join(City, Property.city_id == City.id)
        )

        city_filter = self._selected_city.get()
        if city_filter != "All Cities":
            q = q.filter(City.name == city_filter)

        status_filter = self._status_var.get()
        if status_filter != "All":
            status_map = {
                "Available":   ApartmentStatus.AVAILABLE,
                "Occupied":    ApartmentStatus.OCCUPIED,
                "Maintenance": ApartmentStatus.MAINTENANCE,
                "Inactive":    ApartmentStatus.INACTIVE,
            }
            q = q.filter(Apartment.status == status_map[status_filter])

        results = q.order_by(Property.name, Apartment.unit_number).all()

        for apt, prop, city in results:
            status_label, _ = STATUS_STYLE.get(apt.status, ("Unknown", "#FFFFFF"))
            tag      = apt.status.value if apt.status else "inactive"
            apt_type = apt.apartment_type.value.replace("_", " ").title() if apt.apartment_type else "—"
            rent     = f"£{apt.monthly_rent:,.2f}" if apt.monthly_rent else "—"

            self.tree.insert("", END, tags=(tag,), values=(
                apt.id,
                prop.name,
                city.name,
                apt.unit_number,
                apt.floor if apt.floor is not None else "—",
                apt_type,
                status_label,
                apt.room_count,
                rent,
            ))

        self._count_var.set(f"{len(results)} apartment(s)")

    def _selected_apt_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    # ── Actions ───────────────────────────────────────────────────────────
    def _open_add_dialog(self):
        from app.ui.add_apartment_dialog import AddApartmentDialog
        dlg = AddApartmentDialog(self, user=self.user)
        self.wait_window(dlg)
        self.load_apartments()

    def _open_add_property_dialog(self):
        from app.ui.add_apartment_dialog import AddPropertyDialog
        dlg = AddPropertyDialog(self, user=self.user)
        self.wait_window(dlg)
        self.load_apartments()

    def _edit_selected(self):
        apt_id = self._selected_apt_id()
        if apt_id is None:
            Messagebox.show_warning("Please select an apartment to edit.", title="No Selection")
            return
        self.db.expire_all()
        apt = self.db.query(Apartment).filter(Apartment.id == apt_id).first()
        if not apt:
            return
        from app.ui.add_apartment_dialog import AddApartmentDialog
        dlg = AddApartmentDialog(self, user=self.user, apartment=apt)
        self.wait_window(dlg)
        self.load_apartments()