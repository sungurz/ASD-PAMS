# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/city_management_page.py
================================
Allows Manager to add new cities — expanding the business.
Accessible from Settings page for manager role only.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import City


class CityManagementPage(tb.Toplevel):

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self.title("City Management — Expand Business")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._load()
        self._center(parent)

    def destroy(self):
        try:
            self.db.close()
        except Exception:
            pass
        super().destroy()

    def _build_ui(self):
        self.geometry("560x500")

        btn_row = tb.Frame(self, padding=(20, 0, 20, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Close", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT)
        tb.Button(btn_row, text="＋  Add New City", bootstyle="success",
                  command=self._add_city).pack(side=RIGHT, padx=(0, 8))
        tb.Button(btn_row, text="⊘  Deactivate Selected", bootstyle="danger",
                  command=self._toggle_city).pack(side=LEFT)

        f = tb.Frame(self, padding=(20, 16, 20, 8))
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="City Management",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 4))
        tb.Label(f,
                 text="As Manager you can expand Paragon's business by adding new cities.",
                 font=("Helvetica", 10), bootstyle="secondary",
                 wraplength=500, justify=LEFT).pack(anchor=W, pady=(0, 16))

        tbl = tb.Frame(f)
        tbl.pack(fill=BOTH, expand=YES)

        cols = ("id", "name", "status")
        self.tree = tb.Treeview(tbl, columns=cols, show="headings",
                                bootstyle="dark", selectmode="browse")
        self.tree.heading("id",     text="ID",     anchor=CENTER)
        self.tree.heading("name",   text="City",   anchor=W)
        self.tree.heading("status", text="Status", anchor=CENTER)
        self.tree.column("id",     width=50,  anchor=CENTER)
        self.tree.column("name",   width=300, anchor=W)
        self.tree.column("status", width=100, anchor=CENTER)

        self.tree.tag_configure("active",   foreground="#2ECC71")
        self.tree.tag_configure("inactive", foreground="#7F8C8D")

        sb = tb.Scrollbar(tbl, orient=VERTICAL, command=self.tree.yview,
                          bootstyle="round-dark")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

    def _load(self):
        self.db.expire_all()
        for row in self.tree.get_children():
            self.tree.delete(row)

        cities = self.db.query(City).order_by(City.name).all()
        for c in cities:
            tag = "active" if c.is_active else "inactive"
            self.tree.insert("", END, tags=(tag,), values=(
                c.id, c.name,
                "Active" if c.is_active else "Inactive"
            ))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _add_city(self):
        dlg = _AddCityDialog(self, db=self.db)
        self.wait_window(dlg)
        self._load()

    def _toggle_city(self):
        cid = self._selected_id()
        if not cid:
            Messagebox.show_warning("Please select a city.", title="No Selection")
            return

        city = self.db.query(City).filter(City.id == cid).first()
        if not city:
            return

        action = "reactivate" if not city.is_active else "deactivate"
        confirm = Messagebox.yesno(
            f"{action.title()} {city.name}?",
            title="Confirm"
        )
        if confirm == "Yes":
            city.is_active = not city.is_active
            self.db.commit()
            self._load()

    def _center(self, parent):
        self.update_idletasks()
        w, h = 560, 500
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")


class _AddCityDialog(tb.Toplevel):

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.title("Add New City")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("380x220")

        btn_row = tb.Frame(self, padding=(20, 0, 20, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Add City", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=20)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Add New City",
                 font=("Georgia", 15, "bold")).pack(anchor=W, pady=(0, 16))

        def lbl(t):
            tb.Label(f, text=t, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        lbl("City Name *  (e.g. Birmingham)")
        self.v_name = tb.Entry(f, font=("Helvetica", 12))
        self.v_name.pack(fill=X, pady=(2, 0))
        self.v_name.focus()

    def _center(self, parent):
        self.update_idletasks()
        w, h = 380, 220
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        name = self.v_name.get().strip()
        if not name:
            Messagebox.show_warning("City name is required.", title="Validation", parent=self)
            return

        existing = self.db.query(City).filter(City.name == name).first()
        if existing:
            Messagebox.show_warning(f"{name} already exists.", title="Duplicate", parent=self)
            return

        city = City(name=name, is_active=True)
        self.db.add(city)
        self.db.commit()

        parent_win = self.master
        self.destroy()
        Messagebox.show_info(
            f"{name} added successfully!\n\n"
            f"Staff can now be assigned to {name} and properties can be created there.",
            title="City Added",
            parent=parent_win,
        )