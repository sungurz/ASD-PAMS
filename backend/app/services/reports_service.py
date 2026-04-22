# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/services/reports_service.py
================================
Data queries powering the Reports and Home dashboard pages.
All functions return plain dicts/lists for easy display.
"""

from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func


# ── Occupancy ─────────────────────────────────────────────────────────────────

def get_occupancy_summary(db: Session, city_id: int | None = None) -> dict:
    """Overall occupancy stats, optionally city-scoped."""
    from app.db.models import Apartment, ApartmentStatus, Property

    q = db.query(Apartment)
    if city_id:
        q = q.join(Property, Apartment.property_id == Property.id).filter(
            Property.city_id == city_id
        )
    all_apts = q.all()

    total       = len(all_apts)
    occupied    = sum(1 for a in all_apts if a.status == ApartmentStatus.OCCUPIED)
    available   = sum(1 for a in all_apts if a.status == ApartmentStatus.AVAILABLE)
    maintenance = sum(1 for a in all_apts if a.status == ApartmentStatus.MAINTENANCE)
    inactive    = sum(1 for a in all_apts if a.status == ApartmentStatus.INACTIVE)
    rate        = round((occupied / total * 100), 1) if total else 0.0

    return {
        "total": total,
        "occupied": occupied,
        "available": available,
        "maintenance": maintenance,
        "inactive": inactive,
        "occupancy_rate": rate,
    }


def get_occupancy_by_city(db: Session) -> list[dict]:
    """Occupancy breakdown per city."""
    from app.db.models import City, Property, Apartment, ApartmentStatus

    cities = db.query(City).filter(City.is_active == True).order_by(City.name).all()
    result = []
    for city in cities:
        data = get_occupancy_summary(db, city_id=city.id)
        data["city"] = city.name
        result.append(data)
    return result


# ── Finance ───────────────────────────────────────────────────────────────────

def get_finance_summary(db: Session, city_id: int | None = None) -> dict:
    """Revenue and outstanding totals."""
    from app.db.models import Invoice, InvoiceStatus, Payment, LeaseAgreement, Apartment, Property

    inv_q = db.query(Invoice)
    if city_id:
        inv_q = (
            inv_q.join(LeaseAgreement, Invoice.lease_id == LeaseAgreement.id)
            .join(Apartment, LeaseAgreement.apartment_id == Apartment.id)
            .join(Property, Apartment.property_id == Property.id)
            .filter(Property.city_id == city_id)
        )

    invoices = inv_q.all()
    invoice_ids = [i.id for i in invoices]

    total_invoiced = sum(i.amount for i in invoices if i.status != InvoiceStatus.VOID)

    paid_total = Decimal("0")
    if invoice_ids:
        paid_total = (
            db.query(func.sum(Payment.amount))
            .filter(Payment.invoice_id.in_(invoice_ids))
            .scalar() or Decimal("0")
        )

    overdue_total = sum(
        i.amount for i in invoices if i.status == InvoiceStatus.OVERDUE
    )
    outstanding = sum(
        i.amount for i in invoices
        if i.status in (InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE)
    )

    # This month's revenue
    today = date.today()
    this_month_paid = Decimal("0")
    if invoice_ids:
        this_month_paid = (
            db.query(func.sum(Payment.amount))
            .filter(
                Payment.invoice_id.in_(invoice_ids),
                func.month(Payment.payment_date) == today.month,
                func.year(Payment.payment_date) == today.year,
            )
            .scalar() or Decimal("0")
        )

    return {
        "total_invoiced":   float(total_invoiced),
        "total_collected":  float(paid_total),
        "outstanding":      float(outstanding),
        "overdue":          float(overdue_total),
        "this_month":       float(this_month_paid),
    }


def get_monthly_revenue(db: Session, city_id: int | None = None, months: int = 6) -> list[dict]:
    """Revenue collected per month for the last N months."""
    from app.db.models import Payment, Invoice, LeaseAgreement, Apartment, Property

    pay_q = db.query(Payment)
    if city_id:
        pay_q = (
            pay_q.join(Invoice, Payment.invoice_id == Invoice.id)
            .join(LeaseAgreement, Invoice.lease_id == LeaseAgreement.id)
            .join(Apartment, LeaseAgreement.apartment_id == Apartment.id)
            .join(Property, Apartment.property_id == Property.id)
            .filter(Property.city_id == city_id)
        )

    payments = pay_q.order_by(Payment.payment_date).all()

    # Group by month
    monthly: dict[str, float] = {}
    for p in payments:
        if p.payment_date:
            key = p.payment_date.strftime("%b %Y")
            monthly[key] = monthly.get(key, 0.0) + float(p.amount)

    # Return last N months
    items = list(monthly.items())
    return [{"month": k, "amount": round(v, 2)} for k, v in items[-months:]]


# ── Maintenance ───────────────────────────────────────────────────────────────

def get_maintenance_summary(db: Session, city_id: int | None = None) -> dict:
    """Maintenance ticket stats."""
    from app.db.models import MaintenanceTicket, MaintenanceStatus, MaintenancePriority, Apartment, Property

    q = db.query(MaintenanceTicket)
    if city_id:
        q = (
            q.join(Apartment, MaintenanceTicket.apartment_id == Apartment.id)
            .join(Property, Apartment.property_id == Property.id)
            .filter(Property.city_id == city_id)
        )

    tickets = q.all()
    open_statuses = [
        MaintenanceStatus.NEW, MaintenanceStatus.TRIAGED,
        MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS,
        MaintenanceStatus.WAITING_PARTS,
    ]

    total    = len(tickets)
    open_    = sum(1 for t in tickets if t.status in open_statuses)
    resolved = sum(1 for t in tickets if t.status == MaintenanceStatus.RESOLVED)
    closed   = sum(1 for t in tickets if t.status == MaintenanceStatus.CLOSED)
    urgent   = sum(1 for t in tickets if t.status in open_statuses
                   and t.priority == MaintenancePriority.URGENT)

    return {
        "total": total,
        "open": open_,
        "resolved": resolved,
        "closed": closed,
        "urgent_open": urgent,
    }


def get_open_tickets_by_status(db: Session, city_id: int | None = None) -> list[dict]:
    """Count of open tickets grouped by status."""
    from app.db.models import MaintenanceTicket, MaintenanceStatus, Apartment, Property

    q = db.query(MaintenanceTicket)
    if city_id:
        q = (
            q.join(Apartment, MaintenanceTicket.apartment_id == Apartment.id)
            .join(Property, Apartment.property_id == Property.id)
            .filter(Property.city_id == city_id)
        )

    open_statuses = [
        MaintenanceStatus.NEW, MaintenanceStatus.TRIAGED,
        MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS,
        MaintenanceStatus.WAITING_PARTS,
    ]
    tickets = q.filter(MaintenanceTicket.status.in_(open_statuses)).all()

    counts: dict[str, int] = {}
    for t in tickets:
        label = t.status.value.replace("_", " ").title()
        counts[label] = counts.get(label, 0) + 1

    return [{"status": k, "count": v} for k, v in counts.items()]


# ── Complaints ────────────────────────────────────────────────────────────────

def get_complaints_summary(db: Session, city_id: int | None = None) -> dict:
    """Complaint stats."""
    from app.db.models import Complaint, ComplaintStatus, LeaseAgreement, Apartment, Property, Tenant

    q = db.query(Complaint)
    if city_id:
        q = (
            q.join(Tenant, Complaint.tenant_id == Tenant.id)
            .outerjoin(LeaseAgreement, (LeaseAgreement.tenant_id == Tenant.id))
            .outerjoin(Apartment, LeaseAgreement.apartment_id == Apartment.id)
            .outerjoin(Property, Apartment.property_id == Property.id)
            .filter(Property.city_id == city_id)
        )

    complaints = q.all()
    return {
        "total":       len(complaints),
        "open":        sum(1 for c in complaints if c.status == ComplaintStatus.OPEN),
        "under_review":sum(1 for c in complaints if c.status == ComplaintStatus.UNDER_REVIEW),
        "resolved":    sum(1 for c in complaints if c.status == ComplaintStatus.RESOLVED),
        "closed":      sum(1 for c in complaints if c.status == ComplaintStatus.CLOSED),
    }


# ── Home dashboard ────────────────────────────────────────────────────────────

def get_dashboard_summary(db: Session, city_id: int | None = None) -> dict:
    """All key stats for the home dashboard in one call."""
    return {
        "occupancy":   get_occupancy_summary(db, city_id),
        "finance":     get_finance_summary(db, city_id),
        "maintenance": get_maintenance_summary(db, city_id),
        "complaints":  get_complaints_summary(db, city_id),
    }


def get_recent_activity(db: Session, city_id: int | None = None, limit: int = 8) -> list[dict]:
    """Recent events across the system for the activity feed."""
    from app.db.models import (
        MaintenanceTicket, Complaint, Invoice, LeaseAgreement,
        Apartment, Property, Tenant, InvoiceStatus
    )
    events = []

    # Recent maintenance tickets
    mq = db.query(MaintenanceTicket).order_by(MaintenanceTicket.created_at.desc())
    if city_id:
        mq = (mq.join(Apartment, MaintenanceTicket.apartment_id == Apartment.id)
              .join(Property, Apartment.property_id == Property.id)
              .filter(Property.city_id == city_id))
    for t in mq.limit(3).all():
        events.append({
            "type": "maintenance",
            "text": f"Ticket: {t.title}",
            "sub":  f"{t.priority.value.title()} — {t.status.value.replace('_',' ').title()}",
            "date": t.created_at,
        })

    # Recent complaints
    cq = db.query(Complaint).order_by(Complaint.id.desc())
    for c in cq.limit(3).all():
        events.append({
            "type": "complaint",
            "text": f"Complaint: {c.subject}",
            "sub":  c.status.value.replace("_", " ").title(),
            "date": None,
        })

    # Recent overdue invoices
    iq = db.query(Invoice).filter(Invoice.status == InvoiceStatus.OVERDUE).order_by(Invoice.due_date)
    if city_id:
        iq = (iq.join(LeaseAgreement, Invoice.lease_id == LeaseAgreement.id)
              .join(Apartment, LeaseAgreement.apartment_id == Apartment.id)
              .join(Property, Apartment.property_id == Property.id)
              .filter(Property.city_id == city_id))
    for inv in iq.limit(3).all():
        events.append({
            "type": "invoice",
            "text": f"Overdue: {inv.invoice_number}",
            "sub":  f"£{inv.amount:,.2f} due {inv.due_date.strftime('%d %b %Y') if inv.due_date else '—'}",
            "date": None,
        })

    # Sort by date where available
    events.sort(key=lambda x: x["date"] or datetime.min, reverse=True)
    return events[:limit]


def get_maintenance_costs(db: Session, city_id: int | None = None) -> dict:
    """Total material costs and time spent across resolved/closed tickets."""
    from app.db.models import (
        MaintenanceTicket, MaintenanceStatus, Apartment, Property
    )
    from sqlalchemy import func

    q = db.query(MaintenanceTicket).filter(
        MaintenanceTicket.status.in_([
            MaintenanceStatus.RESOLVED, MaintenanceStatus.CLOSED
        ])
    )
    if city_id:
        q = (q.join(Apartment, MaintenanceTicket.apartment_id == Apartment.id)
               .join(Property, Apartment.property_id == Property.id)
               .filter(Property.city_id == city_id))

    tickets = q.all()
    total_cost  = sum(float(t.material_cost or 0)  for t in tickets)
    total_hours = sum(float(t.time_taken_hours or 0) for t in tickets)

    # Top 5 most expensive tickets
    top = sorted(
        [t for t in tickets if t.material_cost],
        key=lambda t: t.material_cost,
        reverse=True
    )[:5]

    return {
        "total_material_cost": round(total_cost, 2),
        "total_hours":         round(total_hours, 1),
        "resolved_count":      len(tickets),
        "top_cost_tickets":    [
            {
                "title":    t.title,
                "cost":     float(t.material_cost),
                "hours":    float(t.time_taken_hours or 0),
            }
            for t in top
        ],
    }