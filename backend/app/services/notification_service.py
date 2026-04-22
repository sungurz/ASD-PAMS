# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
Create and retrieve in-app notifications.
"""

from __future__ import annotations
from sqlalchemy.orm import Session
from app.db.models import Notification, NotificationType


def create_notification(
    db: Session,
    *,
    title: str,
    message: str,
    notification_type: str = "general",
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        tenant_id=tenant_id,
        type=NotificationType(notification_type),
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def get_unread_for_user(db: Session, user_id: int) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .order_by(Notification.id.desc())
        .all()
    )


def mark_all_read(db: Session, user_id: int) -> int:
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return count