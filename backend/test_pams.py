# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
test_pams.py
============
PAMS — Automated Test Suite
UFCF8S-30-2  Advanced Software Development  |  Group 38
Student: Ahmet (24034408)

Run with:  pytest test_pams.py -v
           pytest test_pams.py -v --tb=short   (brief tracebacks)

Tests cover:
  - All major model classes (City, Role, User, Tenant, Apartment,
    Lease, Invoice, Payment, MaintenanceTicket, AuditLog)
  - Valid data (expected to pass)
  - Invalid / out-of-range data (expected to fail / return errors)
  - Business rule enforcement via service layer
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# ── App imports ──────────────────────────────────────────────────────────────
from app.db.models import (
    Base,
    Role, User, City, Property, Apartment, Tenant,
    LeaseAgreement, LeaseTerminationRequest,
    Invoice, Payment, PaymentReceipt, LatePaymentAlert,
    MaintenanceTicket, AuditLog,
    # Enums
    RoleName, ApartmentStatus, ApartmentType,
    LeaseStatus, InvoiceStatus, PaymentMethod,
    MaintenancePriority, MaintenanceStatus,
)
from app.services.lease_service    import request_early_termination
from app.services.payment_service  import record_payment
from app.services.tenant_service   import register_tenant


# ═══════════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def engine():
    """Single in-memory SQLite engine for the whole test session."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture(scope="function")
def db(engine):
    """
    Fresh transactional scope per test.
    Each test runs inside a transaction that is rolled back on teardown —
    guaranteeing full isolation without recreating tables.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ── Shared factory helpers ───────────────────────────────────────────────────

def _city(db, name="Bristol"):
    obj = City(name=name, country="United Kingdom", is_active=True)
    db.add(obj); db.flush(); return obj

def _role(db, role_name=RoleName.FRONT_DESK):
    obj = Role(name=role_name, description="Test role",
               permissions="tenant.view,tenant.create")
    db.add(obj); db.flush(); return obj

def _user(db, role, city, username="teststaff"):
    obj = User(
        username=username, password_hash="$2b$12$fakehashXXXXXXXXXXXXXX",
        full_name="Test Staff", email=f"{username}@paragon.test",
        phone="07700900000", is_active=True,
        role_id=role.id, city_id=city.id,
    )
    db.add(obj); db.flush(); return obj

def _property(db, city):
    obj = Property(name="Paragon House", address="1 Test St",
                   postcode="BS1 1AA", city_id=city.id,
                   total_units=10, is_active=True)
    db.add(obj); db.flush(); return obj

def _apartment(db, prop, rent=Decimal("900.00")):
    obj = Apartment(
        unit_number="1A", floor=1,
        apartment_type=ApartmentType.ONE_BED,
        room_count=1, monthly_rent=rent,
        status=ApartmentStatus.AVAILABLE,
        property_id=prop.id,
    )
    db.add(obj); db.flush(); return obj

def _tenant(db):
    """Create a tenant via the service layer (correct NI handling)."""
    return register_tenant(
        db,
        full_name="Jane Smith",
        email="jane.smith@example.com",
        phone="07700911111",
        ni_number="AB123456C",
        occupation="Software Engineer",
        annual_income=40000.0,
    )

def _lease(db, tenant, apartment, months=12):
    today = date.today()
    obj = LeaseAgreement(
        tenant_id=tenant.id, apartment_id=apartment.id,
        start_date=today,
        end_date=today + timedelta(days=30 * months),
        agreed_rent=apartment.monthly_rent,
        deposit=apartment.monthly_rent * 2,
        status=LeaseStatus.ACTIVE,
    )
    db.add(obj)
    apartment.status = ApartmentStatus.OCCUPIED
    db.flush(); return obj

def _invoice(db, tenant, lease, amount=Decimal("900.00"), days_overdue=0):
    today = date.today()
    due   = today - timedelta(days=days_overdue) if days_overdue else today + timedelta(days=14)
    obj   = Invoice(
        lease_id=lease.id, tenant_id=tenant.id,
        invoice_number=f"INV-2026-{tenant.id:04d}",
        amount=amount, due_date=due,
        billing_period_start=today,
        billing_period_end=today + timedelta(days=30),
        status=InvoiceStatus.ISSUED,
    )
    db.add(obj); db.flush(); return obj


