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
            tb.Button(btn_bar, text="🗑  Delete", bootstyle="danger",
                      padding=(10, 6),
                      command=self._delete_selected).pack(side=LEFT)

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=20)

        table_frame = tb.Frame(self, padding=(20, 12, 20, 0))
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
        self.db.expire_all()
        for row in self.tree.get_children():
            self.tree.delete(row)

        users = (
            self.db.query(User)
            .options(joinedload(User.role), joinedload(User.city))
            .all()
        )

        for u in users:
            role_display = (
                u.role.name.value.replace("_", " ").title()
                if u.role else "—"
            )
            city_display = u.city.name if u.city else "All Cities"
            status       = "Active" if u.is_active else "Inactive"

            self.tree.insert("", END, values=(
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

        self.db.expire_all()
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

    def _delete_selected(self):
        uid = self._selected_user_id()
        if uid is None:
            Messagebox.show_warning("Please select a user to delete.", title="No Selection")
            return

        if uid == self.user.id:
            Messagebox.show_warning("You cannot delete your own account.", title="Not Allowed")
            return

        confirm = Messagebox.yesno(
            "Are you sure you want to delete this user?\nThis cannot be undone.",
            title="Confirm Delete",
        )
        if confirm == "Yes":
            u = self.db.query(User).filter(User.id == uid).first()
            if u:
                self.db.delete(u)
                self.db.commit()
                self.load_users()