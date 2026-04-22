# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/add_user_dialog.py
=========================
Modal dialog for creating or editing a staff user account.

Sprint 2 changes:
  - City assignment dropdown (loads live from DB).
  - All 6 correct role names with friendly display labels.
  - Roles that outrank the current user's role are hidden
    (a location_admin cannot create a manager).
  - result_role stores the raw enum value (e.g. "front_desk")
    so users_page can query Role by name directly.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import User, Role, City, RoleName
from app.auth.security import hash_password


# Friendly display labels for each role value
ROLE_LABELS = {
    "manager":           "Manager",
    "location_admin":    "Location Admin",
    "front_desk":        "Front Desk",
    "finance_manager":   "Finance Manager",
    "maintenance_staff": "Maintenance Staff",
    "tenant":            "Tenant",
}

# Which roles a given role can create
# (you can only create roles at or below your own level)
CREATABLE_BY = {
    "manager":           ["manager", "location_admin", "front_desk",
                          "finance_manager", "maintenance_staff", "tenant"],
    "location_admin":    ["front_desk", "finance_manager", "maintenance_staff", "tenant"],
    "front_desk":        [],
    "finance_manager":   [],
    "maintenance_staff": [],
    "tenant":            [],
}


class AddUserDialog(tb.Toplevel):
    """
    Modal dialog — create or edit a user account.

    After wait_window() returns check:
        dialog.submitted       — True if confirmed
        dialog.result_*        — values entered
    """

    def __init__(self, parent, editing: bool = False, user=None):
        super().__init__(parent)
        self.editing  = editing
        self.actor    = user          # _UserContext of the logged-in staff member
        self.db       = SessionLocal()

        self.submitted        = False
        self.result_username  = ""
        self.result_password  = ""
        self.result_role      = ""
        self.result_full_name = ""
        self.result_city      = ""

        self.title("Edit User" if editing else "Add New User")
        self.resizable(False, False)
        self.grab_set()

        self._build_ui()
        self._center(parent)

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        frame = tb.Frame(self, padding=28)
        frame.pack(fill=BOTH, expand=YES)

        tb.Label(
            frame,
            text="Edit User" if self.editing else "Add New User",
            font=("Georgia", 17, "bold"),
        ).pack(anchor=W, pady=(0, 18))

        # Username
        tb.Label(frame, text="Username", font=("Helvetica", 11),
                 bootstyle="secondary").pack(anchor=W)
        self.username_input = tb.Entry(frame, font=("Helvetica", 12), width=36)
        self.username_input.pack(fill=X, pady=(2, 12))

        # Full Name
        tb.Label(frame, text="Full Name", font=("Helvetica", 11),
                 bootstyle="secondary").pack(anchor=W)
        self.full_name_input = tb.Entry(frame, font=("Helvetica", 12), width=36)
        self.full_name_input.pack(fill=X, pady=(2, 12))

        # Password
        tb.Label(frame, text="Password", font=("Helvetica", 11),
                 bootstyle="secondary").pack(anchor=W)
        placeholder = "Leave blank to keep existing" if self.editing else "Enter password"
        self.password_input = tb.Entry(
            frame, font=("Helvetica", 12), width=36, show="•"
        )
        self.password_input.pack(fill=X, pady=(2, 12))

        # Role
        tb.Label(frame, text="Role", font=("Helvetica", 11),
                 bootstyle="secondary").pack(anchor=W)

        allowed_roles = self._get_allowed_roles()
        self.role_var = tb.StringVar(value=allowed_roles[0] if allowed_roles else "front_desk")

        self.role_input = tb.Combobox(
            frame, textvariable=self.role_var,
            values=allowed_roles,
            state="readonly", font=("Helvetica", 12), width=34,
        )
        self.role_input.pack(fill=X, pady=(2, 12))

        # City
        tb.Label(frame, text="City (leave as All Cities for cross-city roles)",
                 font=("Helvetica", 11), bootstyle="secondary").pack(anchor=W)

        cities = self._load_cities()
        self.city_var = tb.StringVar(value="All Cities")
        self.city_input = tb.Combobox(
            frame, textvariable=self.city_var,
            values=cities,
            state="readonly", font=("Helvetica", 12), width=34,
        )
        self.city_input.pack(fill=X, pady=(2, 18))

        # Submit
        tb.Button(
            frame,
            text="Save Changes" if self.editing else "Create User",
            bootstyle="primary",
            padding=(0, 9),
            command=self._submit,
        ).pack(fill=X)

    # ── Helpers ───────────────────────────────────────────────────────────
    def _get_allowed_roles(self) -> list[str]:
        """Return role values this actor is allowed to assign."""
        if self.actor is None:
            return list(ROLE_LABELS.keys())
        allowed_values = CREATABLE_BY.get(self.actor.role_value, [])
        # Return as friendly labels for display but store value on select
        return [ROLE_LABELS.get(v, v) for v in allowed_values] or list(ROLE_LABELS.values())

    def _get_role_value(self, label: str) -> str:
        """Convert a friendly display label back to the enum value."""
        reverse = {v: k for k, v in ROLE_LABELS.items()}
        return reverse.get(label, label)

    def _load_cities(self) -> list[str]:
        cities = self.db.query(City).filter(City.is_active == True).order_by(City.name).all()
        return ["All Cities"] + [c.name for c in cities]

    def _center(self, parent):
        self.update_idletasks()
        w, h = 420, 520
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    # ── Submit ────────────────────────────────────────────────────────────
    def _submit(self):
        username  = self.username_input.get().strip()
        password  = self.password_input.get()
        role_label = self.role_var.get()
        role_value = self._get_role_value(role_label)
        full_name  = self.full_name_input.get().strip()
        city       = self.city_var.get()

        # Validation
        if not username:
            Messagebox.show_warning("Username is required.", title="Validation Error", parent=self)
            return
        if not full_name:
            Messagebox.show_warning("Full name is required.", title="Validation Error", parent=self)
            return
        if not password and not self.editing:
            Messagebox.show_warning("Password is required.", title="Validation Error", parent=self)
            return

        # Duplicate check (create only)
        exists = self.db.query(User).filter(User.username == username).first()
        if exists and not self.editing:
            Messagebox.show_warning(
                "That username already exists.", title="Duplicate Username", parent=self
            )
            return

        # CREATE
        if not self.editing:
            role_record = (
                self.db.query(Role)
                .filter(Role.name == role_value)
                .first()
            )
            city_record = None
            if city and city != "All Cities":
                city_record = self.db.query(City).filter(City.name == city).first()

            if not role_record:
                Messagebox.show_warning(
                    f"Role '{role_value}' not found in database.",
                    title="Error", parent=self
                )
                return

            new_user = User(
                username=username,
                password_hash=hash_password(password),
                role_id=role_record.id,
                full_name=full_name,
                city_id=city_record.id if city_record else None,
                is_active=True,
            )
            self.db.add(new_user)
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                Messagebox.show_warning("Username already exists!", title="Error", parent=self)
                return
            Messagebox.show_info("User created successfully!", title="Success", parent=self)

        # Store results (used by users_page in edit mode)
        self.result_username  = username
        self.result_password  = password
        self.result_role      = role_value
        self.result_full_name = full_name
        self.result_city      = city
        self.submitted        = True
        self.destroy()