"""
app/ui/payment_dialog.py
=========================
Simulated card payment dialog.
Validates card number (16 digits), expiry (MM/YY), CVV (3 digits).
No real gateway — just records the payment in the DB.
"""

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from decimal import Decimal
import re

from app.db.database import SessionLocal
from app.db.models import Invoice, InvoiceStatus, Tenant
from app.services.payment_service import record_payment
from sqlalchemy.orm import joinedload


class PaymentDialog(tb.Toplevel):
    """Simulated card payment dialog."""

    def __init__(self, parent, user, invoice_id: int | None = None):
        super().__init__(parent)
        self.user       = user
        self.db         = SessionLocal()
        self.invoice_id = invoice_id
        self._card_frame = None   # ← initialize before _build_ui

        self.title("Record Payment")
        self.resizable(False, False)
        self.grab_set()

        self._invoice_map: dict[str, int] = {}
        self._build_ui()
        self._load_invoices()
        self._center(parent)

        if invoice_id:
            self._preselect_invoice(invoice_id)

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.geometry("460x580")

        # Buttons FIRST — anchors to bottom
        btn_row = tb.Frame(self, padding=(24, 0, 24, 16))
        btn_row.pack(side=BOTTOM, fill=X)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary",
                  command=self.destroy).pack(side=RIGHT, padx=(6, 0))
        tb.Button(btn_row, text="Process Payment", bootstyle="success",
                  command=self._submit).pack(side=RIGHT)

        f = tb.Frame(self, padding=24)
        f.pack(fill=BOTH, expand=YES)

        tb.Label(f, text="Record Payment",
                 font=("Georgia", 16, "bold")).pack(anchor=W, pady=(0, 4))
        tb.Label(f, text="Card details are simulated — no real transaction occurs.",
                 font=("Helvetica", 10), bootstyle="secondary").pack(anchor=W, pady=(0, 16))

        def lbl(text):
            tb.Label(f, text=text, font=("Helvetica", 10),
                     bootstyle="secondary").pack(anchor=W)

        # Invoice selector
        lbl("Invoice *")
        self.v_invoice = tb.StringVar()
        self._inv_combo = tb.Combobox(f, textvariable=self.v_invoice,
                                       state="readonly", font=("Helvetica", 12))
        self._inv_combo.pack(fill=X, pady=(2, 4))
        self._inv_combo.bind("<<ComboboxSelected>>", self._on_invoice_selected)

        # Invoice details display
        self._inv_detail = tb.StringVar(value="Select an invoice above")
        tb.Label(f, textvariable=self._inv_detail, font=("Helvetica", 10),
                 bootstyle="info").pack(anchor=W, pady=(0, 12))

        # Amount
        lbl("Amount (£) *")
        self.v_amount = tb.Entry(f, font=("Helvetica", 12))
        self.v_amount.pack(fill=X, pady=(2, 12))

        # Payment method
        lbl("Payment Method")
        self.v_method = tb.StringVar(value="Card")
        method_frame = tb.Frame(f)
        method_frame.pack(fill=X, pady=(2, 12))
        for method in ["Card", "Bank Transfer", "Cash"]:
            tb.Radiobutton(method_frame, text=method, variable=self.v_method,
                           value=method, bootstyle="primary").pack(side=LEFT, padx=(0, 16))
        self.v_method.trace_add("write", self._toggle_card_fields)

        # Card details frame
        self._card_frame = tb.LabelFrame(f, text="Card Details")
        self._card_frame.pack(fill=X, pady=(0, 12))

        inner = tb.Frame(self._card_frame)
        inner.pack(fill=X, padx=8, pady=8)

        tb.Label(inner, text="Card Number (16 digits)", font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=W)
        self.v_card_num = tb.Entry(inner, font=("Helvetica", 12))
        self.v_card_num.pack(fill=X, pady=(2, 8))

        row = tb.Frame(inner)
        row.pack(fill=X)
        left = tb.Frame(row)
        left.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        right = tb.Frame(row)
        right.pack(side=RIGHT, fill=X, expand=YES)

        tb.Label(left, text="Expiry (MM/YY)", font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=W)
        self.v_expiry = tb.Entry(left, font=("Helvetica", 12))
        self.v_expiry.pack(fill=X, pady=(2, 0))

        tb.Label(right, text="CVV (3 digits)", font=("Helvetica", 10),
                 bootstyle="secondary").pack(anchor=W)
        self.v_cvv = tb.Entry(right, font=("Helvetica", 12), show="•")
        self.v_cvv.pack(fill=X, pady=(2, 0))

        lbl("Notes (optional)")
        self.v_notes = tb.Entry(f, font=("Helvetica", 12))
        self.v_notes.pack(fill=X, pady=(2, 0))

    # ── Data ──────────────────────────────────────────────────────────────
    def _load_invoices(self):
        invoices = (
            self.db.query(Invoice)
            .options(joinedload(Invoice.tenant))
            .filter(Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE]))
            .order_by(Invoice.due_date)
            .all()
        )
        self._invoice_map = {}
        for inv in invoices:
            tenant_name = inv.tenant.full_name if inv.tenant else "Unknown"
            label = f"{inv.invoice_number} — {tenant_name}  £{inv.amount:,.2f}"
            self._invoice_map[label] = inv.id
        self._inv_combo.configure(values=list(self._invoice_map.keys()))

    def _preselect_invoice(self, invoice_id: int):
        for label, iid in self._invoice_map.items():
            if iid == invoice_id:
                self.v_invoice.set(label)
                self._on_invoice_selected()
                break

    def _on_invoice_selected(self, _=None):
        label = self.v_invoice.get()
        if label not in self._invoice_map:
            return
        inv_id = self._invoice_map[label]
        inv = self.db.query(Invoice).filter(Invoice.id == inv_id).first()
        if inv:
            self.v_amount.delete(0, END)
            self.v_amount.insert(0, str(inv.amount))
            period = ""
            if inv.billing_period_start:
                period = f" | Period: {inv.billing_period_start.strftime('%b %Y')}"
            self._inv_detail.set(
                f"Due: {inv.due_date.strftime('%d %b %Y') if inv.due_date else '—'}"
                f"  |  Status: {inv.status.value.title()}{period}"
            )

    def _toggle_card_fields(self, *_):
        if self._card_frame is None:
            return
        if self.v_method.get() == "Card":
            self._card_frame.pack(fill=X, pady=(0, 12))
        else:
            self._card_frame.pack_forget()

    # ── Validation ────────────────────────────────────────────────────────
    def _validate_card(self) -> tuple[bool, str]:
        num = self.v_card_num.get().replace(" ", "").replace("-", "")
        if not re.match(r"^\d{16}$", num):
            return False, "Card number must be exactly 16 digits."
        expiry = self.v_expiry.get().strip()
        if not re.match(r"^\d{2}/\d{2}$", expiry):
            return False, "Expiry must be in MM/YY format."
        cvv = self.v_cvv.get().strip()
        if not re.match(r"^\d{3}$", cvv):
            return False, "CVV must be exactly 3 digits."
        return True, num[-4:]   # return last 4 digits

    # ── Helpers ───────────────────────────────────────────────────────────
    def _center(self, parent):
        self.update_idletasks()
        w, h = 460, 560
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    # ── Submit ────────────────────────────────────────────────────────────
    def _submit(self):
        inv_label = self.v_invoice.get()
        if not inv_label or inv_label not in self._invoice_map:
            Messagebox.show_warning("Please select an invoice.", title="Validation", parent=self)
            return

        amount_str = self.v_amount.get().strip()
        try:
            amount = Decimal(amount_str)
        except Exception:
            Messagebox.show_warning("Invalid amount.", title="Validation", parent=self)
            return

        method  = self.v_method.get()
        last_four = None

        if method == "Card":
            ok, result = self._validate_card()
            if not ok:
                Messagebox.show_warning(result, title="Card Validation", parent=self)
                return
            last_four = result

        method_map = {
            "Card":          "card",
            "Bank Transfer": "bank_transfer",
            "Cash":          "cash",
        }

        invoice_id = self._invoice_map[inv_label]
        payment, error = record_payment(
            self.db,
            invoice_id=invoice_id,
            amount=amount,
            payment_method=method_map[method],
            recorded_by_user_id=self.user.id,
            card_last_four=last_four,
            notes=self.v_notes.get().strip() or None,
        )

        if error:
            Messagebox.show_warning(error, title="Payment Failed", parent=self)
            return

        # Show receipt number
        receipt_num = "—"
        if hasattr(payment, "receipt") and payment.receipt:
            receipt_num = payment.receipt.receipt_number
        else:
            from app.db.models import PaymentReceipt
            r = self.db.query(PaymentReceipt).filter(
                PaymentReceipt.payment_id == payment.id
            ).first()
            if r:
                receipt_num = r.receipt_number

        Messagebox.show_info(
            f"Payment recorded successfully!\n\nReceipt: {receipt_num}\nAmount: £{amount:,.2f}",
            title="Payment Successful",
            parent=self,
        )
        self.destroy()