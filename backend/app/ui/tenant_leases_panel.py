"""
app/ui/tenant_leases_panel.py
==============================
Shows all leases for a selected tenant with status,
dates, rent, and option to end/cancel individual leases.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import date

from app.db.database import SessionLocal
from app.db.models import LeaseAgreement, LeaseStatus, Apartment
from sqlalchemy.orm import joinedload


STATUS_COLORS = {
    "active":             "#2ECC71",
    "pending_termination":"#E67E22",
    "terminated_early":   "#E74C3C",
    "expired":            "#7F8C8D",
}


class TenantLeasesPanel(tb.Toplevel):
    """Shows all leases for a tenant and allows ending active ones."""

    def __init__(self, parent, user, tenant_id: int, tenant_name: str):
        super().__init__(parent)
        self.user       = user
        self.db         = SessionLocal()
        self.tenant_id  = tenant_id
        self.tenant_name = tenant_name

        self.title(f"Leases — {tenant_name}")
        self.resizable(True, False)
        self.grab_set()
        self._build_ui()
        self._load_leases()
        self._center(parent)

    def _build_ui(self):
        self.geometry("720x420")

        # Buttons
        btn_row = tb.Frame(self, padding=(20, 0, 20, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Close", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        if self.user.has_permission("lease.terminate"):
            tb.Button(btn_row, text="✂  End Selected Lease",
                      bootstyle="danger",
                      command=self._end_selected).pack(side=RIGHT)

        f = tb.Frame(self, padding=(20, 16, 20, 8))
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text=f"Lease History — {self.tenant_name}",
                 font=("Georgia", 15, "bold")).pack(anchor=W, pady=(0, 12))

        tbl = tb.Frame(f)
        tbl.pack(fill=BOTH, expand=YES)

        cols = ("id", "apartment", "start", "end", "rent", "status")
        self.tree = tb.Treeview(tbl, columns=cols, show="headings",
                                bootstyle="dark", selectmode="browse")

        col_cfg = [
            ("id",        "ID",        50,  CENTER),
            ("apartment", "Unit",      80,  CENTER),
            ("start",     "Start",     110, CENTER),
            ("end",       "End",       110, CENTER),
            ("rent",      "Rent/mo",   100, CENTER),
            ("status",    "Status",    160, CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self.tree.heading(cid, text=heading, anchor=anchor)
            self.tree.column(cid, width=width, anchor=anchor, minwidth=40)

        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(status, foreground=color)

        sb = tb.Scrollbar(tbl, orient=VERTICAL, command=self.tree.yview,
                          bootstyle="round-dark")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        self._count_var = tb.StringVar()
        tb.Label(f, textvariable=self._count_var,
                 font=("Helvetica", 10), bootstyle="secondary").pack(
            anchor=E, pady=(4, 0))

    def _fix_pending_leases(self):
        """Auto-complete any leases stuck in PENDING_TERMINATION state."""
        from app.db.models import LeaseTerminationRequest, ApartmentStatus
        from app.services.invoice_service import void_invoices_for_lease
        from datetime import datetime

        pending = (
            self.db.query(LeaseAgreement)
            .filter(
                LeaseAgreement.tenant_id == self.tenant_id,
                LeaseAgreement.status == LeaseStatus.PENDING_TERMINATION,
            )
            .all()
        )
        for lease in pending:
            # Find the pending termination request
            req = (
                self.db.query(LeaseTerminationRequest)
                .filter(
                    LeaseTerminationRequest.lease_id == lease.id,
                    LeaseTerminationRequest.status == "pending",
                )
                .first()
            )
            if req:
                req.status = "approved"
                req.reviewed_at = datetime.now()
                lease.status = LeaseStatus.TERMINATED_EARLY
                lease.end_date = req.intended_end_date
            else:
                # No request found — just terminate directly
                lease.status = LeaseStatus.TERMINATED_EARLY

            apt = self.db.query(Apartment).filter(Apartment.id == lease.apartment_id).first()
            if apt:
                apt.status = ApartmentStatus.AVAILABLE
            void_invoices_for_lease(self.db, lease.id)

        if pending:
            self.db.commit()

    def _load_leases(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Auto-complete any stuck PENDING_TERMINATION leases
        self._fix_pending_leases()

        leases = (
            self.db.query(LeaseAgreement)
            .options(joinedload(LeaseAgreement.apartment))
            .filter(LeaseAgreement.tenant_id == self.tenant_id)
            .order_by(LeaseAgreement.start_date.desc())
            .all()
        )

        for lease in leases:
            apt    = lease.apartment
            status = lease.status.value if lease.status else "unknown"
            tag    = status
            self.tree.insert("", END, tags=(tag,), values=(
                lease.id,
                apt.unit_number if apt else "—",
                lease.start_date.strftime("%d %b %Y") if lease.start_date else "—",
                lease.end_date.strftime("%d %b %Y") if lease.end_date else "—",
                f"£{lease.agreed_rent:,.2f}" if lease.agreed_rent else "—",
                status.replace("_", " ").title(),
            ))

        self._count_var.set(f"{len(leases)} lease(s) total")

    def _selected_lease_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _end_selected(self):
        lid = self._selected_lease_id()
        if lid is None:
            Messagebox.show_warning("Please select a lease.", title="No Selection")
            return

        lease = self.db.query(LeaseAgreement).filter(LeaseAgreement.id == lid).first()
        if not lease:
            return
        if lease.status != LeaseStatus.ACTIVE:
            Messagebox.show_warning(
                f"Only active leases can be ended. This lease is '{lease.status.value}'.",
                title="Cannot End Lease"
            )
            return

        confirm = Messagebox.yesno(
            f"End lease #{lid}?\n\nThis will immediately terminate the lease "
            f"and return the apartment to Available.\n"
            f"All unpaid invoices for this lease will be voided.",
            title="Confirm End Lease",
        )
        if confirm != "Yes":
            return

        from app.services.lease_service import end_lease
        from app.services.invoice_service import void_invoices_for_lease

        ok, err = end_lease(self.db, lid, ended_by_user_id=self.user.id)
        if not ok:
            Messagebox.show_warning(err, title="Error")
            return

        void_invoices_for_lease(self.db, lid)
        Messagebox.show_info(
            f"Lease #{lid} ended.\nApartment returned to Available.\nUnpaid invoices voided.",
            title="Lease Ended"
        )
        self._load_leases()

    def _center(self, parent):
        self.update_idletasks()
        w, h = 720, 420
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")