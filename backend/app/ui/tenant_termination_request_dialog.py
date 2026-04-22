# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/tenant_termination_request_dialog.py
============================================
Tenant-facing early termination REQUEST dialog.
Creates a PENDING_TERMINATION request — does NOT auto-approve.
Management must review and approve via the pending_terminations panel.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import date, timedelta
from decimal import Decimal

from app.db.database import SessionLocal
from app.db.models import LeaseAgreement, LeaseStatus
from app.services.lease_service import (
    request_early_termination, calculate_penalty, get_tenant_active_lease
)
from sqlalchemy.orm import joinedload


class TenantTerminationRequestDialog(tb.Toplevel):
    """
    Tenant submits an early termination request.
    No approval happens here — the request goes to PENDING_TERMINATION
    and management will action it.
    """

    def __init__(self, parent, user, tenant_id: int):
        super().__init__(parent)
        self.user      = user
        self.tenant_id = tenant_id
        self.db        = SessionLocal()

        self.lease = get_tenant_active_lease(self.db, tenant_id)

        self.title("Request Early Termination")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("500x560")

        # Buttons first
        btn_row = tb.Frame(self, padding=(20, 0, 20, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Submit Request", bootstyle="danger",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=(20, 16, 20, 8))
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Request Early Termination",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 4))
        tb.Label(f, text="Your request will be reviewed by the management team.",
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(0, 14))

        if not self.lease:
            tb.Label(f, text="No active lease found.",
                     bootstyle="danger").pack(pady=20)
            return

        # Lease summary
        apt  = self.lease.apartment
        prop = apt.property if apt else None

        card = tb.Frame(f, padding=12)
        card.pack(fill=X, pady=(0, 12))

        for text in [
            f"Property:     {prop.name if prop else '—'}",
            f"Unit:         {apt.unit_number if apt else '—'}",
            f"Monthly rent: £{self.lease.agreed_rent:,.2f}",
            f"Lease ends:   {self.lease.end_date.strftime('%d %b %Y') if self.lease.end_date else '—'}",
        ]:
            tb.Label(card, text=text, font=("Helvetica", 11)).pack(anchor=W)

        # Notice rules
        min_date = date.today() + timedelta(days=30)
        notice = tb.Frame(f, bootstyle="warning", padding=10)
        notice.pack(fill=X, pady=(0, 14))
        tb.Label(
            notice,
            text=f"Minimum 30 days notice required.\n"
                 f"Earliest end date: {min_date.strftime('%d %b %Y')}\n"
                 f"Penalty: 5% of monthly rent = £{calculate_penalty(self.lease.agreed_rent):,.2f}",
            font=("Helvetica", 10), bootstyle="warning", justify=LEFT,
        ).pack(anchor=W)

        def lbl(text):
            tb.Label(f, text=text, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        lbl("Intended End Date * (DD/MM/YYYY)")
        self.v_date = tb.Entry(f, font=("Helvetica", 12))
        self.v_date.insert(0, min_date.strftime("%d/%m/%Y"))
        self.v_date.pack(fill=X, pady=(2, 12))

        lbl("Reason for leaving *")
        self.v_reason = tb.Text(f, font=("Helvetica", 12), height=4)
        self.v_reason.pack(fill=X, pady=(2, 0))

    def _parse_date(self, text: str) -> date | None:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                from datetime import datetime
                return datetime.strptime(text.strip(), fmt).date()
            except ValueError:
                continue
        return None

    def _center(self, parent):
        self.update_idletasks()
        w, h = 500, 560
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        if not self.lease:
            return

        end_date = self._parse_date(self.v_date.get())
        if not end_date:
            Messagebox.show_warning("Invalid date. Use DD/MM/YYYY.", title="Validation", parent=self)
            return

        reason = self.v_reason.get("1.0", "end").strip()
        if not reason:
            Messagebox.show_warning("Please provide a reason.", title="Validation", parent=self)
            return

        req, error = request_early_termination(
            self.db,
            self.lease.id,
            requested_date=end_date,
            reason=reason,
            requested_by_user_id=getattr(self.user, "id", None),
        )
        if error:
            Messagebox.show_warning(error, title="Cannot Submit", parent=self)
            return

        penalty = calculate_penalty(self.lease.agreed_rent)
        parent_win = self.master
        self.destroy()
        Messagebox.show_info(
            f"Your request has been submitted.\n\n"
            f"Requested end date: {end_date.strftime('%d %b %Y')}\n"
            f"Penalty amount: £{penalty:,.2f}\n\n"
            f"Management will review your request and contact you.\n"
            f"Your lease remains active until approved.",
            title="Request Submitted",
            parent=parent_win,
        )