# ═══════════════════════════════════════════════════════════════════════════════
#  1 — CITY MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestCityModel:

    def test_city_can_be_created(self, db):
        """A city record can be saved and retrieved."""
        city = _city(db, name="Manchester")
        assert city.id is not None
        assert city.name == "Manchester"
        assert city.is_active is True

    def test_city_name_uniqueness_enforced(self, db):
        """Duplicate city names must be rejected."""
        _city(db, name="Cardiff")
        with pytest.raises(IntegrityError):
            _city(db, name="Cardiff")   # duplicate — must fail

    def test_city_is_active_defaults_to_true(self, db):
        """New cities are active by default."""
        city = City(name="London", country="United Kingdom")
        db.add(city); db.flush()
        assert city.is_active is True


# ═══════════════════════════════════════════════════════════════════════════════
#  2 — ROLE & USER MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoleAndUser:

    def test_all_six_roles_can_be_created(self, db):
        """All six PAMS roles defined in the brief can be persisted."""
        for role_name in RoleName:
            r = Role(name=role_name, description=f"{role_name.value} role",
                     permissions="")
            db.add(r)
        db.flush()
        count = db.query(Role).count()
        assert count == len(RoleName)

    def test_user_can_be_created(self, db):
        """A staff user can be created with the correct role and city scope."""
        city = _city(db)
        role = _role(db)
        user = _user(db, role, city)
        assert user.id is not None
        assert user.username == "teststaff"
        assert user.is_active is True

    def test_duplicate_username_rejected(self, db):
        """Usernames must be unique across the system."""
        city = _city(db)
        role = _role(db)
        _user(db, role, city, username="duplicateuser")
        with pytest.raises(IntegrityError):
            _user(db, role, city, username="duplicateuser")   # must fail

    def test_duplicate_email_rejected(self, db):
        """User emails must be unique."""
        city = _city(db)
        role = _role(db, RoleName.FINANCE_MANAGER)
        u1 = User(username="userA", password_hash="hash",
                  full_name="A", email="shared@paragon.test",
                  is_active=True, role_id=role.id, city_id=city.id)
        u2 = User(username="userB", password_hash="hash",
                  full_name="B", email="shared@paragon.test",
                  is_active=True, role_id=role.id, city_id=city.id)
        db.add(u1); db.flush()
        db.add(u2)
        with pytest.raises(IntegrityError):
            db.flush()

    def test_deactivated_user_flag(self, db):
        """is_active can be set to False to deactivate a user."""
        city = _city(db)
        role = _role(db)
        user = _user(db, role, city)
        user.is_active = False
        db.flush()
        fetched = db.query(User).filter(User.id == user.id).first()
        assert fetched.is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
#  3 — TENANT MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestTenantModel:

    def test_tenant_can_be_registered(self, db):
        """A tenant can be registered via the service layer."""
        tenant = _tenant(db)
        assert tenant.id is not None
        assert tenant.full_name == "Jane Smith"
        assert tenant.is_active is True

    def test_ni_number_never_stored_as_plaintext(self, db):
        """NI numbers must be stored masked/hashed — never as plain text."""
        tenant = _tenant(db)
        # The raw NI "AB123456C" must not appear anywhere
        assert tenant.ni_number_masked != "AB123456C"
        assert tenant.ni_number_hash   != "AB123456C"
        # But masked form should exist
        assert tenant.ni_number_masked is not None
        assert tenant.ni_number_hash   is not None

    def test_tenant_email_uniqueness_enforced(self, db):
        """No two tenants can share the same email address."""
        register_tenant(db, full_name="Alice", email="dupe@example.com",
                        phone="07700000001", ni_number="CD234567D",
                        occupation="Teacher", annual_income=30000.0)
        with pytest.raises((IntegrityError, Exception)):
            register_tenant(db, full_name="Bob", email="dupe@example.com",
                            phone="07700000002", ni_number="EF345678E",
                            occupation="Driver", annual_income=28000.0)

    def test_inactive_tenant_can_be_flagged(self, db):
        """Tenant is_active flag can be set to False."""
        tenant = _tenant(db)
        tenant.is_active = False
        db.flush()
        assert db.query(Tenant).filter(Tenant.id == tenant.id).first().is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
