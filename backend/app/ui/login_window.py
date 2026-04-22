# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
import ttkbootstrap as tb
from ttkbootstrap.constants import *


class LoginWindow(tb.Frame):
    """Login screen using ttkbootstrap."""

    def __init__(self, parent, on_login_success):
        super().__init__(parent, bootstyle="default")
        self.on_login_success = on_login_success
        self.pack(fill=BOTH, expand=YES)
        self._build_ui()

    def _build_ui(self):
        # ── Centring wrapper ──
        wrapper = tb.Frame(self)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        # ── Brand ──
        tb.Label(
            wrapper, text="PARAGON",
            font=("Georgia", 36, "bold"),
            bootstyle="inverse-default",
        ).pack(pady=(0, 4))

        tb.Label(
            wrapper, text="Property Management System",
            font=("Helvetica", 11),
            bootstyle="secondary",
        ).pack(pady=(0, 30))

        # ── Card ──
        card = tb.Frame(wrapper, bootstyle="dark", padding=32)
        card.pack(ipadx=10)

        tb.Label(
            card, text="Sign in to your account",
            font=("Helvetica", 14, "bold"),
        ).pack(anchor=W, pady=(0, 20))

        # Username
        tb.Label(card, text="Username", font=("Helvetica", 11),
                 bootstyle="secondary").pack(anchor=W)
        self.username_input = tb.Entry(card, width=34, font=("Helvetica", 12))
        self.username_input.pack(pady=(2, 12), fill=X)
        self.username_input.focus()

        # Password
        tb.Label(card, text="Password", font=("Helvetica", 11),
                 bootstyle="secondary").pack(anchor=W)
        self.password_input = tb.Entry(card, width=34, show="•", font=("Helvetica", 12))
        self.password_input.pack(pady=(2, 6), fill=X)
        self.password_input.bind("<Return>", lambda _: self._attempt_login())

        # Error label
        self._error_var = tb.StringVar()
        tb.Label(
            card, textvariable=self._error_var,
            font=("Helvetica", 11), bootstyle="danger",
        ).pack(pady=(4, 0))

        # Login button
        tb.Button(
            card, text="Login", bootstyle="primary",
            width=28, padding=(0, 8),
            command=self._attempt_login,
        ).pack(pady=(14, 0), fill=X)

    def _attempt_login(self):
        self._error_var.set("")
        username = self.username_input.get().strip()
        password = self.password_input.get().strip()
        self.on_login_success(username, password, self)

    def show_error(self, message: str):
        self._error_var.set(message)