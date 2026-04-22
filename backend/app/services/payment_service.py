# Ahmet (24034408)
"""
app/services/payment_service.py
================================
Records a payment against an invoice, updates invoice status,
and auto-generates a receipt. Card flow is fully simulated.
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Payment, Invoice, InvoiceStatus, PaymentMethod, LatePaymentAlert
)
from app.services.receipt_service import create_receipt


def record_payment(
    db: Session,
    *,
    invoice_id: int,
    amount: Decimal,
    payment_method: str,
    recorded_by_user_id: int | None = None,
    card_last_four: str | None = None,
    reference: str | None = None,
    notes: str | None = None,
) -> tuple[Payment | None, str]:
    """
    Record a payment against an invoice.
    - Partial payments allowed.
    - If total payments >= invoice amount → mark PAID.
    - Auto-generates a receipt.
    - Resolves any open LatePaymentAlert.
    Returns (payment, "") on success, (None, error) on failure.
    """
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        return None, "Invoice not found."
    if invoice.status == InvoiceStatus.PAID:
        return None, "This invoice is already fully paid."
    if invoice.status == InvoiceStatus.VOID:
        return None, "Cannot pay a voided invoice."

    if amount <= 0:
        return None, "Payment amount must be greater than zero."
    if amount > invoice.amount:
        return None, f"Payment exceeds invoice amount of £{invoice.amount:,.2f}."

    # Build reference string
    if card_last_four:
        ref = f"**** **** **** {card_last_four}"
    else:
        ref = reference or ""

    try:
        method = PaymentMethod(payment_method)
    except ValueError:
        method = PaymentMethod.CARD

    payment = Payment(
        invoice_id=invoice_id,
        tenant_id=invoice.tenant_id,
        recorded_by=recorded_by_user_id,
        amount=amount,
        payment_method=method,
        payment_date=datetime.now(),
        reference=ref,
        notes=notes,
    )
    db.add(payment)
    db.flush()

    # Check if fully paid
    total_paid = (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice_id)
        .with_entities(__import__("sqlalchemy", fromlist=["func"]).func.sum(Payment.amount))
        .scalar() or Decimal("0")
    )

    if total_paid >= invoice.amount:
        invoice.status = InvoiceStatus.PAID
        # Resolve any open late payment alert
        alert = db.query(LatePaymentAlert).filter(
            LatePaymentAlert.invoice_id == invoice_id,
            LatePaymentAlert.is_resolved == False,
        ).first()
        if alert:
            alert.is_resolved = True
            alert.resolved_at = datetime.now()

    db.commit()
    db.refresh(payment)

    # Auto-generate receipt
    create_receipt(db, payment)

    try:
        from app.services.audit_service import log_action, AuditAction
        log_action(db, action=AuditAction.PAYMENT_RECORD,
                   entity="payment", entity_id=payment.id,
                   detail=f"Invoice: {invoice_id} | Amount: £{amount:,.2f} | "
                          f"Method: {payment_method}")
    except Exception:
        pass

    return payment, ""


def get_payments_for_invoice(db: Session, invoice_id: int) -> list[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice_id)
        .order_by(Payment.payment_date.desc())
        .all()
    )


def get_payments_for_tenant(db: Session, tenant_id: int) -> list[Payment]:
    return (
        db.query(Payment)
        .options(joinedload(Payment.invoice))
        .filter(Payment.tenant_id == tenant_id)
        .order_by(Payment.payment_date.desc())
        .all()
    )