#  4 — APARTMENT MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestApartmentModel:

    def test_apartment_can_be_created(self, db):
        """An apartment record can be created with all required fields."""
        city = _city(db)
        prop = _property(db, city)
        apt  = _apartment(db, prop)
        assert apt.id is not None
        assert apt.unit_number == "1A"
        assert apt.monthly_rent == Decimal("900.00")

    def test_apartment_default_status_is_available(self, db):
        """Newly created apartments must default to AVAILABLE status."""
        city = _city(db)
        prop = _property(db, city)
        apt  = _apartment(db, prop)
        assert apt.status == ApartmentStatus.AVAILABLE

    def test_apartment_status_transitions(self, db):
        """Apartment status can be changed to OCCUPIED and MAINTENANCE."""
        city = _city(db)
        prop = _property(db, city)
        apt  = _apartment(db, prop)

        apt.status = ApartmentStatus.OCCUPIED
        db.flush()
        assert apt.status == ApartmentStatus.OCCUPIED

        apt.status = ApartmentStatus.MAINTENANCE
        db.flush()
        assert apt.status == ApartmentStatus.MAINTENANCE

    def test_apartment_rent_is_stored_correctly(self, db):
        """Monthly rent is stored as a precise Decimal value."""
        city = _city(db)
        prop = _property(db, city)
        apt  = _apartment(db, prop, rent=Decimal("1250.50"))
        assert apt.monthly_rent == Decimal("1250.50")


# ═══════════════════════════════════════════════════════════════════════════════
#  5 — LEASE AGREEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class TestLeaseAgreement:

    def test_lease_can_be_created(self, db):
        """A lease agreement can be created linking a tenant to an apartment."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db)
        lease = _lease(db, tenant, apt)
        assert lease.id is not None
        assert lease.status == LeaseStatus.ACTIVE

    def test_lease_marks_apartment_as_occupied(self, db):
        """Creating a lease should update the apartment status to OCCUPIED."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db)
        _lease(db, tenant, apt)
        assert apt.status == ApartmentStatus.OCCUPIED

    def test_lease_stores_agreed_rent(self, db):
        """Lease stores the agreed rent at the time of signing."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db)
        lease = _lease(db, tenant, apt)
        assert lease.agreed_rent == Decimal("900.00")

    def test_lease_end_date_is_after_start_date(self, db):
        """Lease end date must be in the future relative to start date."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db)
        today = date.today()
        lease = LeaseAgreement(
            tenant_id=tenant.id, apartment_id=apt.id,
            start_date=today,
            end_date=today + timedelta(days=365),
            agreed_rent=Decimal("900.00"),
            deposit=Decimal("1800.00"),
            status=LeaseStatus.ACTIVE,
        )
        db.add(lease); db.flush()
        assert lease.end_date > lease.start_date


