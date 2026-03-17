"""
Business logic for complaint lifecycle.
"""

from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Complaint, ComplaintStatus, ComplaintCategory,
    Notification, NotificationType
)


def create_complaint(
    db: Session,
    *,
    tenant_id: int,
    category: str,
    subject: str,
    description: str | None = None,
    raised_by_user_id: int | None = None,
) -> tuple[Complaint | None, str]:
    try:
        cat = ComplaintCategory(category)
    except ValueError:
        return None, f"Invalid category '{category}'."

    complaint = Complaint(
        tenant_id=tenant_id,
        raised_by=raised_by_user_id,
        category=cat,
        subject=subject,
        description=description,
        status=ComplaintStatus.OPEN,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint, ""


def update_complaint_status(
    db: Session,
    complaint_id: int,
    new_status: str,
    *,
    resolution_notes: str | None = None,
    assigned_to_user_id: int | None = None,
    updated_by_user_id: int | None = None,
) -> tuple[bool, str]:
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        return False, "Complaint not found."

    try:
        status = ComplaintStatus(new_status)
    except ValueError:
        return False, f"Invalid status '{new_status}'."

    complaint.status = status
    if resolution_notes:
        complaint.resolution_notes = resolution_notes
    if assigned_to_user_id:
        complaint.assigned_to = assigned_to_user_id

    # Notify tenant
    db.add(Notification(
        tenant_id=complaint.tenant_id,
        type=NotificationType.COMPLAINT_UPDATE,
        title=f"Complaint Update: {complaint.subject}",
        message=f"Your complaint status is now: {status.value.replace('_', ' ').title()}."
                + (f" {resolution_notes}" if resolution_notes else ""),
        is_read=False,
    ))

    db.commit()
    return True, ""


def get_all_complaints(
    db: Session,
    status: str | None = None,
    category: str | None = None,
    limit: int = 300,
) -> list[Complaint]:
    q = db.query(Complaint)
    if status:
        q = q.filter(Complaint.status == ComplaintStatus(status))
    if category:
        q = q.filter(Complaint.category == ComplaintCategory(category))
    return q.order_by(Complaint.id.desc()).limit(limit).all()