# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/services/late_payment_service.py
=====================================
Scans all unpaid invoices past their due date and creates
LatePaymentAlert rows. Called on dashboard load or manually.
"""

from __future__ import annotations
from datetime import date, datetime
from sqlalchemy.orm import Session

from app.db.models import Invoice, InvoiceStatus, LatePaymentAlert


def run_overdue_scan(db: Session) -> int:
    """
    Check all ISSUED/OVERDUE invoices. For each one past due_date:
      - Update status to OVERDUE
      - Create or update a LatePaymentAlert
    Returns number of alerts created/updated.
    """
    today = date.today()

    unpaid = db.query(Invoice).filter(
        Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE]),
        Invoice.due_date < today,
    ).all()

    count = 0
    for inv in unpaid:
        inv.status   = InvoiceStatus.OVERDUE
        days_overdue = (today - inv.due_date).days

        alert = db.query(LatePaymentAlert).filter(
            LatePaymentAlert.invoice_id == inv.id,
            LatePaymentAlert.is_resolved == False,
        ).first()

        if not alert:
            db.add(LatePaymentAlert(
                invoice_id=inv.id,
                tenant_id=inv.tenant_id,
                days_overdue=days_overdue,
                alert_date=datetime.now(),
            ))
        else:
            alert.days_overdue = days_overdue

        count += 1

    if count:
        db.commit()
    return count


def get_active_alerts(
    db: Session,
    city_id: int | None = None,
) -> list[LatePaymentAlert]:
    """Return all unresolved late payment alerts, optionally city-scoped."""
    from app.db.models import Invoice, LeaseAgreement, Apartment, Property
    from sqlalchemy.orm import joinedload

    q = (
        db.query(LatePaymentAlert)
        .options(
            joinedload(LatePaymentAlert.invoice),
        )
        .filter(LatePaymentAlert.is_resolved == False)
    )

    if city_id:
        q = (
            q.join(LatePaymentAlert.invoice)
            .join(Invoice.lease)
            .join(LeaseAgreement.apartment)
            .join(Apartment.property)
            .filter(Property.city_id == city_id)
        )

    return q.order_by(LatePaymentAlert.days_overdue.desc()).all()