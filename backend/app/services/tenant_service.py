"""
Business logic for tenant registration, search, and management.
UI layer calls these functions — never writes to DB directly.
"""

from __future__ import annotations
import hashlib
from datetime import date
from sqlalchemy.orm import Session, joinedload
from app.db.models import Tenant, TenantReference, ApartmentType


# ── Helpers 

def _mask_ni(ni: str) -> str:
    """Return a masked version: 'AB 12 34 56 C' → 'AB ** ** 56 C'"""
    ni = ni.upper().strip().replace(" ", "")
    if len(ni) < 9:
        return ni
    return f"{ni[:2]} ** ** {ni[6:8]} {ni[8]}"


def _hash_ni(ni: str) -> str:
    """One-way SHA-256 hash of the NI number for verification."""
    return hashlib.sha256(ni.upper().strip().replace(" ", "").encode()).hexdigest()


# ── Core CRUD 

def register_tenant(
    db: Session,
    *,
    full_name: str,
    email: str,
    phone: str,
    date_of_birth: date | None = None,
    ni_number: str | None = None,
    occupation: str | None = None,
    employer_name: str | None = None,
    employer_phone: str | None = None,
    annual_income: float | None = None,
    emergency_contact_name: str | None = None,
    emergency_contact_phone: str | None = None,
    preferred_apartment_type: ApartmentType | None = None,
    preferred_move_in_date: date | None = None,
    preferred_lease_months: int | None = None,
    additional_requirements: str | None = None,
    references: list[dict] | None = None,
    created_by_user_id: int | None = None,
) -> Tenant:
    """
    Register a new tenant.
    NI number is stored as masked display + hash only — never plain text.
    references: list of dicts with keys: reference_type, full_name,
                relation_type, phone, email, notes
    """
    ni_masked = _mask_ni(ni_number) if ni_number else None
    ni_hash   = _hash_ni(ni_number) if ni_number else None

    tenant = Tenant(
        full_name=full_name,
        email=email,
        phone=phone,
        date_of_birth=date_of_birth,
        ni_number_masked=ni_masked,
        ni_number_hash=ni_hash,
        occupation=occupation,
        employer_name=employer_name,
        employer_phone=employer_phone,
        annual_income=annual_income,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_phone=emergency_contact_phone,
        preferred_apartment_type=preferred_apartment_type,
        preferred_move_in_date=preferred_move_in_date,
        preferred_lease_months=preferred_lease_months,
        additional_requirements=additional_requirements,
        is_active=True,
    )
    db.add(tenant)
    db.flush()   # get tenant.id before adding references

    for ref in (references or []):
        if ref.get("full_name"):
            db.add(TenantReference(
                tenant_id=tenant.id,
                reference_type=ref.get("reference_type", "Personal"),
                full_name=ref["full_name"],
                relation_type=ref.get("relation_type", ""),
                phone=ref.get("phone", ""),
                email=ref.get("email", ""),
                notes=ref.get("notes", ""),
            ))

    db.commit()
    db.refresh(tenant)
    return tenant


def update_tenant(
    db: Session,
    tenant_id: int,
    *,
    full_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    occupation: str | None = None,
    employer_name: str | None = None,
    employer_phone: str | None = None,
    annual_income: float | None = None,
    emergency_contact_name: str | None = None,
    emergency_contact_phone: str | None = None,
    additional_requirements: str | None = None,
) -> Tenant | None:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return None

    if full_name  is not None: tenant.full_name  = full_name
    if email      is not None: tenant.email      = email
    if phone      is not None: tenant.phone      = phone
    if occupation is not None: tenant.occupation = occupation
    if employer_name  is not None: tenant.employer_name  = employer_name
    if employer_phone is not None: tenant.employer_phone = employer_phone
    if annual_income  is not None: tenant.annual_income  = annual_income
    if emergency_contact_name  is not None: tenant.emergency_contact_name  = emergency_contact_name
    if emergency_contact_phone is not None: tenant.emergency_contact_phone = emergency_contact_phone
    if additional_requirements is not None: tenant.additional_requirements = additional_requirements

    db.commit()
    db.refresh(tenant)
    return tenant


def archive_tenant(db: Session, tenant_id: int) -> bool:
    """Soft-delete: mark tenant as inactive."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return False
    tenant.is_active = False
    db.commit()
    return True


def get_tenant(db: Session, tenant_id: int) -> Tenant | None:
    return (
        db.query(Tenant)
        .options(joinedload(Tenant.references), joinedload(Tenant.leases))
        .filter(Tenant.id == tenant_id)
        .first()
    )


def search_tenants(
    db: Session,
    *,
    query: str = "",
    active_only: bool = True,
    limit: int = 200,
) -> list[Tenant]:
    """
    Search tenants by name, email, or phone.
    Returns up to `limit` results.
    """
    q = db.query(Tenant)
    if active_only:
        q = q.filter(Tenant.is_active == True)
    if query:
        like = f"%{query}%"
        q = q.filter(
            Tenant.full_name.ilike(like) |
            Tenant.email.ilike(like) |
            Tenant.phone.ilike(like)
        )
    return q.order_by(Tenant.full_name).limit(limit).all()


def email_exists(db: Session, email: str, exclude_id: int | None = None) -> bool:
    q = db.query(Tenant).filter(Tenant.email == email)
    if exclude_id:
        q = q.filter(Tenant.id != exclude_id)
    return q.first() is not None