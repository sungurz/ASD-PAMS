"""
app/ui/finance_page.py
=======================
Finance module — three tabs:
  1. Invoices   — list, generate, void
  2. Payments   — payment history
  3. Arrears    — overdue invoices with days overdue
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from datetime import date
import calendar

from app.db.database import SessionLocal
from app.db.models import Invoice, InvoiceStatus, Payment, LatePaymentAlert, Tenant
from app.services.invoice_service import (
    generate_monthly_invoices, get_unpaid_invoices, void_invoice, mark_overdue
)
from app.services.late_payment_service import run_overdue_scan, get_active_alerts
from sqlalchemy.orm import joinedload


STATUS_COLORS = {
    "draft":   "#7F8C8D",
    "issued":  "#3498DB",
    "paid":    "#2ECC71",
    "overdue": "#E74C3C",
    "void":    "#7F8C8D",
}


class FinancePage(tb.Frame):
    """Finance management page."""

    def __init__(self, parent, user):
        super().__init__(parent)
        self.user = user
        self.db   = SessionLocal()
        self._build_ui()
        self._refresh_all()

    # ── Layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = tb.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill=X)
        tb.Label(header, text="Finance",
                 font=("Georgia", 20, "bold")).pack(side=LEFT)

        # Run overdue scan button
        tb.Button(header, text="🔄  Scan Overdue",
                  bootstyle="warning", padding=(10, 6),
                  command=self._run_overdue_scan).pack(side=RIGHT, padx=(6, 0))

        if self.user.has_permission("invoice.create"):
            tb.Button(header, text="⚡  Generate Monthly Invoices",
                      bootstyle="success", padding=(10, 6),
                      command=self._generate_monthly).pack(side=RIGHT, padx=(6, 0))

        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=20)

        # Notebook
        self.nb = tb.Notebook(self, bootstyle="primary")
        self.nb.pack(fill=BOTH, expand=YES, padx=0, pady=0)

        self._tab_invoices = tb.Frame(self.nb)
        self._tab_payments = tb.Frame(self.nb)
        self._tab_arrears  = tb.Frame(self.nb)

        self.nb.add(self._tab_invoices, text="  Invoices  ")
        self.nb.add(self._tab_payments, text="  Payments  ")
        self.nb.add(self._tab_arrears,  text="  Arrears  ")

        self._build_invoices_tab()
        self._build_payments_tab()
        self._build_arrears_tab()

    # ── Invoices tab ──────────────────────────────────────────────────────
    def _build_invoices_tab(self):
        f = self._tab_invoices

        # Toolbar
        bar = tb.Frame(f, padding=(12, 10, 12, 6))
        bar.pack(fill=X)

        # Status filter
        tb.Label(bar, text="Status:", font=("Helvetica", 11)).pack(side=LEFT)
        self._inv_status_var = tb.StringVar(value="All")
        tb.Combobox(bar, textvariable=self._inv_status_var,
                    values=["All", "Issued", "Paid", "Overdue", "Draft", "Void"],
                    state="readonly", font=("Helvetica", 11), width=12).pack(side=LEFT, padx=(6, 16))
        self._inv_status_var.trace_add("write", lambda *_: self.load_invoices())

        if self.user.has_permission("invoice.void"):
            tb.Button(bar, text="🚫  Void Selected",
                      bootstyle="danger-outline", padding=(8, 4),
                      command=self._void_selected).pack(side=LEFT, padx=(0, 6))

        if self.user.has_permission("payment.create"):
            tb.Button(bar, text="💳  Record Payment",
                      bootstyle="primary", padding=(8, 4),
                      command=self._open_payment_dialog).pack(side=LEFT)

        # Table
        tbl_frame = tb.Frame(f, padding=(12, 4, 12, 0))
        tbl_frame.pack(fill=BOTH, expand=YES)

        cols = ("id", "invoice_num", "tenant", "period", "amount", "paid", "remaining", "due_date", "status")
        self.inv_tree = tb.Treeview(tbl_frame, columns=cols, show="headings",
                                    bootstyle="dark", selectmode="browse")

        col_cfg = [
            ("id",          "ID",          50,  CENTER),
            ("invoice_num", "Invoice #",   120, W),
            ("tenant",      "Tenant",      160, W),
            ("period",      "Period",      120, CENTER),
            ("amount",      "Total",       90,  CENTER),
            ("paid",        "Paid",        90,  CENTER),
            ("remaining",   "Remaining",   90,  CENTER),
            ("due_date",    "Due Date",    100, CENTER),
            ("status",      "Status",      90,  CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self.inv_tree.heading(cid, text=heading, anchor=anchor)
            self.inv_tree.column(cid, width=width, anchor=anchor, minwidth=40)

        for status, color in STATUS_COLORS.items():
            self.inv_tree.tag_configure(status, foreground=color)

        sb = tb.Scrollbar(tbl_frame, orient=VERTICAL, command=self.inv_tree.yview, bootstyle="round-dark")
        self.inv_tree.configure(yscrollcommand=sb.set)
        self.inv_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        self._inv_count = tb.StringVar()
        tb.Label(f, textvariable=self._inv_count, font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=E, padx=16, pady=(4, 8))

    # ── Payments tab ──────────────────────────────────────────────────────
    def _build_payments_tab(self):
        f = self._tab_payments

        tbl_frame = tb.Frame(f, padding=12)
        tbl_frame.pack(fill=BOTH, expand=YES)

        cols = ("id", "receipt", "tenant", "invoice", "amount", "method", "date")
        self.pay_tree = tb.Treeview(tbl_frame, columns=cols, show="headings",
                                    bootstyle="dark", selectmode="browse")

        col_cfg = [
            ("id",      "ID",         50,  CENTER),
            ("receipt", "Receipt #",  130, W),
            ("tenant",  "Tenant",     200, W),
            ("invoice", "Invoice #",  130, W),
            ("amount",  "Amount",     90,  CENTER),
            ("method",  "Method",     110, CENTER),
            ("date",    "Date",       140, CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self.pay_tree.heading(cid, text=heading, anchor=anchor)
            self.pay_tree.column(cid, width=width, anchor=anchor, minwidth=40)

        sb = tb.Scrollbar(tbl_frame, orient=VERTICAL, command=self.pay_tree.yview, bootstyle="round-dark")
        self.pay_tree.configure(yscrollcommand=sb.set)
        self.pay_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        self._pay_count = tb.StringVar()
        tb.Label(f, textvariable=self._pay_count, font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=E, padx=16, pady=(4, 8))

    # ── Arrears tab ───────────────────────────────────────────────────────
    def _build_arrears_tab(self):
        f = self._tab_arrears

        info = tb.Frame(f, padding=(12, 10, 12, 4))
        info.pack(fill=X)
        tb.Label(info, text="Tenants with overdue invoices. Click 'Scan Overdue' to refresh.",
                 font=("Helvetica", 10), bootstyle="secondary").pack(side=LEFT)

        tbl_frame = tb.Frame(f, padding=(12, 4, 12, 0))
        tbl_frame.pack(fill=BOTH, expand=YES)

        cols = ("id", "tenant", "invoice_num", "amount", "due_date", "days_overdue")
        self.arr_tree = tb.Treeview(tbl_frame, columns=cols, show="headings",
                                    bootstyle="dark", selectmode="browse")

        col_cfg = [
            ("id",           "ID",          50,  CENTER),
            ("tenant",       "Tenant",      200, W),
            ("invoice_num",  "Invoice #",   130, W),
            ("amount",       "Amount",      90,  CENTER),
            ("due_date",     "Due Date",    100, CENTER),
            ("days_overdue", "Days Overdue",100, CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self.arr_tree.heading(cid, text=heading, anchor=anchor)
            self.arr_tree.column(cid, width=width, anchor=anchor, minwidth=40)

        self.arr_tree.tag_configure("critical", foreground="#E74C3C")
        self.arr_tree.tag_configure("warning",  foreground="#E67E22")

        sb = tb.Scrollbar(tbl_frame, orient=VERTICAL, command=self.arr_tree.yview, bootstyle="round-dark")
        self.arr_tree.configure(yscrollcommand=sb.set)
        self.arr_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        sb.pack(side=RIGHT, fill=Y)

        self._arr_count = tb.StringVar()
        tb.Label(f, textvariable=self._arr_count, font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=E, padx=16, pady=(4, 8))

    # ── Data loading ──────────────────────────────────────────────────────
    def _refresh_all(self):
        self.db.close()
        self.db = SessionLocal()
        self.load_invoices()
        self.load_payments()
        self.load_arrears()

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

    def load_invoices(self, *_):
        self._refresh_db()
        for row in self.inv_tree.get_children():
            self.inv_tree.delete(row)

        q = self.db.query(Invoice).options(joinedload(Invoice.tenant))
        status_filter = self._inv_status_var.get()
        if status_filter != "All":
            q = q.filter(Invoice.status == InvoiceStatus(status_filter.lower()))
        invoices = q.order_by(Invoice.due_date.desc()).all()

        from app.db.models import Payment as _Payment
        from sqlalchemy import func as _func
        from decimal import Decimal as _Dec

        # Batch load total paid per invoice
        paid_rows = (
            self.db.query(_Payment.invoice_id, _func.sum(_Payment.amount))
            .group_by(_Payment.invoice_id)
            .all()
        )
        paid_map = {row[0]: row[1] or _Dec("0") for row in paid_rows}

        for inv in invoices:
            tenant_name = inv.tenant.full_name if inv.tenant else "—"
            period = ""
            if inv.billing_period_start and inv.billing_period_end:
                period = f"{inv.billing_period_start.strftime('%d %b')}–{inv.billing_period_end.strftime('%d %b %Y')}"
            tag = inv.status.value if inv.status else "draft"
            paid      = paid_map.get(inv.id, _Dec("0"))
            remaining = max(inv.amount - paid, _Dec("0"))
            self.inv_tree.insert("", END, tags=(tag,), values=(
                inv.id,
                inv.invoice_number,
                tenant_name,
                period,
                f"£{inv.amount:,.2f}",
                f"£{paid:,.2f}",
                f"£{remaining:,.2f}",
                inv.due_date.strftime("%d %b %Y") if inv.due_date else "—",
                inv.status.value.title() if inv.status else "—",
            ))

        self._inv_count.set(f"{len(invoices)} invoice(s)")

    def load_payments(self):
        for row in self.pay_tree.get_children():
            self.pay_tree.delete(row)

        from app.db.models import Payment, PaymentReceipt
        payments = (
            self.db.query(Payment)
            .options(joinedload(Payment.invoice), joinedload(Payment.receipt))
            .order_by(Payment.payment_date.desc())
            .limit(200)
            .all()
        )

        for p in payments:
            tenant = self.db.query(Tenant).filter(Tenant.id == p.tenant_id).first()
            receipt_num = p.receipt.receipt_number if hasattr(p, "receipt") and p.receipt else "—"
            self.pay_tree.insert("", END, values=(
                p.id,
                receipt_num,
                tenant.full_name if tenant else "—",
                p.invoice.invoice_number if p.invoice else "—",
                f"£{p.amount:,.2f}",
                p.payment_method.value.replace("_", " ").title() if p.payment_method else "—",
                p.payment_date.strftime("%d %b %Y %H:%M") if p.payment_date else "—",
            ))

        self._pay_count.set(f"{len(payments)} payment(s)")

    def load_arrears(self):
        for row in self.arr_tree.get_children():
            self.arr_tree.delete(row)

        alerts = get_active_alerts(self.db)

        for alert in alerts:
            inv    = alert.invoice
            tenant = self.db.query(Tenant).filter(Tenant.id == alert.tenant_id).first()
            tag    = "critical" if alert.days_overdue > 14 else "warning"
            self.arr_tree.insert("", END, tags=(tag,), values=(
                alert.id,
                tenant.full_name if tenant else "—",
                inv.invoice_number if inv else "—",
                f"£{inv.amount:,.2f}" if inv else "—",
                inv.due_date.strftime("%d %b %Y") if inv and inv.due_date else "—",
                f"{alert.days_overdue} days",
            ))

        self._arr_count.set(f"{len(alerts)} overdue account(s)")

    # ── Actions ───────────────────────────────────────────────────────────
    def _generate_monthly(self):
        today = date.today()
        dlg = _GenerateInvoicesDialog(self, user=self.user, month=today.month, year=today.year)
        self.wait_window(dlg)
        self._refresh_all()

    def _run_overdue_scan(self):
        count = run_overdue_scan(self.db)
        self._refresh_all()
        Messagebox.show_info(
            f"Scan complete. {count} invoice(s) marked overdue.",
            title="Overdue Scan"
        )

    def _void_selected(self):
        sel = self.inv_tree.selection()
        if not sel:
            Messagebox.show_warning("Please select an invoice to void.", title="No Selection")
            return
        inv_id = int(self.inv_tree.item(sel[0])["values"][0])
        confirm = Messagebox.yesno("Void this invoice? This cannot be undone.", title="Confirm Void")
        if confirm == "Yes":
            ok, err = void_invoice(self.db, inv_id)
            if err:
                Messagebox.show_warning(err, title="Cannot Void")
            else:
                self.load_invoices()

    def _open_payment_dialog(self):
        sel = self.inv_tree.selection()
        inv_id = None
        if sel:
            inv_id = int(self.inv_tree.item(sel[0])["values"][0])
        from app.ui.payment_dialog import PaymentDialog
        dlg = PaymentDialog(self, user=self.user, invoice_id=inv_id)
        self.wait_window(dlg)
        self._refresh_all()


# ── Generate Invoices Dialog ──────────────────────────────────────────────────

class _GenerateInvoicesDialog(tb.Toplevel):
    def __init__(self, parent, user, month: int, year: int):
        super().__init__(parent)
        self.user  = user
        self.db    = SessionLocal()
        self.title("Generate Monthly Invoices")
        self.resizable(False, False)
        self.grab_set()
        self.geometry("380x280")

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Generate Monthly Invoices",
                 font=("Georgia", 15, "bold")).pack(anchor=W, pady=(0, 16))

        row = tb.Frame(f)
        row.pack(fill=X, pady=(0, 12))

        left = tb.Frame(row)
        left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right = tb.Frame(row)
        right.pack(side=RIGHT, fill=X, expand=YES)

        tb.Label(left, text="Month", bootstyle="secondary",
                 font=("Helvetica", 10)).pack(anchor=W)
        self.v_month = tb.StringVar(value=str(month))
        tb.Combobox(left, textvariable=self.v_month,
                    values=[str(i) for i in range(1, 13)],
                    state="readonly", font=("Helvetica", 12)).pack(fill=X, pady=(2, 0))

        tb.Label(right, text="Year", bootstyle="secondary",
                 font=("Helvetica", 10)).pack(anchor=W)
        self.v_year = tb.Entry(right, font=("Helvetica", 12))
        self.v_year.insert(0, str(year))
        self.v_year.pack(fill=X, pady=(2, 0))

        tb.Label(f, text="This will generate invoices for all active leases\nin the selected period.",
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(0, 16))

        btn_row = tb.Frame(f)
        btn_row.pack(fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Generate", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

        # center
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - 380) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 280) // 2
        self.geometry(f"380x280+{px}+{py}")

    def _submit(self):
        try:
            month = int(self.v_month.get())
            year  = int(self.v_year.get())
        except ValueError:
            Messagebox.show_warning("Invalid month or year.", title="Validation", parent=self)
            return

        created, errors = generate_monthly_invoices(
            self.db, month=month, year=year,
            generated_by_user_id=self.user.id
        )
        msg = f"✓ {created} invoice(s) generated."
        if errors:
            msg += f"\n\n{len(errors)} error(s):\n" + "\n".join(errors[:5])
        Messagebox.show_info(msg, title="Done", parent=self)
        self.destroy()