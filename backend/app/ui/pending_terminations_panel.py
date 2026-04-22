# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/pending_terminations_panel.py
=====================================
Management panel showing all pending early termination requests.
Location Admins and Managers can approve or reject each request.

Accessible from the Tenants page toolbar.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from app.db.database import SessionLocal
from app.db.models import (
    LeaseTerminationRequest, LeaseAgreement, Tenant, Apartment
)
from app.services.lease_service import approve_termination
from sqlalchemy.orm import joinedload


class PendingTerminationsPanel(tb.Toplevel):

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self.title("Pending Termination Requests")
        self.resizable(True, False)
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
        self.geometry("780x460")

        btn_row = tb.Frame(self, padding=(20, 0, 20, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Close", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="✓  Approve Selected",
                  bootstyle="success", command=self._approve).pack(side=RIGHT, padx=(0, 6))
        tb.Button(btn_row, text="✗  Reject Selected",
                  bootstyle="danger", command=self._reject).pack(side=RIGHT)

        f = tb.Frame(self, padding=(20, 16, 20, 8))
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Pending Termination Requests",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 4))
        tb.Label(f, text="Review each request and approve or reject. Approving immediately terminates the lease.",
                 font=("Helvetica", 10), bootstyle="secondary",
                 wraplength=720, justify=LEFT).pack(anchor=W, pady=(0, 12))

        tbl = tb.Frame(f)
        tbl.pack(fill=BOTH, expand=YES)

        cols = ("id", "tenant", "unit", "rent", "requested_end", "penalty", "reason", "requested")
        self.tree = tb.Treeview(tbl, columns=cols, show="headings",
                                bootstyle="dark", selectmode="browse")

        col_cfg = [
            ("id",           "ID",           50,  CENTER),
            ("tenant",       "Tenant",       160, W),
            ("unit",         "Unit",         70,  CENTER),
            ("rent",         "Rent/mo",      90,  CENTER),
            ("requested_end","End Date",     110, CENTER),
            ("penalty",      "Penalty",      90,  CENTER),
            ("reason",       "Reason",       180, W),
            ("requested",    "Submitted",    110, CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self.tree.heading(cid, text=heading, anchor=anchor)
            self.tree.column(cid, width=width, anchor=anchor, minwidth=40)

        sb = tb.Scrollbar(tbl, orient=VERTICAL, command=self.tree.yview,
                          bootstyle="round-dark")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        self._count_var = tb.StringVar()
        tb.Label(f, textvariable=self._count_var,
                 font=("Helvetica", 10), bootstyle="secondary").pack(
            anchor=E, pady=(4, 0))

    def _load(self):
        self.db.rollback()
        self.db.expire_all()
        for row in self.tree.get_children():
            self.tree.delete(row)

        requests = (
            self.db.query(LeaseTerminationRequest)
            .filter(LeaseTerminationRequest.status == "pending")
            .order_by(LeaseTerminationRequest.requested_date.desc())
            .all()
        )

        # Batch load leases and tenants
        lease_ids  = [r.lease_id for r in requests]
        leases     = {l.id: l for l in
                      self.db.query(LeaseAgreement)
                      .options(joinedload(LeaseAgreement.apartment))
                      .filter(LeaseAgreement.id.in_(lease_ids)).all()}
        tenant_ids = [l.tenant_id for l in leases.values() if l.tenant_id]
        tenants    = {t.id: t for t in
                      self.db.query(Tenant)
                      .filter(Tenant.id.in_(tenant_ids)).all()}

        for req in requests:
            lease  = leases.get(req.lease_id)
            tenant = tenants.get(lease.tenant_id) if lease else None
            apt    = lease.apartment if lease else None

            self.tree.insert("", END, values=(
                req.id,
                tenant.full_name if tenant else "—",
                apt.unit_number if apt else "—",
                f"£{lease.agreed_rent:,.2f}" if lease else "—",
                req.intended_end_date.strftime("%d %b %Y") if req.intended_end_date else "—",
                f"£{req.penalty_amount:,.2f}" if req.penalty_amount else "—",
                (req.reason or "—")[:60],
                req.requested_date.strftime("%d %b %Y") if req.requested_date else "—",
            ))

        count = len(requests)
        self._count_var.set(
            f"{count} pending request(s)" if count else "No pending requests"
        )

    def _selected_req_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _approve(self):
        req_id = self._selected_req_id()
        if req_id is None:
            Messagebox.show_warning("Please select a request.", title="No Selection")
            return

        # Get details for confirmation
        req = self.db.query(LeaseTerminationRequest).filter(
            LeaseTerminationRequest.id == req_id
        ).first()
        if not req:
            return

        confirm = Messagebox.yesno(
            f"Approve this termination request?\n\n"
            f"End date: {req.intended_end_date.strftime('%d %b %Y') if req.intended_end_date else '—'}\n"
            f"Penalty: £{req.penalty_amount:,.2f}\n\n"
            f"This will immediately terminate the lease,\n"
            f"free the apartment, and void unpaid invoices.",
            title="Confirm Approval",
        )
        if confirm != "Yes":
            return

        ok, err = approve_termination(
            self.db, req_id,
            reviewed_by_user_id=self.user.id,
        )
        if not ok:
            Messagebox.show_warning(err, title="Error")
            return

        # Generate penalty invoice
        self._generate_penalty_invoice(req)

        Messagebox.show_info(
            "Termination approved.\n"
            "Lease terminated, apartment freed, penalty invoice generated.",
            title="Approved"
        )
        self._load()

    def _reject(self):
        req_id = self._selected_req_id()
        if req_id is None:
            Messagebox.show_warning("Please select a request.", title="No Selection")
            return

        confirm = Messagebox.yesno(
            "Reject this termination request?\n\n"
            "The tenant's lease will remain active.",
            title="Confirm Rejection",
        )
        if confirm != "Yes":
            return

        req = self.db.query(LeaseTerminationRequest).filter(
            LeaseTerminationRequest.id == req_id
        ).first()
        if req:
            req.status = "rejected"
            # Revert lease back to active
            lease = self.db.query(LeaseAgreement).filter(
                LeaseAgreement.id == req.lease_id
            ).first()
            if lease:
                from app.db.models import LeaseStatus
                lease.status = LeaseStatus.ACTIVE
            self.db.commit()

        Messagebox.show_info(
            "Request rejected. The lease remains active.",
            title="Rejected"
        )
        self._load()

    def _generate_penalty_invoice(self, req: LeaseTerminationRequest):
        """Auto-generate a penalty invoice when termination is approved."""
        try:
            from app.services.invoice_service import generate_invoice
            from datetime import date
            today = date.today()
            generate_invoice(
                self.db,
                lease_id=req.lease_id,
                billing_period_start=today,
                billing_period_end=today,
                due_date=today,
                notes=f"Early termination penalty — 5% of monthly rent",
                amount_override=req.penalty_amount,
            )
        except Exception:
            pass  # Don't block approval if penalty invoice fails

    def _center(self, parent):
        self.update_idletasks()
        w, h = 780, 460
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")