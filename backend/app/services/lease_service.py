"""

Business logic for lease lifecycle management.

Rules enforced here (not in the DB):
  - Only one ACTIVE lease per apartment at a time.
  - Early termination requires >= 30 days notice.
  - Early termination penalty = 5% of agreed_rent.
  - Apartment status is updated automatically on lease changes.
"""

from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    LeaseAgreement, LeaseTerminationRequest, Apartment,
    LeaseStatus, ApartmentStatus
)


# ── Queries

def get_active_lease(db: Session, apartment_id: int) -> LeaseAgreement | None:
    """Return the current ACTIVE lease for an apartment, or None."""
    return (
        db.query(LeaseAgreement)
        .filter(
            LeaseAgreement.apartment_id == apartment_id,
            LeaseAgreement.status == LeaseStatus.ACTIVE,
        )
        .first()
    )


def get_tenant_active_lease(db: Session, tenant_id: int) -> LeaseAgreement | None:
    """Return the tenant's current active lease."""
    return (
        db.query(LeaseAgreement)
        .filter(
            LeaseAgreement.tenant_id == tenant_id,
            LeaseAgreement.status == LeaseStatus.ACTIVE,
        )
        .options(joinedload(LeaseAgreement.apartment))
        .first()
    )


def get_lease_history(db: Session, apartment_id: int) -> list[LeaseAgreement]:
    """All leases for an apartment, newest first."""
    return (
        db.query(LeaseAgreement)
        .filter(LeaseAgreement.apartment_id == apartment_id)
        .options(joinedload(LeaseAgreement.tenant))
        .order_by(LeaseAgreement.start_date.desc())
        .all()
    )


# ── Core operations 

def create_lease(
    db: Session,
    *,
    tenant_id: int,
    apartment_id: int,
    start_date: date,
    end_date: date,
    agreed_rent: Decimal,
    deposit: Decimal | None = None,
    notes: str | None = None,
    created_by_user_id: int | None = None,
) -> tuple[LeaseAgreement | None, str]:
    """
    Create a new active lease.
    Returns (lease, "") on success, (None, error_message) on failure.
    """
    # Guard: apartment must be available
    apartment = db.query(Apartment).filter(Apartment.id == apartment_id).first()
    if not apartment:
        return None, "Apartment not found."

    if apartment.status == ApartmentStatus.OCCUPIED:
        return None, "This apartment already has an active lease."

    if apartment.status == ApartmentStatus.MAINTENANCE:
        return None, "This apartment is currently under maintenance and cannot be leased."

    # Guard: tenant must not already have an active lease
    existing = get_tenant_active_lease(db, tenant_id)
    if existing:
        return None, f"This tenant already has an active lease (Apartment {existing.apartment.unit_number})."

    # Guard: date logic
    if end_date <= start_date:
        return None, "End date must be after start date."

    lease = LeaseAgreement(
        tenant_id=tenant_id,
        apartment_id=apartment_id,
        start_date=start_date,
        end_date=end_date,
        agreed_rent=agreed_rent,
        deposit=deposit,
        status=LeaseStatus.ACTIVE,
        notes=notes,
        created_by=created_by_user_id,
    )
    db.add(lease)

    # Update apartment status
    apartment.status = ApartmentStatus.OCCUPIED

    db.commit()
    db.refresh(lease)
    return lease, ""


def end_lease(
    db: Session,
    lease_id: int,
    *,
    ended_by_user_id: int | None = None,
) -> tuple[bool, str]:
    """
    End a lease naturally (reached end_date or admin action).
    Frees the apartment back to Available.
    """
    lease = db.query(LeaseAgreement).filter(LeaseAgreement.id == lease_id).first()
    if not lease:
        return False, "Lease not found."
    if lease.status not in (LeaseStatus.ACTIVE, LeaseStatus.PENDING_TERMINATION):
        return False, f"Cannot end a lease with status '{lease.status.value}'."

    lease.status = LeaseStatus.EXPIRED

    apartment = db.query(Apartment).filter(Apartment.id == lease.apartment_id).first()
    if apartment:
        apartment.status = ApartmentStatus.AVAILABLE

    db.commit()
    return True, ""


def request_early_termination(
    db: Session,
    lease_id: int,
    *,
    requested_date: date,
    reason: str = "",
    requested_by_user_id: int | None = None,
) -> tuple[LeaseTerminationRequest | None, str]:
    """
    Submit an early termination request.
    - Notice period: minimum 30 days from today.
    - Penalty: 5% of agreed monthly rent.
    Returns (request, "") on success, (None, error) on failure.
    """
    lease = db.query(LeaseAgreement).filter(LeaseAgreement.id == lease_id).first()
    if not lease:
        return None, "Lease not found."
    if lease.status != LeaseStatus.ACTIVE:
        return None, "Only active leases can be terminated early."

    today = date.today()
    min_end = today + timedelta(days=30)
    intended_end = requested_date

    if intended_end < min_end:
        return None, (
            f"Early termination requires at least 30 days notice. "
            f"Earliest possible end date: {min_end.strftime('%d %b %Y')}."
        )

    if intended_end >= lease.end_date:
        return None, "Intended end date is on or after the natural lease end. No early termination needed."

    penalty = Decimal(str(lease.agreed_rent)) * Decimal("0.05")

    termination = LeaseTerminationRequest(
        lease_id=lease_id,
        requested_by=requested_by_user_id,
        requested_date=today,
        intended_end_date=intended_end,
        penalty_amount=penalty,
        reason=reason,
        status="pending",
    )
    db.add(termination)

    # Mark lease as pending termination
    lease.status = LeaseStatus.PENDING_TERMINATION

    db.commit()
    db.refresh(termination)
    return termination, ""


def approve_termination(
    db: Session,
    termination_id: int,
    *,
    reviewed_by_user_id: int | None = None,
) -> tuple[bool, str]:
    """Approve a pending termination request and close the lease."""
    from datetime import datetime
    req = db.query(LeaseTerminationRequest).filter(
        LeaseTerminationRequest.id == termination_id
    ).first()
    if not req:
        return False, "Termination request not found."
    if req.status != "pending":
        return False, f"Request is already '{req.status}'."

    req.status      = "approved"
    req.reviewed_by = reviewed_by_user_id
    req.reviewed_at = datetime.now()

    lease = db.query(LeaseAgreement).filter(LeaseAgreement.id == req.lease_id).first()
    if lease:
        lease.status   = LeaseStatus.TERMINATED_EARLY
        lease.end_date = req.intended_end_date
        apartment = db.query(Apartment).filter(Apartment.id == lease.apartment_id).first()
        if apartment:
            apartment.status = ApartmentStatus.AVAILABLE

    db.commit()
    return True, ""


def calculate_penalty(agreed_rent: Decimal) -> Decimal:
    """Return 5% of agreed_rent as the early termination penalty."""
    return Decimal(str(agreed_rent)) * Decimal("0.05")