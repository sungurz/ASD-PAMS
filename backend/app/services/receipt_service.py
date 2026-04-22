# Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
Auto-generates a receipt after every successful payment.
Receipt number format: RCP-YYYY-NNNN
"""

from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.db.models import Payment, PaymentReceipt, Invoice, InvoiceStatus


def _next_receipt_number(db: Session) -> str:
    year   = date.today().year
    prefix = f"RCP-{year}-"
    last   = (
        db.query(PaymentReceipt)
        .filter(PaymentReceipt.receipt_number.like(f"{prefix}%"))
        .order_by(PaymentReceipt.id.desc())
        .first()
    )
    seq = int(last.receipt_number.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def create_receipt(
    db: Session,
    payment: Payment,
) -> PaymentReceipt:
    """Create and persist a receipt for a payment. Called by payment_service."""
    receipt = PaymentReceipt(
        payment_id=payment.id,
        receipt_number=_next_receipt_number(db),
        amount=payment.amount,
        notes=f"Payment for Invoice #{payment.invoice_id}",
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt