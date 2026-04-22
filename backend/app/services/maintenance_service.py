# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/services/maintenance_service.py
=====================================
Business logic for maintenance ticket lifecycle.

Rules:
  - Only one ACTIVE ticket per apartment at a time (warn, don't block).
  - Status transitions must follow the workflow order.
  - Every status change logs a MaintenanceUpdate row.
  - Closing a ticket records actual_cost and time_spent.
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    MaintenanceTicket, MaintenanceUpdate, Apartment, Property,
    MaintenancePriority, MaintenanceStatus, Notification, NotificationType
)


# ── Queries ───────────────────────────────────────────────────────────────────

def get_ticket(db: Session, ticket_id: int) -> MaintenanceTicket | None:
    return (
        db.query(MaintenanceTicket)
        .options(
            joinedload(MaintenanceTicket.apartment),
            joinedload(MaintenanceTicket.updates),
        )
        .filter(MaintenanceTicket.id == ticket_id)
        .first()
    )


def get_all_tickets(
    db: Session,
    status: str | None = None,
    priority: str | None = None,
    apartment_id: int | None = None,
    assigned_to: int | None = None,
    city_id: int | None = None,
    limit: int = 300,
) -> list[MaintenanceTicket]:
    q = db.query(MaintenanceTicket)
    if status:
        q = q.filter(MaintenanceTicket.status == MaintenanceStatus(status))
    if priority:
        q = q.filter(MaintenanceTicket.priority == MaintenancePriority(priority))
    if apartment_id:
        q = q.filter(MaintenanceTicket.apartment_id == apartment_id)
    if assigned_to:
        q = q.filter(MaintenanceTicket.assigned_to == assigned_to)
    if city_id:
        q = (
            q.join(Apartment, MaintenanceTicket.apartment_id == Apartment.id)
            .join(Property, Apartment.property_id == Property.id)
            .filter(Property.city_id == city_id)
        )
    return (
        q.order_by(MaintenanceTicket.created_at.desc())
        .limit(limit)
        .all()
    )


# ── Core operations ───────────────────────────────────────────────────────────

def create_ticket(
    db: Session,
    *,
    apartment_id: int,
    title: str,
    description: str | None = None,
    priority: str = "medium",
    tenant_id: int | None = None,
    raised_by_user_id: int | None = None,
    scheduled_date: datetime | None = None,
) -> tuple[MaintenanceTicket | None, str]:
    apartment = db.query(Apartment).filter(Apartment.id == apartment_id).first()
    if not apartment:
        return None, "Apartment not found."

    try:
        prio = MaintenancePriority(priority)
    except ValueError:
        prio = MaintenancePriority.MEDIUM

    ticket = MaintenanceTicket(
        apartment_id=apartment_id,
        tenant_id=tenant_id,
        raised_by=raised_by_user_id,
        title=title,
        description=description,
        priority=prio,
        status=MaintenanceStatus.NEW,
        scheduled_date=scheduled_date,
        created_at=datetime.now(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    try:
        from app.services.audit_service import log_action, AuditAction
        log_action(db, action=AuditAction.TICKET_CREATE,
                   entity="ticket", entity_id=ticket.id,
                   user_id=raised_by_user_id,
                   detail=f"Title: {title} | Priority: {priority} | Apt: {apartment_id}")
    except Exception:
        pass
    return ticket, ""


def update_status(
    db: Session,
    ticket_id: int,
    new_status: str,
    *,
    note: str | None = None,
    updated_by_user_id: int | None = None,
    material_cost: Decimal | None = None,
    time_taken_hours: float | None = None,
    scheduled_date=None,
) -> tuple[bool, str]:
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    if not ticket:
        return False, "Ticket not found."

    try:
        status = MaintenanceStatus(new_status)
    except ValueError:
        return False, f"Invalid status '{new_status}'."

    old_status = ticket.status
    ticket.status = status

    if material_cost is not None:
        ticket.material_cost = material_cost
    if time_taken_hours is not None:
        ticket.time_taken_hours = time_taken_hours
    if scheduled_date is not None:
        ticket.scheduled_date = scheduled_date
    if status in (MaintenanceStatus.RESOLVED, MaintenanceStatus.CLOSED):
        ticket.completed_at = datetime.now()

    db.add(MaintenanceUpdate(
        ticket_id=ticket_id,
        updated_by=updated_by_user_id,
        old_status=old_status,
        new_status=status,
        note=note or "",
        created_at=datetime.now(),
    ))

    # Notify tenant if they're attached
    if ticket.tenant_id:
        db.add(Notification(
            tenant_id=ticket.tenant_id,
            type=NotificationType.MAINTENANCE_UPDATE,
            title=f"Maintenance Update: {ticket.title}",
            message=f"Status changed to {status.value.replace('_', ' ').title()}."
                    + (f" Note: {note}" if note else ""),
            is_read=False,
        ))

    db.commit()
    try:
        from app.services.audit_service import log_action, AuditAction
        old_label = old_status.value.replace("_", " ").title() if old_status else "—"
        new_label = status.value.replace("_", " ").title()
        detail = f"Ticket #{ticket_id}: {old_label} → {new_label}"
        if material_cost is not None:
            detail += f" | Cost: £{material_cost:,.2f}"
        if time_taken_hours is not None:
            detail += f" | Time: {time_taken_hours}h"
        if scheduled_date is not None:
            detail += f" | Scheduled: {scheduled_date.strftime('%d %b %Y') if hasattr(scheduled_date,'strftime') else scheduled_date}"
        if note:
            detail += f" | Note: {note}"
        log_action(db, action=AuditAction.TICKET_UPDATE,
                   user_id=updated_by_user_id,
                   entity="ticket", entity_id=ticket_id,
                   detail=detail)
    except Exception:
        pass
    return True, ""


def assign_ticket(
    db: Session,
    ticket_id: int,
    assigned_to_user_id: int,
    *,
    updated_by_user_id: int | None = None,
) -> tuple[bool, str]:
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    if not ticket:
        return False, "Ticket not found."

    ticket.assigned_to = assigned_to_user_id
    if ticket.status == MaintenanceStatus.NEW:
        ticket.status = MaintenanceStatus.TRIAGED
        db.add(MaintenanceUpdate(
            ticket_id=ticket_id,
            updated_by=updated_by_user_id,
            old_status=MaintenanceStatus.NEW,
            new_status=MaintenanceStatus.TRIAGED,
            note="Assigned to staff.",
            created_at=datetime.now(),
        ))

    db.commit()
    try:
        from app.services.audit_service import log_action, AuditAction
        from app.db.models import User as _User
        assignee = db.query(_User).filter(_User.id == assigned_to_user_id).first()
        log_action(db, action=AuditAction.TICKET_ASSIGN,
                   user_id=updated_by_user_id,
                   entity="ticket", entity_id=ticket_id,
                   detail=f"Ticket #{ticket_id} assigned to "
                          f"{assignee.full_name if assignee else assigned_to_user_id}")
    except Exception:
        pass
    return True, ""