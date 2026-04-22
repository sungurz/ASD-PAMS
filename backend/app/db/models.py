# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
Paragon Property Management System — Full Domain Model
Schema covers all modules required by the case study:
  - Identity & RBAC
  - Location hierarchy (City → Property → Apartment)
  - Tenant profiles & references
  - Lease lifecycle
  - Finance (invoices, payments, receipts, alerts)
  - Maintenance workflow
  - Complaints
  - Audit logging
  - Notifications
"""

from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Boolean,
    Numeric, ForeignKey, Enum, func
)
import enum


# ─────────────────────────────────────────────
#  Base
# ─────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
#  Enums
#  Using Python enums keeps values consistent
#  across the whole codebase.
# ─────────────────────────────────────────────

class RoleName(str, enum.Enum):
    TENANT             = "tenant"
    FRONT_DESK         = "front_desk"
    FINANCE_MANAGER    = "finance_manager"
    MAINTENANCE_STAFF  = "maintenance_staff"
    LOCATION_ADMIN     = "location_admin"
    MANAGER            = "manager"


class ApartmentStatus(str, enum.Enum):
    AVAILABLE   = "available"
    OCCUPIED    = "occupied"
    MAINTENANCE = "maintenance"   # unit under repair, cannot be leased
    INACTIVE    = "inactive"      # removed from inventory


class ApartmentType(str, enum.Enum):
    STUDIO    = "studio"
    ONE_BED   = "one_bed"
    TWO_BED   = "two_bed"
    THREE_BED = "three_bed"
    FOUR_BED  = "four_bed"


class LeaseStatus(str, enum.Enum):
    ACTIVE              = "active"
    EXPIRED             = "expired"
    TERMINATED_EARLY    = "terminated_early"
    PENDING_TERMINATION = "pending_termination"   # notice given, not yet ended
    DRAFT               = "draft"                 # created but not yet signed


class InvoiceStatus(str, enum.Enum):
    DRAFT    = "draft"
    ISSUED   = "issued"
    PAID     = "paid"
    OVERDUE  = "overdue"
    VOID     = "void"


class PaymentMethod(str, enum.Enum):
    CARD         = "card"         # simulated card flow
    BANK_TRANSFER = "bank_transfer"
    CASH         = "cash"


class MaintenancePriority(str, enum.Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    URGENT   = "urgent"


class MaintenanceStatus(str, enum.Enum):
    NEW            = "new"
    TRIAGED        = "triaged"
    SCHEDULED      = "scheduled"
    IN_PROGRESS    = "in_progress"
    WAITING_PARTS  = "waiting_parts"
    RESOLVED       = "resolved"
    CLOSED         = "closed"


class ComplaintStatus(str, enum.Enum):
    OPEN        = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED    = "resolved"
    CLOSED      = "closed"


class ComplaintCategory(str, enum.Enum):
    NOISE           = "noise"
    MAINTENANCE     = "maintenance"
    NEIGHBOUR       = "neighbour"
    BILLING         = "billing"
    STAFF_CONDUCT   = "staff_conduct"
    OTHER           = "other"


class NotificationType(str, enum.Enum):
    LATE_PAYMENT    = "late_payment"
    LEASE_EXPIRY    = "lease_expiry"
    MAINTENANCE_UPDATE = "maintenance_update"
    COMPLAINT_UPDATE   = "complaint_update"
    GENERAL         = "general"


# ─────────────────────────────────────────────
#  IDENTITY & ACCESS CONTROL
# ─────────────────────────────────────────────

class Role(Base):
    """
    The 6 system roles defined by the case study.
    Permissions are stored as a comma-separated string of
    permission keys, e.g. "tenant.view,lease.create".
    Simple and readable without a full permission join table
    for this scope of project.
    """
    __tablename__ = "roles"

    id          = Column(Integer, primary_key=True)
    name        = Column(Enum(RoleName), unique=True, nullable=False)
    description = Column(String(255))
    permissions = Column(Text)          # CSV of permission keys

    # relationships
    users = relationship("User", back_populates="role")


class User(Base):
    """
    Staff and system-level accounts.
    Tenant accounts are in the Tenant table — a Tenant
    optionally links to a User record for portal login.
    city_id scopes front-desk, finance, maintenance, and
    location_admin to a single city; NULL for manager (cross-city).
    """
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name     = Column(String(100), nullable=False)
    email         = Column(String(100), unique=True)
    phone         = Column(String(20))
    is_active     = Column(Boolean, default=True, nullable=False)

    # FK to Role
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    # City scope — NULL means cross-city (manager level)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    role           = relationship("Role", back_populates="users")
    city           = relationship("City", back_populates="staff")
    audit_logs     = relationship("AuditLog", back_populates="user")
    notifications  = relationship("Notification", back_populates="user")


# ─────────────────────────────────────────────
#  LOCATION HIERARCHY
#  City → Property → Apartment
# ─────────────────────────────────────────────

class City(Base):
    """
    Operational locations: Bristol, Cardiff, London, Manchester.
    Designed to allow future cities to be added without schema changes.
    """
    __tablename__ = "cities"

    id         = Column(Integer, primary_key=True)
    name       = Column(String(100), unique=True, nullable=False)
    country    = Column(String(50), default="United Kingdom")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    # relationships
    properties = relationship("Property", back_populates="city")
    staff      = relationship("User", back_populates="city")


class Property(Base):
    """
    A building or block within a city.
    One city can have many properties (e.g. Paragon Bristol Block A, Block B).
    """
    __tablename__ = "properties"

    id          = Column(Integer, primary_key=True)
    city_id     = Column(Integer, ForeignKey("cities.id"), nullable=False)
    name        = Column(String(150), nullable=False)       # e.g. "Paragon Bristol Block A"
    address     = Column(String(255), nullable=False)
    postcode    = Column(String(10))
    total_units = Column(Integer, default=0)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, server_default=func.now())

    # relationships
    city       = relationship("City", back_populates="properties")
    apartments = relationship("Apartment", back_populates="property")


class Apartment(Base):
    """
    A single lettable unit within a property.
    Rent is stored here as the base listed rent;
    the actual agreed rent for a specific lease is on LeaseAgreement.
    """
    __tablename__ = "apartments"

    id           = Column(Integer, primary_key=True)
    property_id  = Column(Integer, ForeignKey("properties.id"), nullable=False)
    unit_number  = Column(String(20), nullable=False)       # e.g. "4B", "Flat 12"
    floor        = Column(Integer)
    apartment_type = Column(Enum(ApartmentType), nullable=False)
    room_count   = Column(Integer, nullable=False)
    monthly_rent = Column(Numeric(10, 2), nullable=False)
    status       = Column(Enum(ApartmentStatus), default=ApartmentStatus.AVAILABLE, nullable=False)
    description  = Column(Text)
    created_at   = Column(DateTime, server_default=func.now())
    updated_at   = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    property            = relationship("Property", back_populates="apartments")
    leases              = relationship("LeaseAgreement", back_populates="apartment")
    maintenance_tickets = relationship("MaintenanceTicket", back_populates="apartment")


# ─────────────────────────────────────────────
#  TENANT
# ─────────────────────────────────────────────

class Tenant(Base):
    """
    Full tenant profile as required by the case study.
    NI number is stored as a hashed value for UK GDPR compliance —
    only authorised roles (location_admin, manager) see it unmasked.
    The optional user_id links to a User account if the tenant
    has portal login access.
    """
    __tablename__ = "tenants"

    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=True)  # portal login

    # Personal details
    full_name      = Column(String(100), nullable=False)
    date_of_birth  = Column(Date)
    email          = Column(String(100), unique=True, nullable=False)
    phone          = Column(String(20), nullable=False)
    emergency_contact_name  = Column(String(100))
    emergency_contact_phone = Column(String(20))

    # UK GDPR: NI number stored masked/hashed, original only shown to authorised roles
    ni_number_masked = Column(String(20))    # e.g. "NX *** *** A"
    ni_number_hash   = Column(String(255))   # bcrypt hash for verification

    # Employment / financial references
    occupation         = Column(String(100))
    employer_name      = Column(String(150))
    employer_phone     = Column(String(20))
    annual_income      = Column(Numeric(12, 2))

    # Requirements captured at registration (case study requirement)
    preferred_apartment_type = Column(Enum(ApartmentType), nullable=True)
    preferred_move_in_date   = Column(Date)
    preferred_lease_months   = Column(Integer)   # e.g. 6, 12, 24
    additional_requirements  = Column(Text)

    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)  # portal login
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    references          = relationship("TenantReference", back_populates="tenant")
    leases              = relationship("LeaseAgreement", back_populates="tenant")
    invoices            = relationship("Invoice", back_populates="tenant")
    payments            = relationship("Payment", back_populates="tenant")
    maintenance_tickets = relationship("MaintenanceTicket", back_populates="tenant")
    complaints          = relationship("Complaint", back_populates="tenant")
    notifications       = relationship("Notification", back_populates="tenant")


class TenantReference(Base):
    """
    References provided by the tenant at registration.
    Could be a previous landlord, employer, or personal reference.
    """
    __tablename__ = "tenant_references"

    id             = Column(Integer, primary_key=True)
    tenant_id      = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    reference_type = Column(String(50))     # e.g. "Previous Landlord", "Employer", "Personal"
    full_name      = Column(String(100), nullable=False)
    relation_to_tenant = Column(String(100))  # e.g. "Former Landlord"
    phone          = Column(String(20))
    email          = Column(String(100))
    notes          = Column(Text)
    created_at     = Column(DateTime, server_default=func.now())

    # relationships
    tenant = relationship("Tenant", back_populates="references")


# ─────────────────────────────────────────────
#  LEASE
# ─────────────────────────────────────────────

class LeaseAgreement(Base):
    """
    The contract linking one tenant to one apartment.
    An apartment can only have one ACTIVE lease at a time —
    this is enforced in the service layer, not the DB constraint,
    so historical leases can coexist.
    agreed_rent may differ from apartment.monthly_rent (negotiated rate).
    """
    __tablename__ = "lease_agreements"

    id          = Column(Integer, primary_key=True)
    tenant_id   = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=False)
    created_by  = Column(Integer, ForeignKey("users.id"))   # front-desk user who registered it

    start_date  = Column(Date, nullable=False)
    end_date    = Column(Date, nullable=False)
    agreed_rent = Column(Numeric(10, 2), nullable=False)
    deposit     = Column(Numeric(10, 2))
    status      = Column(Enum(LeaseStatus), default=LeaseStatus.DRAFT, nullable=False)

    # Renewal tracking
    is_renewal       = Column(Boolean, default=False)
    previous_lease_id = Column(Integer, ForeignKey("lease_agreements.id"), nullable=True)

    notes      = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    tenant                = relationship("Tenant", back_populates="leases")
    apartment             = relationship("Apartment", back_populates="leases")
    termination_requests  = relationship("LeaseTerminationRequest", back_populates="lease")
    invoices              = relationship("Invoice", back_populates="lease")


class LeaseTerminationRequest(Base):
    """
    Early termination flow:
    Tenant must give 1 month notice.
    Penalty = 5% of monthly rent (case study requirement).
    """
    __tablename__ = "lease_termination_requests"

    id               = Column(Integer, primary_key=True)
    lease_id         = Column(Integer, ForeignKey("lease_agreements.id"), nullable=False)
    requested_by     = Column(Integer, ForeignKey("users.id"))    # user who submitted
    requested_date   = Column(Date, nullable=False)               # date notice was given
    intended_end_date = Column(Date, nullable=False)              # must be >= requested_date + 30 days
    penalty_amount   = Column(Numeric(10, 2))                     # 5% of monthly_rent
    reason           = Column(Text)
    status           = Column(String(30), default="pending")      # pending / approved / rejected
    reviewed_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at      = Column(DateTime, nullable=True)
    notes            = Column(Text)
    created_at       = Column(DateTime, server_default=func.now())

    # relationships
    lease = relationship("LeaseAgreement", back_populates="termination_requests")


# ─────────────────────────────────────────────
#  FINANCE
# ─────────────────────────────────────────────

class Invoice(Base):
    """
    Monthly invoice generated for an active lease.
    Finance Manager generates these; they feed the payment ledger.
    """
    __tablename__ = "invoices"

    id           = Column(Integer, primary_key=True)
    lease_id     = Column(Integer, ForeignKey("lease_agreements.id"), nullable=False)
    tenant_id    = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id"))

    invoice_number = Column(String(30), unique=True, nullable=False)  # e.g. "INV-2026-0042"
    amount         = Column(Numeric(10, 2), nullable=False)
    due_date       = Column(Date, nullable=False)
    billing_period_start = Column(Date)
    billing_period_end   = Column(Date)
    status         = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False)
    notes          = Column(Text)
    created_at     = Column(DateTime, server_default=func.now())
    updated_at     = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    lease    = relationship("LeaseAgreement", back_populates="invoices")
    tenant   = relationship("Tenant", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")
    late_payment_alerts = relationship("LatePaymentAlert", back_populates="invoice")


class Payment(Base):
    """
    A payment posted against an invoice.
    The card flow is simulated — no real gateway.
    Partial payments are allowed (amount < invoice.amount).
    """
    __tablename__ = "payments"

    id           = Column(Integer, primary_key=True)
    invoice_id   = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    tenant_id    = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    recorded_by  = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL if self-service

    amount          = Column(Numeric(10, 2), nullable=False)
    payment_method  = Column(Enum(PaymentMethod), nullable=False)
    payment_date    = Column(DateTime, nullable=False, server_default=func.now())
    reference       = Column(String(100))   # card last 4 / bank ref
    notes           = Column(Text)
    created_at      = Column(DateTime, server_default=func.now())

    # relationships
    invoice = relationship("Invoice", back_populates="payments")
    tenant  = relationship("Tenant", back_populates="payments")
    receipt = relationship("PaymentReceipt", back_populates="payment", uselist=False)


class PaymentReceipt(Base):
    """
    Auto-generated receipt for each payment.
    receipt_number is the reference shown to the tenant.
    """
    __tablename__ = "payment_receipts"

    id             = Column(Integer, primary_key=True)
    payment_id     = Column(Integer, ForeignKey("payments.id"), unique=True, nullable=False)
    receipt_number = Column(String(30), unique=True, nullable=False)  # e.g. "RCP-2026-0099"
    issued_at      = Column(DateTime, server_default=func.now())
    amount         = Column(Numeric(10, 2), nullable=False)
    notes          = Column(Text)

    # relationships
    payment = relationship("Payment", back_populates="receipt")


class LatePaymentAlert(Base):
    """
    Created when an invoice passes its due_date unpaid.
    Drives the tenant dashboard alert and finance arrears report.
    """
    __tablename__ = "late_payment_alerts"

    id          = Column(Integer, primary_key=True)
    invoice_id  = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    tenant_id   = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    days_overdue = Column(Integer, default=0)
    alert_date  = Column(DateTime, server_default=func.now())
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)

    # relationships
    invoice = relationship("Invoice", back_populates="late_payment_alerts")


# ─────────────────────────────────────────────
#  MAINTENANCE
# ─────────────────────────────────────────────

class MaintenanceTicket(Base):
    """
    Full maintenance workflow as required:
    priority, scheduling, assignment, cost, time tracking.
    Can be raised by front-desk on behalf of tenant,
    or by tenant directly via the tenant dashboard.
    """
    __tablename__ = "maintenance_tickets"

    id           = Column(Integer, primary_key=True)
    apartment_id = Column(Integer, ForeignKey("apartments.id"), nullable=False)
    tenant_id    = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    raised_by    = Column(Integer, ForeignKey("users.id"))          # user who logged it
    assigned_to  = Column(Integer, ForeignKey("users.id"), nullable=True)  # maintenance staff

    title        = Column(String(200), nullable=False)
    description  = Column(Text)
    priority     = Column(Enum(MaintenancePriority), default=MaintenancePriority.MEDIUM, nullable=False)
    status       = Column(Enum(MaintenanceStatus), default=MaintenanceStatus.NEW, nullable=False)

    # Scheduling
    scheduled_date = Column(DateTime, nullable=True)

    # Resolution
    resolution_notes  = Column(Text)
    resolved_at       = Column(DateTime, nullable=True)
    time_taken_hours  = Column(Numeric(5, 2), nullable=True)   # e.g. 2.5 hours
    material_cost     = Column(Numeric(10, 2), nullable=True)
    labour_cost       = Column(Numeric(10, 2), nullable=True)

    # Optional link to a complaint that triggered this ticket
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    apartment   = relationship("Apartment", back_populates="maintenance_tickets")
    tenant      = relationship("Tenant", back_populates="maintenance_tickets")
    updates     = relationship("MaintenanceUpdate", back_populates="ticket")
    complaint   = relationship("Complaint", back_populates="maintenance_ticket", foreign_keys=[complaint_id])


class MaintenanceUpdate(Base):
    """
    Status change log for a ticket.
    Every time a maintenance staff member updates the ticket,
    a row is added here. This drives the tenant dashboard timeline.
    """
    __tablename__ = "maintenance_updates"

    id        = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("maintenance_tickets.id"), nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"))
    old_status = Column(Enum(MaintenanceStatus))
    new_status = Column(Enum(MaintenanceStatus))
    note       = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # relationships
    ticket = relationship("MaintenanceTicket", back_populates="updates")


# ─────────────────────────────────────────────
#  COMPLAINTS
# ─────────────────────────────────────────────

class Complaint(Base):
    """
    Raised by front-desk on behalf of tenant, or directly by tenant.
    May optionally spawn a MaintenanceTicket if it's a physical issue.
    """
    __tablename__ = "complaints"

    id           = Column(Integer, primary_key=True)
    tenant_id    = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    raised_by    = Column(Integer, ForeignKey("users.id"))
    assigned_to  = Column(Integer, ForeignKey("users.id"), nullable=True)

    category     = Column(Enum(ComplaintCategory), nullable=False)
    subject      = Column(String(200), nullable=False)
    description  = Column(Text)
    status       = Column(Enum(ComplaintStatus), default=ComplaintStatus.OPEN, nullable=False)

    resolution_notes = Column(Text)
    resolved_at      = Column(DateTime, nullable=True)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    tenant             = relationship("Tenant", back_populates="complaints")
    maintenance_ticket = relationship("MaintenanceTicket", back_populates="complaint",
                                      foreign_keys="MaintenanceTicket.complaint_id")


# ─────────────────────────────────────────────
#  NOTIFICATIONS
# ─────────────────────────────────────────────

class Notification(Base):
    """
    In-app notifications for both staff users and tenants.
    tenant_id is set when the notification is tenant-facing;
    user_id is set for staff-facing notifications.
    """
    __tablename__ = "notifications"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True)
    tenant_id   = Column(Integer, ForeignKey("tenants.id"), nullable=True)

    type        = Column(Enum(NotificationType), nullable=False)
    title       = Column(String(200), nullable=False)
    message     = Column(Text)
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime, server_default=func.now())

    # relationships
    user   = relationship("User", back_populates="notifications")
    tenant = relationship("Tenant", back_populates="notifications")


# ─────────────────────────────────────────────
#  AUDIT LOG
# ─────────────────────────────────────────────

class AuditLog(Base):
    """
    Immutable record of sensitive changes.
    Required for UK GDPR accountability and case study audit trail.
    Records: who, what action, which table/record, before and after values, when.
    Rows are never updated or deleted.
    """
    __tablename__ = "audit_logs"

    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    username     = Column(String(100))                   # denormalised for display
    action       = Column(String(100), nullable=False)
    entity       = Column(String(100))                   # e.g. "lease", "tenant"
    entity_id    = Column(Integer)
    detail       = Column(Text)                          # human-readable summary
    target_table = Column(String(100))
    target_id    = Column(Integer)
    before_value = Column(Text)
    after_value  = Column(Text)
    ip_address   = Column(String(45))
    created_at   = Column(DateTime, server_default=func.now())

    # relationships
    user = relationship("User", back_populates="audit_logs")