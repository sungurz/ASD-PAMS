# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/ui/tenant_dashboard.py
===========================
Tenant self-service dashboard.

Requirements (from case study):
  - View own payment records
  - Late payment alerts
  - Submit complaints
  - Submit maintenance requests
  - View progress of repair requests
  - Graphical payment history (bar chart via canvas)
  - Payment vs neighbours comparison
  - Make payments (card validation)
  - Late payments graph per property
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from decimal import Decimal
import re

from app.db.database import SessionLocal
from app.db.models import (
    Invoice, InvoiceStatus, Payment, PaymentMethod,
    MaintenanceTicket, MaintenanceStatus, MaintenancePriority,
    Complaint, ComplaintCategory, LeaseAgreement, LeaseStatus,
    Apartment, Property, LatePaymentAlert
)
from app.services.payment_service import record_payment
from app.services.maintenance_service import create_ticket
from app.services.complaint_service import create_complaint
from sqlalchemy.orm import joinedload
from sqlalchemy import func


class TenantDashboard(tb.Frame):

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user      = user
        self.db        = SessionLocal()
        # Resolve tenant_id — from UserContext or by looking up Tenant.user_id
        self.tenant_id = getattr(user, "tenant_id", None)
        if not self.tenant_id:
            from app.db.models import Tenant as _T
            t = self.db.query(_T).filter(_T.user_id == user.id).first()
            if t:
                self.tenant_id = t.id
        self._build_ui()
        self.load_dashboard()

    def destroy(self):
        try:
            self.db.close()
        except Exception:
            pass
        super().destroy()

    def _refresh_db(self):
        try:
            self.db.close()
        except Exception:
            pass
        from app.db.database import SessionLocal as _SL
        self.db = _SL()

    # ── UI ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        header = tb.Frame(self, padding=(24, 20, 24, 8))
        header.pack(fill=X)
        tb.Label(header, text=f"My Dashboard",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)
        tb.Button(header, text="↻  Refresh", bootstyle="secondary",
                  padding=(8, 4), command=self.load_dashboard).pack(side=RIGHT)

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=24)

        self.nb = tb.Notebook(self, bootstyle="primary")
        self.nb.pack(fill=BOTH, expand=YES, padx=20, pady=12)

        self._tab_overview   = tb.Frame(self.nb, padding=16)
        self._tab_payments   = tb.Frame(self.nb, padding=16)
        self._tab_charts     = tb.Frame(self.nb, padding=16)
        self._tab_maint      = tb.Frame(self.nb, padding=16)
        self._tab_complaints = tb.Frame(self.nb, padding=16)

        self.nb.add(self._tab_overview,   text="  Overview  ")
        self.nb.add(self._tab_payments,   text="  Payments  ")
        self.nb.add(self._tab_charts,     text="  Charts  ")
        self.nb.add(self._tab_maint,      text="  Maintenance  ")
        self.nb.add(self._tab_complaints, text="  Complaints  ")

    def load_dashboard(self):
        self._refresh_db()
        self._load_overview()
        self._load_payments()
        self._load_charts()
        self._load_maintenance()
        self._load_complaints()

    # ── Overview tab ────────────────────────────────────────────────────────
    def _load_overview(self):
        for w in self._tab_overview.winfo_children():
            w.destroy()

        # Lease info
        lease = self._get_active_lease()
        if lease:
            lease_frame = tb.Frame(self._tab_overview, padding=16)
            lease_frame.pack(fill=X, pady=(0, 16))

            tb.Label(lease_frame, text="My Lease",
                     font=("Georgia", 14, "bold")).pack(anchor=W, pady=(0, 8))

            apt  = lease.apartment
            prop = apt.property if apt else None

            from datetime import date as _date
            days_left = (lease.end_date - _date.today()).days if lease.end_date else 0

            info = [
                ("Property",    prop.name if prop else "—"),
                ("Unit",        f"Unit {apt.unit_number}" if apt else "—"),
                ("Monthly Rent",f"£{lease.agreed_rent:,.2f}"),
                ("Deposit",     f"£{lease.deposit:,.2f}" if lease.deposit else "—"),
                ("Lease Start", lease.start_date.strftime("%d %b %Y") if lease.start_date else "—"),
                ("Lease End",   lease.end_date.strftime("%d %b %Y") if lease.end_date else "—"),
                ("Days Remaining", f"{days_left} days" if days_left > 0 else "Expired"),
            ]
            for label, value in info:
                row = tb.Frame(lease_frame)
                row.pack(fill=X, pady=2)
                tb.Label(row, text=label, font=("Helvetica", 10),
                         bootstyle="secondary", width=16).pack(side=LEFT)
                tb.Label(row, text=value, font=("Helvetica", 11)).pack(side=LEFT)

            # Request early termination button
            tb.Separator(lease_frame, orient=HORIZONTAL).pack(fill=X, pady=(10, 8))
            tb.Label(lease_frame,
                     text="Need to leave early? You can request early termination (1 month notice, 5% penalty applies).",
                     font=("Helvetica", 9), bootstyle="secondary", wraplength=520, justify=LEFT).pack(anchor=W)
            tb.Button(lease_frame, text="📋  Request Early Termination",
                      bootstyle="danger-outline", padding=(10, 5),
                      command=self._request_termination).pack(anchor=W, pady=(6, 0))
        else:
            tb.Label(self._tab_overview, text="No active lease found.",
                     bootstyle="warning").pack(anchor=W, pady=8)

        # Late payment alerts
        alerts = (
            self.db.query(LatePaymentAlert)
            .join(Invoice, LatePaymentAlert.invoice_id == Invoice.id)
            .filter(
                Invoice.tenant_id == self.tenant_id,
                LatePaymentAlert.is_resolved == False,
            )
            .all()
        )
        if alerts:
            tb.Label(self._tab_overview, text="Late Payment Alerts",
                     font=("Georgia", 14, "bold")).pack(anchor=W, pady=(8, 6))
            for alert in alerts:
                inv = alert.invoice
                alert_card = tb.Frame(self._tab_overview, padding=10)
                alert_card.pack(fill=X, pady=(0, 6))
                tb.Label(alert_card,
                         text=f"⚠  {inv.invoice_number} — £{inv.amount:,.2f} — {alert.days_overdue} days overdue",
                         font=("Helvetica", 11), bootstyle="danger").pack(anchor=W)
                tb.Label(alert_card,
                         text=f"Due: {inv.due_date.strftime('%d %b %Y') if inv.due_date else '—'}",
                         font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

        # Balance summary
        if self.tenant_id:
            invoices = self.db.query(Invoice).filter(Invoice.tenant_id == self.tenant_id).all()
            outstanding = sum(i.amount for i in invoices
                              if i.status in (InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE))
            if outstanding > 0:
                tb.Label(self._tab_overview,
                         text=f"Outstanding balance: £{float(outstanding):,.2f}",
                         font=("Helvetica", 11, "bold"), bootstyle="warning").pack(anchor=W, pady=(8, 0))

        # Quick actions
        tb.Label(self._tab_overview, text="Quick Actions",
                 font=("Georgia", 14, "bold")).pack(anchor=W, pady=(16, 8))

        btn_row = tb.Frame(self._tab_overview)
        btn_row.pack(anchor=W)
        tb.Button(btn_row, text="💳  Make Payment",
                  bootstyle="success", padding=(12, 6),
                  command=self._open_payment_dialog).pack(side=LEFT, padx=(0, 8))
        tb.Button(btn_row, text="🔧  Report Repair",
                  bootstyle="warning", padding=(12, 6),
                  command=self._open_maintenance_dialog).pack(side=LEFT, padx=(0, 8))
        tb.Button(btn_row, text="📝  Submit Complaint",
                  bootstyle="secondary", padding=(12, 6),
                  command=self._open_complaint_dialog).pack(side=LEFT)

    # ── Payments tab ────────────────────────────────────────────────────────
    def _load_payments(self):
        for w in self._tab_payments.winfo_children():
            w.destroy()

        tb.Label(self._tab_payments, text="My Invoices & Payments",
                 font=("Georgia", 14, "bold")).pack(anchor=W, pady=(0, 12))

        # Summary cards
        invoices = (
            self.db.query(Invoice)
            .filter(Invoice.tenant_id == self.tenant_id)
            .all()
        )
        invoice_ids = [i.id for i in invoices]
        total_paid = Decimal("0")
        if invoice_ids:
            total_paid = (
                self.db.query(func.sum(Payment.amount))
                .filter(Payment.invoice_id.in_(invoice_ids))
                .scalar() or Decimal("0")
            )

        outstanding = sum(i.amount for i in invoices
                          if i.status in (InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE))
        overdue     = sum(i.amount for i in invoices
                          if i.status == InvoiceStatus.OVERDUE)

        cards = tb.Frame(self._tab_payments)
        cards.pack(fill=X, pady=(0, 16))
        for val, label, style in [
            (f"£{float(total_paid):,.0f}", "Total Paid",   "success"),
            (f"£{float(outstanding):,.0f}", "Outstanding", "warning"),
            (f"£{float(overdue):,.0f}",    "Overdue",      "danger"),
        ]:
            card = tb.Frame(cards, padding=(14, 10))
            card.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
            tb.Label(card, text=val,   font=("Georgia", 18, "bold"), bootstyle=style).pack(anchor=W)
            tb.Label(card, text=label, font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

        # Invoice table
        tb.Label(self._tab_payments, text="Invoice History",
                 font=("Georgia", 13, "bold")).pack(anchor=W, pady=(0, 6))

        tbl = tb.Frame(self._tab_payments)
        tbl.pack(fill=BOTH, expand=YES)

        cols = ("inv_num", "period", "amount", "paid", "remaining", "due", "status")
        tree = tb.Treeview(tbl, columns=cols, show="headings",
                           bootstyle="dark", selectmode="browse")
        col_cfg = [
            ("inv_num",   "Invoice #",   120, W),
            ("period",    "Period",      120, CENTER),
            ("amount",    "Total",       90,  CENTER),
            ("paid",      "Paid",        90,  CENTER),
            ("remaining", "Remaining",   90,  CENTER),
            ("due",       "Due Date",    100, CENTER),
            ("status",    "Status",      90,  CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            tree.heading(cid, text=heading, anchor=anchor)
            tree.column(cid, width=width, anchor=anchor)

        tree.tag_configure("paid",    foreground="#2ECC71")
        tree.tag_configure("overdue", foreground="#E74C3C")
        tree.tag_configure("issued",  foreground="#3498DB")
        tree.tag_configure("void",    foreground="#7F8C8D")

        paid_by_inv: dict[int, Decimal] = {}
        if invoice_ids:
            rows = (
                self.db.query(Payment.invoice_id, func.sum(Payment.amount))
                .filter(Payment.invoice_id.in_(invoice_ids))
                .group_by(Payment.invoice_id)
                .all()
            )
            paid_by_inv = {r[0]: r[1] or Decimal("0") for r in rows}

        for inv in sorted(invoices, key=lambda x: x.due_date or x.created_at, reverse=True):
            paid_amt = paid_by_inv.get(inv.id, Decimal("0"))
            rem      = max(inv.amount - paid_amt, Decimal("0"))
            period   = ""
            if inv.billing_period_start and inv.billing_period_end:
                period = f"{inv.billing_period_start.strftime('%b')}–{inv.billing_period_end.strftime('%b %Y')}"
            tag = inv.status.value if inv.status else "issued"
            tree.insert("", END, tags=(tag,), values=(
                inv.invoice_number,
                period,
                f"£{inv.amount:,.2f}",
                f"£{float(paid_amt):,.2f}",
                f"£{float(rem):,.2f}",
                inv.due_date.strftime("%d %b %Y") if inv.due_date else "—",
                inv.status.value.title() if inv.status else "—",
            ))

        self._inv_tree = tree
        sb = tb.Scrollbar(tbl, orient=VERTICAL, command=tree.yview, bootstyle="round-dark")
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        tb.Button(self._tab_payments, text="💳  Pay Selected Invoice",
                  bootstyle="success", padding=(10, 5),
                  command=self._pay_selected_invoice).pack(anchor=W, pady=(8, 0))

    def _pay_selected_invoice(self):
        sel = self._inv_tree.selection()
        if not sel:
            Messagebox.show_warning("Please select an invoice to pay.", title="No Selection")
            return
        inv_num = self._inv_tree.item(sel[0])["values"][0]
        inv = self.db.query(Invoice).filter(Invoice.invoice_number == inv_num).first()
        if inv:
            self._open_payment_dialog(invoice_id=inv.id)

    # ── Charts tab ──────────────────────────────────────────────────────────
    def _load_charts(self):
        for w in self._tab_charts.winfo_children():
            w.destroy()

        payments = (
            self.db.query(Payment)
            .filter(Payment.tenant_id == self.tenant_id)
            .order_by(Payment.payment_date)
            .all()
        )

        # Monthly totals
        monthly: dict[str, float] = {}
        for p in payments:
            if p.payment_date:
                key = p.payment_date.strftime("%b %Y")
                monthly[key] = monthly.get(key, 0.0) + float(p.amount)

        tb.Label(self._tab_charts, text="Payment History by Month",
                 font=("Georgia", 14, "bold")).pack(anchor=W, pady=(0, 12))

        if not monthly:
            tb.Label(self._tab_charts, text="No payment data yet.",
                     bootstyle="secondary").pack(anchor=W)
        else:
            self._draw_bar_chart(self._tab_charts, monthly, "#2ECC71", "Month", "Amount (£)")

        # Late payments chart
        tb.Label(self._tab_charts, text="Late Payments",
                 font=("Georgia", 14, "bold")).pack(anchor=W, pady=(16, 8))

        late_invs = (
            self.db.query(Invoice)
            .filter(
                Invoice.tenant_id == self.tenant_id,
                Invoice.status == InvoiceStatus.OVERDUE,
            )
            .all()
        )
        if not late_invs:
            tb.Label(self._tab_charts, text="No late payments. Great job!",
                     bootstyle="success").pack(anchor=W)
        else:
            late_data = {}
            for inv in late_invs:
                # Group by property name as required
                prop_name = "Unknown Property"
                if inv.lease and inv.lease.apartment and inv.lease.apartment.property:
                    prop_name = inv.lease.apartment.property.name
                late_data[prop_name] = late_data.get(prop_name, 0.0) + float(inv.amount)
            self._draw_bar_chart(self._tab_charts, late_data, "#E74C3C", "Property", "Overdue (£)")

        # vs Neighbours comparison
        tb.Label(self._tab_charts, text="My Payments vs Neighbours",
                 font=("Georgia", 14, "bold")).pack(anchor=W, pady=(16, 8))
        self._draw_neighbours_chart()

    def _draw_bar_chart(self, parent, data: dict, color: str, x_label: str, y_label: str):
        if not data:
            return

        canvas_h = 180
        canvas_w = 600
        canvas = tb.Canvas(parent, height=canvas_h, width=canvas_w, bg="#1a1a2e")
        canvas.pack(anchor=W, pady=(0, 4))

        keys   = list(data.keys())[-8:]  # last 8 entries
        values = [data[k] for k in keys]
        max_v  = max(values) if values else 1
        if max_v == 0:
            max_v = 1

        pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
        bar_area_w = canvas_w - pad_l - pad_r
        bar_w      = bar_area_w / len(keys) * 0.6
        gap        = bar_area_w / len(keys)

        for i, (key, val) in enumerate(zip(keys, values)):
            x0 = pad_l + i * gap + gap * 0.2
            bar_h = (val / max_v) * (canvas_h - pad_t - pad_b)
            y1 = canvas_h - pad_b
            y0 = y1 - bar_h

            canvas.create_rectangle(x0, y0, x0 + bar_w, y1, fill=color, outline="")
            canvas.create_text(x0 + bar_w / 2, y1 + 10, text=key,
                               fill="#aaaaaa", font=("Helvetica", 8), angle=30 if len(keys) > 5 else 0)
            canvas.create_text(x0 + bar_w / 2, y0 - 8,
                               text=f"£{val:,.0f}", fill="#ffffff", font=("Helvetica", 7))

        # y-axis
        canvas.create_line(pad_l, pad_t, pad_l, canvas_h - pad_b, fill="#555555")
        canvas.create_text(14, canvas_h // 2, text=y_label, fill="#aaaaaa",
                           font=("Helvetica", 8), angle=90)

    def _draw_neighbours_chart(self):
        lease = self._get_active_lease()
        if not lease or not lease.apartment:
            tb.Label(self._tab_charts, text="No lease data for comparison.",
                     bootstyle="secondary").pack(anchor=W)
            return

        prop_id = lease.apartment.property_id

        # Get all tenants in same property
        neighbour_leases = (
            self.db.query(LeaseAgreement)
            .options(joinedload(LeaseAgreement.apartment))
            .join(Apartment, LeaseAgreement.apartment_id == Apartment.id)
            .filter(
                Apartment.property_id == prop_id,
                LeaseAgreement.status == LeaseStatus.ACTIVE,
            )
            .all()
        )

        comparison: dict[str, float] = {}
        for nl in neighbour_leases:
            label = f"Unit {nl.apartment.unit_number}" if nl.apartment else "?"
            if nl.tenant_id == self.tenant_id:
                label = f"Me ({label})"
            total = (
                self.db.query(func.sum(Payment.amount))
                .filter(Payment.tenant_id == nl.tenant_id)
                .scalar() or Decimal("0")
            )
            comparison[label] = float(total)

        if comparison:
            self._draw_bar_chart(self._tab_charts, comparison, "#3498DB", "Tenant", "Total Paid (£)")
        else:
            tb.Label(self._tab_charts, text="No neighbour data available.",
                     bootstyle="secondary").pack(anchor=W)

    # ── Maintenance tab ─────────────────────────────────────────────────────
    def _load_maintenance(self):
        for w in self._tab_maint.winfo_children():
            w.destroy()

        header = tb.Frame(self._tab_maint)
        header.pack(fill=X, pady=(0, 16))
        tb.Label(header, text="My Repair Requests",
                 font=("Georgia", 14, "bold")).pack(side=LEFT)
        tb.Button(header, text="＋  Report a Repair",
                  bootstyle="warning", padding=(10, 5),
                  command=self._open_maintenance_dialog).pack(side=RIGHT)

        tickets = (
            self.db.query(MaintenanceTicket)
            .filter(MaintenanceTicket.tenant_id == self.tenant_id)
            .order_by(MaintenanceTicket.created_at.desc())
            .all()
        )

        if not tickets:
            empty = tb.Frame(self._tab_maint, padding=24)
            empty.pack(fill=X)
            tb.Label(empty, text="No repair requests yet.",
                     font=("Helvetica", 12), bootstyle="secondary").pack()
            tb.Label(empty, text="Click \u201c+ Report a Repair\u201d to log an issue.",
                     font=("Helvetica", 10), bootstyle="secondary").pack()
            return

        STATUS_COLORS = {
            "new":          ("#E74C3C", "New"),
            "triaged":      ("#E67E22", "Being Reviewed"),
            "scheduled":    ("#3498DB", "Scheduled"),
            "in_progress":  ("#2ECC71", "In Progress"),
            "waiting_parts":("#9B59B6", "Waiting for Parts"),
            "resolved":     ("#27AE60", "Resolved"),
            "closed":       ("#7F8C8D", "Closed"),
        }
        PRIO_LABELS = {"urgent":"Urgent","high":"High","medium":"Medium","low":"Low"}

        for t in tickets:
            status_val = t.status.value if t.status else "new"
            color, status_label = STATUS_COLORS.get(status_val, ("#7F8C8D", status_val.title()))
            prio = t.priority.value if t.priority else "medium"

            card = tb.Frame(self._tab_maint, padding=(12, 10))
            card.pack(fill=X, pady=(0, 8))

            # Left colour bar
            bar = tb.Frame(card, width=4)
            bar.pack(side=LEFT, fill=Y, padx=(0, 12))
            bar.pack_propagate(False)

            # Content
            content_frame = tb.Frame(card)
            content_frame.pack(side=LEFT, fill=X, expand=YES)

            # Title row
            title_row = tb.Frame(content_frame)
            title_row.pack(fill=X)
            tb.Label(title_row, text=t.title,
                     font=("Helvetica", 12, "bold")).pack(side=LEFT)
            tb.Label(title_row, text=status_label,
                     font=("Helvetica", 10), foreground=color).pack(side=RIGHT)

            # Sub info row
            sub_row = tb.Frame(content_frame)
            sub_row.pack(fill=X, pady=(2, 0))
            date_str = t.created_at.strftime("%d %b %Y") if t.created_at else ""
            tb.Label(sub_row,
                     text=f"Priority: {PRIO_LABELS.get(prio, prio.title())}  \u2022  Reported: {date_str}",
                     font=("Helvetica", 10), bootstyle="secondary").pack(side=LEFT)

            # View progress button
            tid = t.id
            tb.Button(sub_row, text="View Progress ›",
                      bootstyle="link", padding=(4, 2),
                      command=lambda x=tid: self._show_ticket_progress(x)).pack(side=RIGHT)

            tb.Separator(self._tab_maint, orient=HORIZONTAL).pack(fill=X)

    def _show_ticket_progress(self, ticket_id: int):
        from app.db.models import MaintenanceUpdate, User
        win = tb.Toplevel(self)
        win.title("Repair Progress")
        win.geometry("500x400")
        win.grab_set()

        ticket = self.db.query(MaintenanceTicket).filter(
            MaintenanceTicket.id == ticket_id
        ).first()
        if not ticket:
            return

        f = tb.Frame(win, padding=20)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text=ticket.title,
                 font=("Georgia", 14, "bold")).pack(anchor=W, pady=(0, 4))

        status_label = ticket.status.value.replace("_"," ").title() if ticket.status else "—"
        priority_label = ticket.priority.value.title() if ticket.priority else "—"
        tb.Label(f, text=f"Status: {status_label}   Priority: {priority_label}",
                 font=("Helvetica", 10), bootstyle="info").pack(anchor=W)

        # Show scheduled date if set
        if hasattr(ticket, "scheduled_date") and ticket.scheduled_date:
            tb.Label(f,
                     text=f"Scheduled: {ticket.scheduled_date.strftime('%d %b %Y %H:%M')}",
                     font=("Helvetica", 10), bootstyle="warning").pack(anchor=W)

        # Show time spent if set
        if hasattr(ticket, "time_taken_hours") and ticket.time_taken_hours:
            tb.Label(f,
                     text=f"Time spent: {ticket.time_taken_hours} hour(s)",
                     font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

        # Show cost if set
        if hasattr(ticket, "material_cost") and ticket.material_cost:
            tb.Label(f,
                     text=f"Material cost: £{ticket.material_cost:,.2f}",
                     font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

        tb.Label(f, text="", font=("Helvetica", 6)).pack()

        tb.Label(f, text="Progress Timeline",
                 font=("Georgia", 12, "bold")).pack(anchor=W, pady=(0, 6))

        updates = (
            self.db.query(MaintenanceUpdate)
            .filter(MaintenanceUpdate.ticket_id == ticket_id)
            .order_by(MaintenanceUpdate.created_at.desc())
            .all()
        )
        if not updates:
            tb.Label(f, text="No updates yet.", bootstyle="secondary").pack(anchor=W)
        else:
            for upd in updates:
                row = tb.Frame(f, padding=(0, 4))
                row.pack(fill=X)
                tb.Label(row, text="→",
                         font=("Helvetica", 10), bootstyle="info").pack(side=LEFT, padx=(0, 8))
                txt = f"{upd.new_status.value.replace('_',' ').title() if upd.new_status else '—'}"
                if upd.note:
                    txt += f": {upd.note}"
                tb.Label(row, text=txt, font=("Helvetica", 10)).pack(side=LEFT)
                if upd.created_at:
                    tb.Label(row, text=upd.created_at.strftime("%d %b %Y %H:%M"),
                             font=("Helvetica", 9), bootstyle="secondary").pack(side=RIGHT)
                tb.Separator(f, orient=HORIZONTAL).pack(fill=X)

        tb.Button(win, text="Close", bootstyle="secondary",
                  command=win.destroy).pack(pady=8)

    # ── Complaints tab ──────────────────────────────────────────────────────
    def _load_complaints(self):
        for w in self._tab_complaints.winfo_children():
            w.destroy()

        header = tb.Frame(self._tab_complaints)
        header.pack(fill=X, pady=(0, 16))
        tb.Label(header, text="My Complaints",
                 font=("Georgia", 14, "bold")).pack(side=LEFT)
        tb.Button(header, text="＋  Submit Complaint",
                  bootstyle="secondary", padding=(10, 5),
                  command=self._open_complaint_dialog).pack(side=RIGHT)

        complaints = (
            self.db.query(Complaint)
            .filter(Complaint.tenant_id == self.tenant_id)
            .order_by(Complaint.id.desc())
            .all()
        )

        if not complaints:
            empty = tb.Frame(self._tab_complaints, padding=24)
            empty.pack(fill=X)
            tb.Label(empty, text="No complaints submitted yet.",
                     font=("Helvetica", 12), bootstyle="secondary").pack()
            tb.Label(empty, text="Use \u201c+ Submit Complaint\u201d if you have a concern.",
                     font=("Helvetica", 10), bootstyle="secondary").pack()
            return

        STATUS_COLORS = {
            "open":         ("#E74C3C", "Open"),
            "under_review": ("#E67E22", "Under Review"),
            "resolved":     ("#2ECC71", "Resolved"),
            "closed":       ("#7F8C8D", "Closed"),
        }

        for c in complaints:
            status_val = c.status.value if c.status else "open"
            color, status_label = STATUS_COLORS.get(status_val, ("#7F8C8D", "Unknown"))
            cat = c.category.value.replace("_", " ").title() if c.category else "General"

            card = tb.Frame(self._tab_complaints, padding=(12, 10))
            card.pack(fill=X, pady=(0, 8))

            bar = tb.Frame(card, width=4)
            bar.pack(side=LEFT, fill=Y, padx=(0, 12))
            bar.pack_propagate(False)

            content_frame = tb.Frame(card)
            content_frame.pack(side=LEFT, fill=X, expand=YES)

            title_row = tb.Frame(content_frame)
            title_row.pack(fill=X)
            tb.Label(title_row, text=c.subject,
                     font=("Helvetica", 12, "bold")).pack(side=LEFT)
            tb.Label(title_row, text=status_label,
                     font=("Helvetica", 10), foreground=color).pack(side=RIGHT)

            sub_row = tb.Frame(content_frame)
            sub_row.pack(fill=X, pady=(2, 0))
            tb.Label(sub_row, text=f"Category: {cat}",
                     font=("Helvetica", 10), bootstyle="secondary").pack(side=LEFT)

            if c.resolution_notes and status_val in ("resolved", "closed"):
                res_row = tb.Frame(content_frame)
                res_row.pack(fill=X, pady=(2, 0))
                tb.Label(res_row, text=f"Resolution: {c.resolution_notes}",
                         font=("Helvetica", 10), bootstyle="success",
                         wraplength=500, justify=LEFT).pack(side=LEFT)

            tb.Separator(self._tab_complaints, orient=HORIZONTAL).pack(fill=X)

    # ── Dialogs ─────────────────────────────────────────────────────────────
    def _request_termination(self):
        if not self.tenant_id:
            Messagebox.show_warning("Account not linked to a tenant record.", title="Error")
            return
        lease = self._get_active_lease()
        if not lease:
            Messagebox.show_warning("No active lease found.", title="No Lease")
            return
        from app.ui.tenant_termination_request_dialog import TenantTerminationRequestDialog
        dlg = TenantTerminationRequestDialog(self, user=self.user,
                                              tenant_id=self.tenant_id)
        self.wait_window(dlg)
        self._refresh_db()
        self._load_overview()

    def _open_payment_dialog(self, invoice_id: int | None = None):
        dlg = _TenantPaymentDialog(self, tenant_id=self.tenant_id,
                                   db=self.db, invoice_id=invoice_id)
        self.wait_window(dlg)
        self._refresh_db()
        self._load_payments()
        self._load_charts()
        self._load_overview()

    def _open_maintenance_dialog(self):
        if not self.tenant_id:
            Messagebox.show_warning(
                "Your account is not linked to a tenant record.\n"
                "Please ask an admin to link your user account to your tenant profile.",
                title="Account Not Linked"
            )
            return
        lease = self._get_active_lease()
        if not lease:
            Messagebox.show_warning("You need an active lease to report a repair.",
                                    title="No Lease")
            return
        dlg = _TenantMaintenanceDialog(self, tenant_id=self.tenant_id,
                                        apartment_id=lease.apartment_id,
                                        user_id=getattr(self.user, "id", None),
                                        db=self.db)
        self.wait_window(dlg)
        self._refresh_db()
        self._load_maintenance()

    def _open_complaint_dialog(self):
        if not self.tenant_id:
            Messagebox.show_warning(
                "Your account is not linked to a tenant record.\n"
                "Please ask an admin to link your user account to your tenant profile.",
                title="Account Not Linked"
            )
            return
        dlg = _TenantComplaintDialog(self, tenant_id=self.tenant_id,
                                      user_id=getattr(self.user, "id", None),
                                      db=self.db)
        self.wait_window(dlg)
        self._refresh_db()
        self._load_complaints()

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _get_active_lease(self) -> LeaseAgreement | None:
        return (
            self.db.query(LeaseAgreement)
            .options(
                joinedload(LeaseAgreement.apartment)
                .joinedload(Apartment.property)
            )
            .filter(
                LeaseAgreement.tenant_id == self.tenant_id,
                LeaseAgreement.status == LeaseStatus.ACTIVE,
            )
            .first()
        )


# ── Tenant Payment Dialog ─────────────────────────────────────────────────────

class _TenantPaymentDialog(tb.Toplevel):

    def __init__(self, parent, tenant_id, db, invoice_id=None):
        super().__init__(parent)
        self.tenant_id  = tenant_id
        self.db         = db
        self.invoice_id = invoice_id
        self.title("Make Payment")
        self.resizable(False, False)
        self.grab_set()
        self._invoice_map: dict[str, int] = {}
        self._build_ui()
        self._load_invoices()
        self._center(parent)
        if invoice_id:
            self._preselect(invoice_id)

    def _build_ui(self):
        self.geometry("480x580")

        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="💳  Process Payment", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Make Payment",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 4))
        tb.Label(f, text="Card details are simulated — no real transaction occurs.",
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(0, 16))

        def lbl(t):
            tb.Label(f, text=t, font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

        lbl("Invoice *")
        self.v_inv = tb.StringVar()
        self._combo = tb.Combobox(f, textvariable=self.v_inv, state="readonly",
                                  font=("Helvetica", 12))
        self._combo.pack(fill=X, pady=(2, 4))
        self._combo.bind("<<ComboboxSelected>>", self._on_inv_selected)

        self._detail_var = tb.StringVar(value="Select an invoice above")
        tb.Label(f, textvariable=self._detail_var, font=("Helvetica", 10),
                 bootstyle="info", justify=LEFT, wraplength=400).pack(anchor=W, pady=(0, 10))

        lbl("Amount (£) *")
        self.v_amount = tb.Entry(f, font=("Helvetica", 12))
        self.v_amount.pack(fill=X, pady=(2, 10))

        lbl("Card Number (16 digits)")
        self.v_card = tb.Entry(f, font=("Helvetica", 12))
        self.v_card.pack(fill=X, pady=(2, 10))

        row = tb.Frame(f)
        row.pack(fill=X, pady=(0, 10))
        left = tb.Frame(row)
        left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right = tb.Frame(row)
        right.pack(side=RIGHT, fill=X, expand=YES)

        lbl2 = lambda p, t: tb.Label(p, text=t, font=("Helvetica", 10),
                                      bootstyle="secondary").pack(anchor=W)
        lbl2(left, "Expiry (MM/YY)")
        self.v_expiry = tb.Entry(left, font=("Helvetica", 12))
        self.v_expiry.pack(fill=X, pady=(2, 0))

        lbl2(right, "CVV")
        self.v_cvv = tb.Entry(right, font=("Helvetica", 12), show="•")
        self.v_cvv.pack(fill=X, pady=(2, 0))

    def _load_invoices(self):
        invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.tenant_id == self.tenant_id,
                Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE]),
            )
            .order_by(Invoice.due_date)
            .all()
        )
        inv_ids = [i.id for i in invoices]
        paid_map: dict[int, Decimal] = {}
        if inv_ids:
            rows = (
                self.db.query(Payment.invoice_id, func.sum(Payment.amount))
                .filter(Payment.invoice_id.in_(inv_ids))
                .group_by(Payment.invoice_id)
                .all()
            )
            paid_map = {r[0]: r[1] or Decimal("0") for r in rows}

        self._invoice_map = {}
        for inv in invoices:
            remaining = max(inv.amount - paid_map.get(inv.id, Decimal("0")), Decimal("0"))
            label = f"{inv.invoice_number}  (Balance: £{float(remaining):,.2f})"
            self._invoice_map[label] = inv.id
        self._combo.configure(values=list(self._invoice_map.keys()))

    def _preselect(self, invoice_id):
        for label, iid in self._invoice_map.items():
            if iid == invoice_id:
                self.v_inv.set(label)
                self._on_inv_selected()
                break

    def _on_inv_selected(self, _=None):
        label = self.v_inv.get()
        if label not in self._invoice_map:
            return
        inv_id = self._invoice_map[label]
        inv = self.db.query(Invoice).filter(Invoice.id == inv_id).first()
        if not inv:
            return
        paid = (self.db.query(func.sum(Payment.amount))
                .filter(Payment.invoice_id == inv_id).scalar() or Decimal("0"))
        remaining = max(inv.amount - paid, Decimal("0"))
        self.v_amount.delete(0, END)
        self.v_amount.insert(0, str(remaining))
        period = ""
        if inv.billing_period_start and inv.billing_period_end:
            period = f"\nPeriod: {inv.billing_period_start.strftime('%d %b')} – {inv.billing_period_end.strftime('%d %b %Y')}"
        self._detail_var.set(
            f"Total: £{inv.amount:,.2f}  |  Paid: £{float(paid):,.2f}  |  Remaining: £{float(remaining):,.2f}"
            + period
        )

    def _center(self, parent):
        self.update_idletasks()
        w, h = 480, 580
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        label = self.v_inv.get()
        if not label or label not in self._invoice_map:
            Messagebox.show_warning("Please select an invoice.", title="Validation", parent=self)
            return

        try:
            amount = Decimal(self.v_amount.get().strip())
        except Exception:
            Messagebox.show_warning("Invalid amount.", title="Validation", parent=self)
            return

        card = self.v_card.get().replace(" ", "").replace("-", "")
        if not re.match(r"^\d{16}$", card):
            Messagebox.show_warning("Card number must be 16 digits.", title="Validation", parent=self)
            return
        if not re.match(r"^\d{2}/\d{2}$", self.v_expiry.get().strip()):
            Messagebox.show_warning("Expiry must be MM/YY.", title="Validation", parent=self)
            return
        if not re.match(r"^\d{3}$", self.v_cvv.get().strip()):
            Messagebox.show_warning("CVV must be 3 digits.", title="Validation", parent=self)
            return

        invoice_id = self._invoice_map[label]
        payment, error = record_payment(
            self.db,
            invoice_id=invoice_id,
            amount=amount,
            payment_method="card",
            card_last_four=card[-4:],
        )
        if error:
            Messagebox.show_warning(error, title="Payment Failed", parent=self)
            return

        receipt_num = "—"
        from app.db.models import PaymentReceipt
        r = self.db.query(PaymentReceipt).filter(
            PaymentReceipt.payment_id == payment.id
        ).first()
        if r:
            receipt_num = r.receipt_number

        parent_win = self.master
        self.destroy()
        Messagebox.show_info(
            f"Payment successful!\nReceipt: {receipt_num}\nAmount: £{amount:,.2f}",
            title="Payment Confirmed",
            parent=parent_win,
        )


# ── Tenant Maintenance Dialog ─────────────────────────────────────────────────

class _TenantMaintenanceDialog(tb.Toplevel):

    def __init__(self, parent, tenant_id, apartment_id, user_id, db):
        super().__init__(parent)
        self.tenant_id    = tenant_id
        self.apartment_id = apartment_id
        self.user_id      = user_id
        self.db           = db
        self.title("Report a Repair")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("460x400")

        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Submit Request", bootstyle="warning",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Report a Repair",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 16))

        def lbl(t):
            tb.Label(f, text=t, font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

        lbl("Title / Issue Summary *")
        self.v_title = tb.Entry(f, font=("Helvetica", 12))
        self.v_title.pack(fill=X, pady=(2, 10))

        lbl("Priority")
        self.v_priority = tb.StringVar(value="Medium")
        tb.Combobox(f, textvariable=self.v_priority,
                    values=["Low", "Medium", "High", "Urgent"],
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 10))

        lbl("Description")
        self.v_desc = tb.Text(f, font=("Helvetica", 12), height=4)
        self.v_desc.pack(fill=X, pady=(2, 0))

    def _center(self, parent):
        self.update_idletasks()
        w, h = 460, 400
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        title = self.v_title.get().strip()
        if not title:
            Messagebox.show_warning("Please enter a title.", title="Validation", parent=self)
            return

        ticket, err = create_ticket(
            self.db,
            apartment_id=self.apartment_id,
            title=title,
            description=self.v_desc.get("1.0", "end").strip() or None,
            priority=self.v_priority.get().lower(),
            tenant_id=self.tenant_id,
            raised_by_user_id=self.user_id,
        )
        if err:
            Messagebox.show_warning(err, title="Error", parent=self)
            return

        parent_win = self.master
        self.destroy()
        Messagebox.show_info(
            f"Repair request submitted!\nTicket #{ticket.id} has been logged.",
            title="Request Submitted",
            parent=parent_win,
        )


