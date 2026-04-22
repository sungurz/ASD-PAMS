# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/session_manager.py
==========================
Tracks user activity and triggers auto-logout after 30 minutes
of inactivity. Attach to MainWindow after login.

Usage in main_window.py:
    from app.ui.session_manager import SessionManager
    self._session = SessionManager(self, timeout_minutes=30,
                                   on_timeout=self._logout)
    # Call self._session.reset() on any user interaction
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *


class SessionManager:
    """
    Monitors inactivity and calls on_timeout after timeout_minutes.
    Uses Tkinter's after() scheduler — no threads needed.
    """

    TIMEOUT_MS = 30 * 60 * 1000   # 30 minutes in milliseconds
    WARNING_MS = 29 * 60 * 1000   # warn at 29 minutes

    def __init__(self, root: tb.Frame, *, timeout_minutes: int = 30, on_timeout):
        self.root        = root
        self.on_timeout  = on_timeout
        self.timeout_ms  = timeout_minutes * 60 * 1000
        self.warning_ms  = (timeout_minutes - 1) * 60 * 1000
        self._timer      = None
        self._warn_timer = None
        self._active     = True

        # Bind all user interaction events to reset the timer
        for event in ("<Motion>", "<KeyPress>", "<ButtonPress>"):
            try:
                root.bind_all(event, self._on_activity, add="+")
            except Exception:
                pass

        self._schedule()

    def reset(self):
        """Manually reset the inactivity timer (e.g. after a dialog closes)."""
        self._schedule()

    def stop(self):
        """Stop the session manager (call on logout)."""
        self._active = False
        if self._timer:
            try:
                self.root.after_cancel(self._timer)
            except Exception:
                pass
        if self._warn_timer:
            try:
                self.root.after_cancel(self._warn_timer)
            except Exception:
                pass

    def _on_activity(self, _event=None):
        if self._active:
            self._schedule()

    def _schedule(self):
        if not self._active:
            return
        # Cancel existing timers
        if self._timer:
            try:
                self.root.after_cancel(self._timer)
            except Exception:
                pass
        if self._warn_timer:
            try:
                self.root.after_cancel(self._warn_timer)
            except Exception:
                pass
        # Schedule warning and timeout
        self._warn_timer = self.root.after(self.warning_ms,  self._warn)
        self._timer      = self.root.after(self.timeout_ms,  self._timeout)

    def _warn(self):
        """Show a 1-minute warning toast."""
        if not self._active:
            return
        try:
            self._show_warning_toast()
        except Exception:
            pass

    def _timeout(self):
        """Log the user out."""
        if not self._active:
            return
        self._active = False
        try:
            self.on_timeout()
        except Exception:
            pass

    def _show_warning_toast(self):
        """Show a small non-blocking warning window."""
        try:
            toast = tb.Toplevel(self.root)
            toast.title("Session Expiring")
            toast.geometry("320x100")
            toast.resizable(False, False)
            toast.attributes("-topmost", True)

            tb.Label(toast,
                     text="⚠  Your session expires in 1 minute.",
                     font=("Helvetica", 11), bootstyle="warning").pack(pady=12)

            btn_row = tb.Frame(toast)
            btn_row.pack()
            tb.Button(btn_row, text="Stay Logged In", bootstyle="success",
                      command=lambda: [self.reset(), toast.destroy()]).pack(side=LEFT, padx=6)
            tb.Button(btn_row, text="Logout Now", bootstyle="secondary",
                      command=lambda: [self.stop(), toast.destroy(), self.on_timeout()]).pack(side=LEFT)

            # Auto-close toast after 55 seconds
            toast.after(55000, lambda: toast.destroy() if toast.winfo_exists() else None)
        except Exception:
            pass