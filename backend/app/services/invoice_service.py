# Ahmet (24034408) 
"""
app/services/invoice_service.py
================================
Business logic for invoice generation and lifecycle.

Rules:
  - One invoice per lease per billing period (no duplicates).
  - Invoice number format: INV-YYYY-NNNN (e.g. INV-2026-0042).
  - Overdue = due_date has passed and status is still ISSUED.
  - Marking paid checks total payments >= invoice amount.
"""

from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.db.models import (
    Invoice, InvoiceStatus, LeaseAgreement, LeaseStatus,
    Tenant, LatePaymentAlert
)


# ── Number generation ─────────────────────────────────────────────────────────

def _next_invoice_number(db: Session) -> str:
    year = date.today().year
    prefix = f"INV-{year}-"
    last = (
        db.query(Invoice)
        .filter(Invoice.invoice_number.like(f"{prefix}%"))
        .order_by(Invoice.id.desc())
        .first()
    )
    if last:
        seq = int(last.invoice_number.split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


# ── Core operations ───────────────────────────────────────────────────────────

def generate_invoice(
    db: Session,
    *,
    lease_id: int,
    billing_period_start: date,
    billing_period_end: date,
    due_date: date | None = None,
    generated_by_user_id: int | None = None,
    notes: str | None = None,
    amount_override=None,
) -> tuple[Invoice | None, str]:
    """
    Generate a single invoice for a lease billing period.
    Returns (invoice, "") on success, (None, error) on failure.
    """
    lease = (
        db.query(LeaseAgreement)
        .options(joinedload(LeaseAgreement.tenant))
        .filter(LeaseAgreement.id == lease_id)
        .first()
    )
    if not lease:
        return None, "Lease not found."
    if lease.status not in (LeaseStatus.ACTIVE, LeaseStatus.PENDING_TERMINATION):
        return None, "Can only invoice active leases."

    # Duplicate check
    existing = db.query(Invoice).filter(
        Invoice.lease_id == lease_id,
        Invoice.billing_period_start == billing_period_start,
        Invoice.status != InvoiceStatus.VOID,
    ).first()
    if existing:
        return None, f"Invoice {existing.invoice_number} already exists for this period."

    if due_date is None:
        due_date = billing_period_end

    invoice = Invoice(
        lease_id=lease_id,
        tenant_id=lease.tenant_id,
        generated_by=generated_by_user_id,
        invoice_number=_next_invoice_number(db),
        amount=amount_override if amount_override is not None else lease.agreed_rent,
        due_date=due_date,
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
        status=InvoiceStatus.ISSUED,
        notes=notes,
    )
    db.add(invoice)
    db.commit()
    try:
        from app.services.audit_service import log_action, AuditAction
        log_action(db, action=AuditAction.INVOICE_GENERATE,
                   user_id=generated_by_user_id,
                   entity="invoice", entity_id=invoice.id,
                   detail=f"Invoice {invoice.invoice_number} | Lease {lease_id} | "
                          f"£{invoice.amount:,.2f}")
    except Exception:
        pass
    db.refresh(invoice)
    return invoice, ""


def generate_monthly_invoices(
    db: Session,
    *,
    month: int,
    year: int,
    generated_by_user_id: int | None = None,
    city_id: int | None = None,
) -> tuple[int, list[str]]:
    """
    Bulk-generate invoices for all active leases in a given month.
    Returns (count_created, list_of_errors).
    Skips leases that already have an invoice for this period.
    """
    from calendar import monthrange
    from app.db.models import Apartment, Property

    first_day = date(year, month, 1)
    last_day  = date(year, month, monthrange(year, month)[1])

    q = (
        db.query(LeaseAgreement)
        .filter(
            LeaseAgreement.status == LeaseStatus.ACTIVE,
            LeaseAgreement.start_date <= last_day,
            LeaseAgreement.end_date   >= first_day,
        )
    )

    if city_id:
        q = (
            q.join(LeaseAgreement.apartment)
            .join(Apartment.property)
            .filter(Property.city_id == city_id)
        )

    leases = q.all()
    created = 0
    errors  = []

    for lease in leases:
        _, err = generate_invoice(
            db,
            lease_id=lease.id,
            billing_period_start=first_day,
            billing_period_end=last_day,
            due_date=last_day,
            generated_by_user_id=generated_by_user_id,
        )
        if err and "already exists" not in err:
            errors.append(f"Lease {lease.id}: {err}")
        elif not err:
            created += 1

    return created, errors


def mark_overdue(db: Session) -> int:
    """
    Scan all ISSUED invoices past their due_date and mark them OVERDUE.
    Also creates LatePaymentAlert rows.
    Returns count of invoices updated.
    """
    today = date.today()
    overdue_invoices = db.query(Invoice).filter(
        Invoice.status == InvoiceStatus.ISSUED,
        Invoice.due_date < today,
    ).all()

    count = 0
    for inv in overdue_invoices:
        inv.status = InvoiceStatus.OVERDUE
        days = (today - inv.due_date).days

        # Create alert if not already exists
        existing_alert = db.query(LatePaymentAlert).filter(
            LatePaymentAlert.invoice_id == inv.id,
            LatePaymentAlert.is_resolved == False,
        ).first()

        if not existing_alert:
            db.add(LatePaymentAlert(
                invoice_id=inv.id,
                tenant_id=inv.tenant_id,
                days_overdue=days,
            ))
        else:
            existing_alert.days_overdue = days

        count += 1

    if count:
        db.commit()
    return count


def void_invoice(db: Session, invoice_id: int) -> tuple[bool, str]:
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        return False, "Invoice not found."
    if inv.status == InvoiceStatus.PAID:
        return False, "Cannot void a paid invoice."
    inv.status = InvoiceStatus.VOID
    # Resolve any open late payment alert for this invoice
    from app.db.models import LatePaymentAlert
    from datetime import datetime
    alert = db.query(LatePaymentAlert).filter(
        LatePaymentAlert.invoice_id == invoice_id,
        LatePaymentAlert.is_resolved == False,
    ).first()
    if alert:
        alert.is_resolved = True
        alert.resolved_at = datetime.now()
    db.commit()
    return True, ""


def void_invoices_for_lease(db: Session, lease_id: int) -> int:
    """Void all unpaid invoices for a lease. Called on termination. Returns count voided."""
    from app.db.models import LatePaymentAlert
    from datetime import datetime
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.lease_id == lease_id,
            Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE, InvoiceStatus.DRAFT]),
        )
        .all()
    )
    count = 0
    for inv in invoices:
        inv.status = InvoiceStatus.VOID
        alert = db.query(LatePaymentAlert).filter(
            LatePaymentAlert.invoice_id == inv.id,
            LatePaymentAlert.is_resolved == False,
        ).first()
        if alert:
            alert.is_resolved = True
            alert.resolved_at = datetime.now()
        count += 1
    db.commit()
    return count


def get_invoices_for_tenant(db: Session, tenant_id: int) -> list[Invoice]:
    return (
        db.query(Invoice)
        .filter(Invoice.tenant_id == tenant_id)
        .order_by(Invoice.due_date.desc())
        .all()
    )


def get_unpaid_invoices(
    db: Session,
    city_id: int | None = None,
) -> list[Invoice]:
    """All issued or overdue invoices, optionally scoped to a city."""
    from app.db.models import Apartment, Property, LeaseAgreement as LA
    q = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.tenant),
            joinedload(Invoice.lease),
        )
        .filter(Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE]))
    )
    if city_id:
        q = (
            q.join(Invoice.lease)
            .join(LA.apartment)
            .join(Apartment.property)
            .filter(Property.city_id == city_id)
        )
    return q.order_by(Invoice.due_date).all()