# ── Tenant Complaint Dialog ───────────────────────────────────────────────────

class _TenantComplaintDialog(tb.Toplevel):

    def __init__(self, parent, tenant_id, user_id, db):
        super().__init__(parent)
        self.tenant_id = tenant_id
        self.user_id   = user_id
        self.db        = db
        self.title("Submit Complaint")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        self.geometry("460x400")

        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Submit", bootstyle="danger",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Submit a Complaint",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 16))

        def lbl(t):
            tb.Label(f, text=t, font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W)

        lbl("Category *")
        self.v_category = tb.StringVar(value="Noise")
        tb.Combobox(f, textvariable=self.v_category,
                    values=["Noise", "Maintenance", "Neighbour",
                            "Billing", "Staff Conduct", "Other"],
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 10))

        lbl("Subject *")
        self.v_subject = tb.Entry(f, font=("Helvetica", 12))
        self.v_subject.pack(fill=X, pady=(2, 10))

        lbl("Description")
        self.v_desc = tb.Text(f, font=("Helvetica", 12), height=4)
        self.v_desc.pack(fill=X, pady=(2, 0))

    def _center(self, parent):
        self.update_idletasks()
        w, h = 460, 400
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _submit(self):
        cat_map = {
            "Noise": "noise", "Maintenance": "maintenance", "Neighbour": "neighbour",
            "Billing": "billing", "Staff Conduct": "staff_conduct", "Other": "other",
        }
        subject = self.v_subject.get().strip()
        if not subject:
            Messagebox.show_warning("Please enter a subject.", title="Validation", parent=self)
            return

        complaint, err = create_complaint(
            self.db,
            tenant_id=self.tenant_id,
            category=cat_map.get(self.v_category.get(), "other"),
            subject=subject,
            description=self.v_desc.get("1.0", "end").strip() or None,
            raised_by_user_id=self.user_id,
        )
        if err:
            Messagebox.show_warning(err, title="Error", parent=self)
            return

        parent_win = self.master
        self.destroy()
        Messagebox.show_info(
            f"Complaint #{complaint.id} submitted successfully.",
            title="Complaint Submitted",
            parent=parent_win,
        )