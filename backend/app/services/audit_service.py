# Ahmet (24034408) 
"""
app/services/audit_service.py
Uses SQLAlchemy ORM — table created automatically by create_tables.py.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session


class AuditAction:
    LOGIN            = "auth.login"
    LOGOUT           = "auth.logout"
    USER_CREATE      = "user.create"
    USER_DEACTIVATE  = "user.deactivate"
    USER_REACTIVATE  = "user.reactivate"
    TENANT_REGISTER  = "tenant.register"
    TENANT_EDIT      = "tenant.edit"
    TENANT_ARCHIVE   = "tenant.archive"
    TENANT_REACTIVATE= "tenant.reactivate"
    LEASE_CREATE     = "lease.create"
    LEASE_END        = "lease.end"
    LEASE_TERMINATE  = "lease.terminate"
    INVOICE_GENERATE = "invoice.generate"
    INVOICE_VOID     = "invoice.void"
    PAYMENT_RECORD   = "payment.record"
    TICKET_CREATE    = "ticket.create"
    TICKET_UPDATE    = "ticket.update"
    COMPLAINT_CREATE = "complaint.create"
    COMPLAINT_UPDATE = "complaint.update"
    APARTMENT_CREATE = "apartment.create"
    PROPERTY_CREATE  = "property.create"


def log_action(
    db: Session,
    *,
    action: str,
    user=None,
    user_id: int | None = None,
    username: str | None = None,
    entity: str | None = None,
    entity_id: int | None = None,
    detail: str | None = None,
) -> None:
    """Write one audit log row. Never raises — silently ignores failures."""
    try:
        from app.db.models import AuditLog
        uid   = user_id  or (user.id       if user else None)
        uname = username or (user.username if user else None)
        log = AuditLog(
            user_id   = uid,
            username  = uname,
            action    = action,
            entity    = entity,
            entity_id = entity_id,
            detail    = detail,
            created_at= datetime.now(),
        )
        db.add(log)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def get_audit_logs(
    db: Session,
    *,
    action: str | None = None,
    user_id: int | None = None,
    entity: str | None = None,
    limit: int = 300,
) -> list[dict]:
    try:
        from app.db.models import AuditLog
        q = db.query(AuditLog)
        if action:
            q = q.filter(AuditLog.action == action)
        if user_id:
            q = q.filter(AuditLog.user_id == user_id)
        if entity:
            q = q.filter(AuditLog.entity == entity)
        logs = q.order_by(AuditLog.created_at.desc()).limit(limit).all()
        return [
            {
                "id":         l.id,
                "user_id":    l.user_id,
                "username":   l.username or "System",
                "action":     l.action,
                "entity":     l.entity or "—",
                "entity_id":  l.entity_id,
                "detail":     l.detail or "—",
                "created_at": l.created_at,
            }
            for l in logs
        ]
    except Exception:
        return []