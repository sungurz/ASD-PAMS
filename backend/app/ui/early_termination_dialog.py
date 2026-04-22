# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/early_termination_dialog.py
====================================
Dialog for early lease termination.
Terminates immediately — no separate approval step.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import date, timedelta
from decimal import Decimal

from app.db.database import SessionLocal
from app.db.models import LeaseAgreement, LeaseStatus
from app.services.lease_service import (
    request_early_termination, calculate_penalty,
    get_tenant_active_lease, approve_termination
)
from sqlalchemy.orm import joinedload


class EarlyTerminationDialog(tb.Toplevel):

    def __init__(self, parent, user,
                 tenant_id: int | None = None,
                 lease_id: int | None = None):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()

        if lease_id:
            self.lease = (
                self.db.query(LeaseAgreement)
                .options(
                    joinedload(LeaseAgreement.tenant),
                    joinedload(LeaseAgreement.apartment),
                )
                .filter(LeaseAgreement.id == lease_id)
                .first()
            )
        elif tenant_id:
            self.lease = get_tenant_active_lease(self.db, tenant_id)
        else:
            self.lease = None

        self.title("Early Termination Request")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("480x600")

        # Buttons FIRST — anchors to bottom always
        btn_row = tb.Frame(self, padding=(20, 0, 20, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Confirm Termination", bootstyle="danger",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=(20, 16, 20, 8))
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Early Lease Termination",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 12))

        if not self.lease:
            tb.Label(f, text="No active lease found for this tenant.",
                     bootstyle="danger").pack(pady=20)
            return

        card = tb.Frame(f, bootstyle="dark", padding=12)
        card.pack(fill=X, pady=(0, 12))

        tenant_name = self.lease.tenant.full_name if self.lease.tenant else "Unknown"
        apt_unit    = self.lease.apartment.unit_number if self.lease.apartment else "—"

        for text in [
            f"Tenant:       {tenant_name}",
            f"Apartment:    Unit {apt_unit}",
            f"Lease start:  {self.lease.start_date.strftime('%d %b %Y')}",
            f"Lease end:    {self.lease.end_date.strftime('%d %b %Y')}",
        ]:
            tb.Label(card, text=text, font=("Helvetica", 11)).pack(anchor=W)
        tb.Label(card, text=f"Monthly rent: £{self.lease.agreed_rent:,.2f}",
                 font=("Helvetica", 11, "bold")).pack(anchor=W)

        min_date = date.today() + timedelta(days=30)
        notice = tb.Frame(f, bootstyle="warning", padding=10)
        notice.pack(fill=X, pady=(0, 12))
        tb.Label(
            notice,
            text=f"Minimum 30 days notice required.\n"
                 f"Earliest end date: {min_date.strftime('%d %b %Y')}\n"
                 f"Penalty: 5% of monthly rent",
            font=("Helvetica", 10),
            bootstyle="warning",
            justify=LEFT,
        ).pack(anchor=W)

        def lbl(text):
            tb.Label(f, text=text, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        lbl("Intended End Date * (DD/MM/YYYY)")
        self.v_end_date = tb.Entry(f, font=("Helvetica", 12))
        self.v_end_date.insert(0, min_date.strftime("%d/%m/%Y"))
        self.v_end_date.pack(fill=X, pady=(2, 4))
        self.v_end_date.bind("<KeyRelease>", self._update_penalty)

        self._penalty_var = tb.StringVar()
        penalty = calculate_penalty(self.lease.agreed_rent)
        self._penalty_var.set(f"Penalty amount: £{penalty:,.2f}")
        tb.Label(f, textvariable=self._penalty_var,
                 font=("Helvetica", 12, "bold"), bootstyle="danger").pack(anchor=W, pady=(0, 10))

        lbl("Reason for early termination")
        self.v_reason = tb.Text(f, font=("Helvetica", 12), height=3)
        self.v_reason.pack(fill=X, pady=(2, 0))

    def _update_penalty(self, _event=None):
        if self.lease:
            penalty = calculate_penalty(self.lease.agreed_rent)
            self._penalty_var.set(f"Penalty amount: £{penalty:,.2f}")

    def _parse_date(self, text: str) -> date | None:
        text = text.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                from datetime import datetime
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _center(self, parent):
        self.update_idletasks()
        w, h = 480, 600
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        if not self.lease:
            return

        end_date = self._parse_date(self.v_end_date.get())
        if not end_date:
            Messagebox.show_warning(
                "Invalid date format. Use DD/MM/YYYY.", title="Validation", parent=self
            )
            return

        reason = self.v_reason.get("1.0", "end").strip()

        req, error = request_early_termination(
            self.db,
            self.lease.id,
            requested_date=end_date,
            reason=reason,
            requested_by_user_id=self.user.id,
        )
        if error:
            Messagebox.show_warning(error, title="Cannot Terminate", parent=self)
            return

        ok, err2 = approve_termination(
            self.db,
            req.id,
            reviewed_by_user_id=self.user.id,
        )
        if not ok:
            Messagebox.show_warning(err2, title="Termination Error", parent=self)
            return

        penalty = calculate_penalty(self.lease.agreed_rent)
        # Destroy dialog FIRST so message appears on top
        parent_win = self.master
        self.destroy()
        Messagebox.show_info(
            f"Lease terminated successfully.\n"
            f"End date: {end_date.strftime('%d %b %Y')}\n"
            f"Penalty applied: £{penalty:,.2f}\n"
            f"Apartment returned to Available.",
            title="Lease Terminated",
            parent=parent_win,
        )