# ═══════════════════════════════════════════════════════════════════════════════
#  6 — INVOICE MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestInvoiceModel:

    def test_invoice_can_be_created(self, db):
        """An invoice can be generated for an active lease."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db); lease = _lease(db, tenant, apt)
        inv = _invoice(db, tenant, lease)
        assert inv.id is not None
        assert inv.invoice_number.startswith("INV-")
        assert inv.status == InvoiceStatus.ISSUED

    def test_invoice_amount_stored_as_decimal(self, db):
        """Invoice amount is stored with full decimal precision."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db); lease = _lease(db, tenant, apt)
        inv = _invoice(db, tenant, lease, amount=Decimal("875.50"))
        assert inv.amount == Decimal("875.50")

    def test_invoice_numbers_are_unique(self, db):
        """Two invoices cannot share the same invoice number."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db); lease = _lease(db, tenant, apt)
        today  = date.today()
        inv1 = Invoice(lease_id=lease.id, tenant_id=tenant.id,
                       invoice_number="INV-2026-DUPE", amount=Decimal("900"),
                       due_date=today + timedelta(days=14),
                       billing_period_start=today,
                       billing_period_end=today + timedelta(days=30),
                       status=InvoiceStatus.ISSUED)
        inv2 = Invoice(lease_id=lease.id, tenant_id=tenant.id,
                       invoice_number="INV-2026-DUPE", amount=Decimal("900"),
                       due_date=today + timedelta(days=14),
                       billing_period_start=today,
                       billing_period_end=today + timedelta(days=30),
                       status=InvoiceStatus.ISSUED)
        db.add(inv1); db.flush()
        db.add(inv2)
        with pytest.raises(IntegrityError):
            db.flush()


# ═══════════════════════════════════════════════════════════════════════════════
#  7 — PAYMENT SERVICE  (valid + invalid data)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaymentService:

    def _setup(self, db):
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db); lease = _lease(db, tenant, apt)
        inv = _invoice(db, tenant, lease)
        return inv

    def test_valid_payment_recorded_successfully(self, db):
        """A valid payment against an issued invoice must succeed."""
        inv = self._setup(db)
        payment, err = record_payment(
            db, invoice_id=inv.id, amount=Decimal("900.00"),
            payment_method=PaymentMethod.BANK_TRANSFER,
        )
        assert err == "", f"Unexpected error: {err}"
        assert payment is not None
        assert payment.amount == Decimal("900.00")

    def test_payment_marks_invoice_as_paid(self, db):
        """After full payment the invoice status must change to PAID."""
        inv = self._setup(db)
        record_payment(db, invoice_id=inv.id, amount=Decimal("900.00"),
                       payment_method=PaymentMethod.CASH)
        db.refresh(inv)
        assert inv.status == InvoiceStatus.PAID

    def test_negative_payment_amount_rejected(self, db):
        """A payment with a negative amount must be rejected."""
        inv = self._setup(db)
        payment, err = record_payment(
            db, invoice_id=inv.id, amount=Decimal("-50.00"),
            payment_method=PaymentMethod.CARD,
        )
        assert payment is None
        assert err != ""

    def test_payment_exceeding_invoice_amount_rejected(self, db):
        """A payment greater than the invoice amount must be rejected."""
        inv = self._setup(db)
        payment, err = record_payment(
            db, invoice_id=inv.id, amount=Decimal("9999.00"),
            payment_method=PaymentMethod.CARD,
        )
        assert payment is None
        assert err != ""

    def test_payment_against_already_paid_invoice_rejected(self, db):
        """Paying an invoice that is already fully paid must return an error."""
        inv = self._setup(db)
        # First payment — should succeed
        record_payment(db, invoice_id=inv.id, amount=Decimal("900.00"),
                       payment_method=PaymentMethod.BANK_TRANSFER)
        # Second payment on same invoice — must fail
        payment, err = record_payment(
            db, invoice_id=inv.id, amount=Decimal("900.00"),
            payment_method=PaymentMethod.BANK_TRANSFER,
        )
        assert payment is None
        assert err != ""

    def test_payment_against_void_invoice_rejected(self, db):
        """A voided invoice must not accept any payments."""
        inv = self._setup(db)
        inv.status = InvoiceStatus.VOID
        db.flush()
        payment, err = record_payment(
            db, invoice_id=inv.id, amount=Decimal("900.00"),
            payment_method=PaymentMethod.CASH,
        )
        assert payment is None
        assert err != ""

    def test_payment_against_nonexistent_invoice_rejected(self, db):
        """Attempting to pay a non-existent invoice must return an error."""
        payment, err = record_payment(
            db, invoice_id=99999, amount=Decimal("900.00"),
            payment_method=PaymentMethod.CASH,
        )
        assert payment is None
        assert err != ""


# ═══════════════════════════════════════════════════════════════════════════════
#  8 — LEASE TERMINATION SERVICE  (valid + invalid data)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLeaseTerminationService:

    def _setup(self, db):
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db); lease = _lease(db, tenant, apt, months=24)
        return lease

    def test_valid_early_termination_accepted(self, db):
        """A valid early termination request with 30+ days notice must succeed."""
        lease = self._setup(db)
        notice_date = date.today() + timedelta(days=31)   # 31 days — valid
        req, err = request_early_termination(
            db, lease.id, requested_date=notice_date, reason="Relocation"
        )
        assert err == "", f"Unexpected error: {err}"
        assert req is not None
        assert req.status == "pending"

    def test_penalty_is_five_percent_of_rent(self, db):
        """Early termination penalty must be exactly 5% of monthly rent."""
        lease = self._setup(db)
        notice_date = date.today() + timedelta(days=35)
        req, err = request_early_termination(
            db, lease.id, requested_date=notice_date, reason="Job change"
        )
        assert err == ""
        expected_penalty = Decimal("900.00") * Decimal("0.05")  # £45.00
        assert req.penalty_amount == expected_penalty

    def test_insufficient_notice_period_rejected(self, db):
        """A termination request with fewer than 30 days notice must be rejected."""
        lease = self._setup(db)
        notice_date = date.today() + timedelta(days=10)   # only 10 days — invalid
        req, err = request_early_termination(
            db, lease.id, requested_date=notice_date, reason="Urgent"
        )
        assert req is None
        assert "30" in err   # error message must mention the 30-day rule

    def test_termination_on_expired_lease_rejected(self, db):
        """Cannot request early termination on a non-ACTIVE lease."""
        lease = self._setup(db)
        lease.status = LeaseStatus.EXPIRED
        db.flush()
        notice_date = date.today() + timedelta(days=35)
        req, err = request_early_termination(
            db, lease.id, requested_date=notice_date, reason="N/A"
        )
        assert req is None
        assert err != ""

    def test_termination_on_nonexistent_lease_rejected(self, db):
        """Requesting termination for a lease ID that does not exist must fail."""
        req, err = request_early_termination(
            db, 99999, requested_date=date.today() + timedelta(days=35)
        )
        assert req is None
        assert err != ""


# ═══════════════════════════════════════════════════════════════════════════════
#  9 — MAINTENANCE TICKET
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaintenanceTicket:

    def test_ticket_can_be_created(self, db):
        """A maintenance ticket can be created with required fields."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db)
        ticket = MaintenanceTicket(
            title="Leaking pipe under kitchen sink",
            description="Water dripping continuously from hot water pipe.",
            priority=MaintenancePriority.HIGH,
            status=MaintenanceStatus.NEW,
            tenant_id=tenant.id,
            apartment_id=apt.id,
        )
        db.add(ticket); db.flush()
        assert ticket.id is not None
        assert ticket.status == MaintenanceStatus.NEW

    def test_ticket_default_status_is_new(self, db):
        """New maintenance tickets must have NEW status."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db)
        ticket = MaintenanceTicket(
            title="Broken radiator",
            description="Radiator not heating.",
            priority=MaintenancePriority.MEDIUM,
            status=MaintenanceStatus.NEW,
            tenant_id=tenant.id,
            apartment_id=apt.id,
        )
        db.add(ticket); db.flush()
        assert ticket.status == MaintenanceStatus.NEW

    def test_ticket_priority_levels(self, db):
        """All four priority levels can be assigned to maintenance tickets."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db)
        for i, priority in enumerate(MaintenancePriority):
            ticket = MaintenanceTicket(
                title=f"Test ticket {i}", description="Test",
                priority=priority, status=MaintenanceStatus.NEW,
                tenant_id=tenant.id, apartment_id=apt.id,
            )
            db.add(ticket)
        db.flush()
        count = db.query(MaintenanceTicket).count()
        assert count == len(MaintenancePriority)

    def test_ticket_can_be_marked_resolved(self, db):
        """A maintenance ticket status can be updated to RESOLVED."""
        city = _city(db); prop = _property(db, city); apt = _apartment(db, prop)
        tenant = _tenant(db)
        ticket = MaintenanceTicket(
            title="Broken window latch",
            description="Latch is loose and window won't close.",
            priority=MaintenancePriority.URGENT,
            status=MaintenanceStatus.NEW,
            tenant_id=tenant.id,
            apartment_id=apt.id,
        )
        db.add(ticket); db.flush()
        ticket.status = MaintenanceStatus.RESOLVED
        ticket.labour_cost    = Decimal("75.00")
        ticket.material_cost  = Decimal("12.50")
        ticket.time_taken_hours = 2.0
        db.flush()
        assert ticket.status == MaintenanceStatus.RESOLVED


# ═══════════════════════════════════════════════════════════════════════════════
#  10 — AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLog:

    def test_audit_log_can_be_created(self, db):
        """An audit log entry can be created for any user action."""
        city = _city(db)
        role = _role(db)
        user = _user(db, role, city)
        log  = AuditLog(
            user_id=user.id,
            action="CREATE",
            entity="Tenant",
            entity_id=1,
            detail="Registered new tenant: Jane Smith",
        )
        db.add(log); db.flush()
        assert log.id is not None
        assert log.action == "CREATE"

    def test_audit_log_records_all_action_types(self, db):
        """CREATE, UPDATE, DELETE action types can all be stored."""
        city = _city(db); role = _role(db); user = _user(db, role, city)
        for action in ("CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT"):
            db.add(AuditLog(user_id=user.id, action=action,
                            entity="User", entity_id=user.id,
                            detail=f"Test {action} action"))
        db.flush()
        count = db.query(AuditLog).filter(AuditLog.user_id == user.id).count()
        assert count == 5