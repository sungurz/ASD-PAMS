# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/users_page.py
====================
Staff account management page.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import User, Role, City
from app.auth.security import hash_password
from sqlalchemy.orm import joinedload


class UsersPage(tb.Frame):
    """Users management page."""

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self._build_ui()
        self.load_users()

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


    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        header = tb.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill=X)

        tb.Label(header, text="Users",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)

        btn_bar = tb.Frame(header)
        btn_bar.pack(side=RIGHT)

        if self.user.has_permission("user.create"):
            tb.Button(btn_bar, text="＋  Add User", bootstyle="success",
                      padding=(10, 6),
                      command=self._open_add_dialog).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("user.update"):
            tb.Button(btn_bar, text="✎  Edit", bootstyle="secondary",
                      padding=(10, 6),
                      command=self._edit_selected).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("user.deactivate"):
            tb.Button(btn_bar, text="🚫  Deactivate", bootstyle="danger",
                      padding=(10, 6),
                      command=self._delete_selected).pack(side=LEFT, padx=(0, 6))
            tb.Button(btn_bar, text="♻  Reactivate", bootstyle="success",
                      padding=(10, 6),
                      command=self._reactivate_selected).pack(side=LEFT)

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=20)

        # Filter bar
        filter_bar = tb.Frame(self, padding=(20, 8, 20, 0))
        filter_bar.pack(fill=X)

        tb.Label(filter_bar, text="Status:", font=("Helvetica", 11)).pack(side=LEFT)
        self._status_filter = tb.StringVar(value="Active")
        tb.Combobox(filter_bar, textvariable=self._status_filter,
                    values=["Active", "Inactive", "All"],
                    state="readonly", font=("Helvetica", 11), width=10).pack(side=LEFT, padx=(6, 16))
        self._status_filter.trace_add("write", lambda *_: self.load_users())

        tb.Label(filter_bar, text="Role:", font=("Helvetica", 11)).pack(side=LEFT)
        self._role_filter = tb.StringVar(value="All")
        tb.Combobox(filter_bar, textvariable=self._role_filter,
                    values=["All", "Manager", "Location Admin", "Finance Manager",
                            "Front Desk", "Maintenance Staff", "Tenant"],
                    state="readonly", font=("Helvetica", 11), width=16).pack(side=LEFT, padx=(6, 0))
        self._role_filter.trace_add("write", lambda *_: self.load_users())

        table_frame = tb.Frame(self, padding=(20, 8, 20, 0))
        table_frame.pack(fill=BOTH, expand=YES)

        cols = ("id", "username", "full_name", "role", "city", "active")
        self.tree = tb.Treeview(
            table_frame, columns=cols, show="headings",
            bootstyle="dark", selectmode="browse",
        )

        col_cfg = [
            ("id",        "ID",        50,  CENTER),
            ("username",  "Username",  160, W),
            ("full_name", "Full Name", 180, W),
            ("role",      "Role",      160, W),
            ("city",      "City",      120, CENTER),
            ("active",    "Status",    80,  CENTER),
        ]
        for col_id, heading, width, anchor in col_cfg:
            self.tree.heading(col_id, text=heading, anchor=anchor)
            self.tree.column(col_id, width=width, anchor=anchor, minwidth=40)

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
    def load_users(self):
        try:
            for row in self.tree.get_children():
                self.tree.delete(row)
        except Exception:
            return
        self._refresh_db()

        q = self.db.query(User).options(joinedload(User.role), joinedload(User.city))

        # City scoping — location admins only see users in their city
        city_id = getattr(self.user, "city_id", None)
        if city_id:
            q = q.filter((User.city_id == city_id) | (User.id == self.user.id))

        status_filter = self._status_filter.get()
        if status_filter == "Active":
            q = q.filter(User.is_active == True)
        elif status_filter == "Inactive":
            q = q.filter(User.is_active == False)

        role_filter = self._role_filter.get()
        if role_filter != "All":
            role_map = {
                "Manager":            "manager",
                "Location Admin":     "location_admin",
                "Finance Manager":    "finance_manager",
                "Front Desk":         "front_desk",
                "Maintenance Staff":  "maintenance_staff",
                "Tenant":             "tenant",
            }
            from app.db.models import RoleName
            role_val = role_map.get(role_filter)
            if role_val:
                from app.db.models import Role as _Role
                role_obj = self.db.query(_Role).filter(
                    _Role.name == RoleName(role_val)
                ).first()
                if role_obj:
                    q = q.filter(User.role_id == role_obj.id)

        users = q.order_by(User.is_active.desc(), User.full_name).all()

        # Tag colours
        self.tree.tag_configure("active",   foreground="#2ECC71")
        self.tree.tag_configure("inactive", foreground="#7F8C8D")

        for u in users:
            role_display = (
                u.role.name.value.replace("_", " ").title()
                if u.role else "—"
            )
            city_display = u.city.name if u.city else "All Cities"
            status       = "Active" if u.is_active else "Inactive"
            tag          = "active" if u.is_active else "inactive"

            self.tree.insert("", END, tags=(tag,), values=(
                u.id,
                u.username,
                u.full_name or "—",
                role_display,
                city_display,
                status,
            ))

        self._count_var.set(f"{len(users)} user(s)")

    def _selected_user_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    # ── Dialogs ───────────────────────────────────────────────────────────
    def _open_add_dialog(self):
        from app.ui.add_user_dialog import AddUserDialog
        dlg = AddUserDialog(self, user=self.user)
        self.wait_window(dlg)
        self.load_users()

    def _edit_selected(self):
        from app.ui.add_user_dialog import AddUserDialog

        uid = self._selected_user_id()
        if uid is None:
            Messagebox.show_warning("Please select a user to edit.", title="No Selection")
            return

        self._refresh_db()
        user = (
            self.db.query(User)
            .options(joinedload(User.role), joinedload(User.city))
            .filter(User.id == uid)
            .first()
        )
        if not user:
            return

        dlg = AddUserDialog(self, editing=True, user=self.user)
        dlg.username_input.insert(0, user.username)
        dlg.full_name_input.insert(0, user.full_name or "")
        dlg.role_var.set(user.role.name.value if user.role else "front_desk")
        if user.city:
            dlg.city_var.set(user.city.name)
        self.wait_window(dlg)

        if not dlg.submitted:
            return

        existing = (
            self.db.query(User)
            .filter(User.username == dlg.result_username, User.id != user.id)
            .first()
        )
        if existing:
            Messagebox.show_warning("That username is already taken.", title="Duplicate")
            return

        try:
            role_record = (
                self.db.query(Role)
                .filter(Role.name == dlg.result_role)
                .first()
            )
            city_record = None
            if dlg.result_city and dlg.result_city != "All Cities":
                city_record = (
                    self.db.query(City)
                    .filter(City.name == dlg.result_city)
                    .first()
                )

            user.username  = dlg.result_username
            user.full_name = dlg.result_full_name
            user.role_id   = role_record.id if role_record else user.role_id
            user.city_id   = city_record.id if city_record else None

            if dlg.result_password:
                user.password_hash = hash_password(dlg.result_password)

            self.db.commit()
            Messagebox.show_info("User updated successfully!", title="Success")

        except Exception as exc:
            self.db.rollback()
            Messagebox.show_error(str(exc), title="Database Error")

        self.load_users()

    def _reactivate_selected(self):
        uid = self._selected_user_id()
        if uid is None:
            Messagebox.show_warning("Please select a user to reactivate.", title="No Selection")
            return
        confirm = Messagebox.yesno(
            "Reactivate this user? They will be able to log in again.",
            title="Confirm Reactivate",
        )
        if confirm == "Yes":
            u = self.db.query(User).filter(User.id == uid).first()
            if u:
                u.is_active = True
                self.db.commit()
                self.load_users()

    def _delete_selected(self):
        uid = self._selected_user_id()
        if uid is None:
            Messagebox.show_warning("Please select a user to delete.", title="No Selection")
            return

        if uid == self.user.id:
            Messagebox.show_warning("You cannot delete your own account.", title="Not Allowed")
            return

        confirm = Messagebox.yesno(
            "Deactivate this user?\n\n"
            "Their account will be disabled and they will no longer be able to log in.\n"
            "All their records (leases, tickets, payments) are preserved.\n\n"
            "This cannot be undone without database access.",
            title="Confirm Deactivate",
        )
        if confirm == "Yes":
            u = self.db.query(User).filter(User.id == uid).first()
            if u:
                u.is_active = False
                self.db.commit()
                self.load_users()