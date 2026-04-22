# Ahmet (24034408) Efe Genc (23001693)  ·  Dan McNamara (23037788)
"""
app/db/seed_demo_data.py
=========================
Seeds realistic demo data across all 4 Paragon cities:
  - Properties and apartments
  - Staff users per city
  - Tenants with leases
  - Invoices and payments
  - Maintenance tickets
  - Complaints

Run AFTER seed_data.py:
    python -m app.db.seed_demo_data

Safe to re-run — skips existing records.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from app.db.database import SessionLocal, engine
from app.db.models import Base


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        _seed_properties_and_apartments(db)
        _seed_staff_users(db)
        _seed_tenants_and_leases(db)
        _seed_invoices_and_payments(db)
        _seed_maintenance_tickets(db)
        _seed_complaints(db)
        print("\n✓ Demo data seeded successfully.")
        print("  Log in as admin / admin123 to see the full dataset.")
    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()


# ── Properties & Apartments ───────────────────────────────────────────────────

def _seed_properties_and_apartments(db):
    from app.db.models import City, Property, Apartment, ApartmentType, ApartmentStatus

    cities = {c.name: c for c in db.query(City).all()}
    if not cities:
        print("  ✗ No cities found — run seed_data.py first")
        return

    PROPERTIES = [
        {"city": "Bristol",    "name": "Paragon Bristol Central",  "address": "12 College Green, Bristol",      "postcode": "BS1 5SJ"},
        {"city": "Bristol",    "name": "Paragon Bristol Harbourside","address": "8 Anchor Road, Bristol",        "postcode": "BS1 5TT"},
        {"city": "London",     "name": "Paragon London Mayfair",   "address": "45 Park Lane, London",           "postcode": "W1K 1PN"},
        {"city": "London",     "name": "Paragon London Shoreditch","address": "22 Curtain Road, London",        "postcode": "EC2A 3NZ"},
        {"city": "Cardiff",    "name": "Paragon Cardiff Bay",      "address": "6 Mermaid Quay, Cardiff",        "postcode": "CF10 5BZ"},
        {"city": "Manchester", "name": "Paragon Manchester NQ",    "address": "34 Northern Quarter, Manchester","postcode": "M1 1JF"},
    ]

    APARTMENTS = {
        "Paragon Bristol Central": [
            ("A01", 0, "studio",    1, 720),
            ("A02", 0, "one_bed",   1, 950),
            ("A03", 1, "two_bed",   2, 1400),
            ("A04", 1, "two_bed",   2, 1450),
            ("A05", 2, "three_bed", 3, 2000),
        ],
        "Paragon Bristol Harbourside": [
            ("B01", 0, "one_bed",  1, 1100),
            ("B02", 0, "one_bed",  1, 1050),
            ("B03", 1, "two_bed",  2, 1600),
            ("B04", 2, "three_bed",3, 2200),
        ],
        "Paragon London Mayfair": [
            ("M01", 0, "one_bed",  1, 2800),
            ("M02", 0, "two_bed",  2, 3500),
            ("M03", 1, "two_bed",  2, 3800),
            ("M04", 1, "three_bed",3, 5000),
            ("M05", 2, "four_bed", 4, 7500),
        ],
        "Paragon London Shoreditch": [
            ("S01", 0, "studio",   1, 1800),
            ("S02", 0, "one_bed",  1, 2200),
            ("S03", 1, "two_bed",  2, 3100),
        ],
        "Paragon Cardiff Bay": [
            ("C01", 0, "one_bed",  1, 850),
            ("C02", 0, "two_bed",  2, 1200),
            ("C03", 1, "two_bed",  2, 1250),
            ("C04", 1, "three_bed",3, 1800),
        ],
        "Paragon Manchester NQ": [
            ("N01", 0, "studio",   1, 750),
            ("N02", 0, "one_bed",  1, 950),
            ("N03", 1, "two_bed",  2, 1350),
            ("N04", 1, "two_bed",  2, 1400),
            ("N05", 2, "three_bed",3, 1900),
        ],
    }

    prop_map = {}
    added_props = 0
    for p_data in PROPERTIES:
        city = cities.get(p_data["city"])
        if not city:
            continue
        existing = db.query(Property).filter(Property.name == p_data["name"]).first()
        if not existing:
            prop = Property(
                city_id=city.id,
                name=p_data["name"],
                address=p_data["address"],
                postcode=p_data["postcode"],
                is_active=True,
            )
            db.add(prop)
            db.flush()
            prop_map[p_data["name"]] = prop
            added_props += 1
        else:
            prop_map[p_data["name"]] = existing

    db.commit()
    print(f"  ✓ {added_props} properties added")

    added_apts = 0
    for prop_name, units in APARTMENTS.items():
        prop = prop_map.get(prop_name)
        if not prop:
            continue
        for unit_num, floor, apt_type, rooms, rent in units:
            existing = db.query(Apartment).filter(
                Apartment.property_id == prop.id,
                Apartment.unit_number == unit_num,
            ).first()
            if not existing:
                db.add(Apartment(
                    property_id=prop.id,
                    unit_number=unit_num,
                    floor=floor,
                    apartment_type=ApartmentType(apt_type),
                    room_count=rooms,
                    monthly_rent=Decimal(str(rent)),
                    status=ApartmentStatus.AVAILABLE,
                ))
                added_apts += 1

    db.commit()
    print(f"  ✓ {added_apts} apartments added")


# ── Staff Users ───────────────────────────────────────────────────────────────

def _seed_staff_users(db):
    from app.db.models import User, Role, RoleName, City
    from app.auth.security import hash_password

    cities = {c.name: c for c in db.query(City).all()}
    roles  = {r.name: r for r in db.query(Role).all()}

    STAFF = [
        # Bristol
        {"username":"bristol_admin",   "full_name":"Sarah Collins",   "role":RoleName.LOCATION_ADMIN,   "city":"Bristol",    "pw":"Bristol123"},
        {"username":"bristol_finance",  "full_name":"Mark Hughes",     "role":RoleName.FINANCE_MANAGER,  "city":"Bristol",    "pw":"Bristol123"},
        {"username":"bristol_desk",     "full_name":"Emma Davies",     "role":RoleName.FRONT_DESK,       "city":"Bristol",    "pw":"Bristol123"},
        {"username":"bristol_maint1",   "full_name":"Aaron Smith",     "role":RoleName.MAINTENANCE_STAFF,"city":"Bristol",    "pw":"Bristol123"},
        {"username":"bristol_maint2",   "full_name":"Hylie Jones",     "role":RoleName.MAINTENANCE_STAFF,"city":"Bristol",    "pw":"Bristol123"},
        # London
        {"username":"london_admin",     "full_name":"James Fletcher",  "role":RoleName.LOCATION_ADMIN,   "city":"London",     "pw":"London123"},
        {"username":"london_finance",   "full_name":"Priya Sharma",    "role":RoleName.FINANCE_MANAGER,  "city":"London",     "pw":"London123"},
        {"username":"london_desk",      "full_name":"Oliver Chen",     "role":RoleName.FRONT_DESK,       "city":"London",     "pw":"London123"},
        {"username":"london_maint1",    "full_name":"Ben Carter",      "role":RoleName.MAINTENANCE_STAFF,"city":"London",     "pw":"London123"},
        # Cardiff
        {"username":"cardiff_admin",    "full_name":"Rhys Morgan",     "role":RoleName.LOCATION_ADMIN,   "city":"Cardiff",    "pw":"Cardiff123"},
        {"username":"cardiff_desk",     "full_name":"Sian Williams",   "role":RoleName.FRONT_DESK,       "city":"Cardiff",    "pw":"Cardiff123"},
        {"username":"cardiff_maint1",   "full_name":"Tom Evans",       "role":RoleName.MAINTENANCE_STAFF,"city":"Cardiff",    "pw":"Cardiff123"},
        # Manchester
        {"username":"manchester_admin", "full_name":"Lisa Patel",      "role":RoleName.LOCATION_ADMIN,   "city":"Manchester", "pw":"Manchester123"},
        {"username":"manchester_desk",  "full_name":"Jake Wilson",     "role":RoleName.FRONT_DESK,       "city":"Manchester", "pw":"Manchester123"},
        {"username":"manchester_maint1","full_name":"Dan Thompson",    "role":RoleName.MAINTENANCE_STAFF,"city":"Manchester", "pw":"Manchester123"},
    ]

    added = 0
    for s in STAFF:
        if db.query(User).filter(User.username == s["username"]).first():
            continue
        city = cities.get(s["city"])
        role = roles.get(s["role"])
        if not city or not role:
            continue
        db.add(User(
            username=s["username"],
            password_hash=hash_password(s["pw"]),
            full_name=s["full_name"],
            role_id=role.id,
            city_id=city.id,
            is_active=True,
        ))
        added += 1

    db.commit()
    print(f"  ✓ {added} staff users added")


# ── Tenants & Leases ─────────────────────────────────────────────────────────

def _seed_tenants_and_leases(db):
    from app.db.models import Tenant, LeaseAgreement, LeaseStatus, Apartment, ApartmentStatus, Property, City

    TENANTS = [
        # Bristol
        {"name":"James Hartley",    "email":"j.hartley@gmail.com",    "phone":"07711000001","city":"Bristol",    "unit":"A01","rent":720,  "start":date(2025,6,1),  "end":date(2026,6,1)},
        {"name":"Sophie Walsh",     "email":"s.walsh@hotmail.com",    "phone":"07711000002","city":"Bristol",    "unit":"A02","rent":950,  "start":date(2025,8,1),  "end":date(2027,8,1)},
        {"name":"Mohammed Al-Rashid","email":"m.alrashid@gmail.com",  "phone":"07711000003","city":"Bristol",    "unit":"A03","rent":1400, "start":date(2025,3,1),  "end":date(2027,3,1)},
        {"name":"Emily Carter",     "email":"e.carter@icloud.com",    "phone":"07711000004","city":"Bristol",    "unit":"A04","rent":1450, "start":date(2026,1,1),  "end":date(2028,1,1)},
        # London
        {"name":"Oliver Bennett",   "email":"o.bennett@yahoo.co.uk",  "phone":"07711000005","city":"London",    "unit":"M01","rent":2800, "start":date(2025,9,1),  "end":date(2027,9,1)},
        {"name":"Priya Nair",       "email":"p.nair@outlook.com",     "phone":"07711000006","city":"London",    "unit":"M02","rent":3500, "start":date(2025,7,1),  "end":date(2027,7,1)},
        {"name":"Liam O'Connor",    "email":"l.oconnor@gmail.com",    "phone":"07711000007","city":"London",    "unit":"M03","rent":3800, "start":date(2026,2,1),  "end":date(2028,2,1)},
        # Cardiff
        {"name":"Aisha Patel",      "email":"a.patel@gmail.com",      "phone":"07711000008","city":"Cardiff",   "unit":"C01","rent":850,  "start":date(2025,11,1), "end":date(2027,11,1)},
        {"name":"Rhiannon James",   "email":"r.james@gmail.com",      "phone":"07711000009","city":"Cardiff",   "unit":"C02","rent":1200, "start":date(2026,1,1),  "end":date(2028,1,1)},
        # Manchester
        {"name":"Connor Burke",     "email":"c.burke@gmail.com",      "phone":"07711000010","city":"Manchester","unit":"N01","rent":750,  "start":date(2025,10,1), "end":date(2027,10,1)},
        {"name":"Fatima Hussain",   "email":"f.hussain@gmail.com",    "phone":"07711000011","city":"Manchester","unit":"N02","rent":950,  "start":date(2025,12,1), "end":date(2027,12,1)},
        {"name":"Daniel Park",      "email":"d.park@gmail.com",       "phone":"07711000012","city":"Manchester","unit":"N03","rent":1350, "start":date(2026,1,1),  "end":date(2028,1,1)},
    ]

    added_t = 0
    added_l = 0

    for td in TENANTS:
        # Skip if tenant email already exists
        if db.query(Tenant).filter(Tenant.email == td["email"]).first():
            continue

        tenant = Tenant(
            full_name=td["name"],
            email=td["email"],
            phone=td["phone"],
            is_active=True,
        )
        db.add(tenant)
        db.flush()
        added_t += 1

        # Find the apartment in this city
        city = db.query(City).filter(City.name == td["city"]).first()
        if not city:
            continue
        apt = (
            db.query(Apartment)
            .join(Property, Apartment.property_id == Property.id)
            .filter(Property.city_id == city.id, Apartment.unit_number == td["unit"])
            .first()
        )
        if not apt:
            continue

        # Create lease
        lease = LeaseAgreement(
            tenant_id=apt.id,   # will fix below
            apartment_id=apt.id,
            start_date=td["start"],
            end_date=td["end"],
            agreed_rent=Decimal(str(td["rent"])),
            deposit=Decimal(str(td["rent"] * 2)),
            status=LeaseStatus.ACTIVE,
        )
        lease.tenant_id = tenant.id
        db.add(lease)

        # Mark apartment occupied
        apt.status = ApartmentStatus.OCCUPIED
        added_l += 1

    db.commit()
    print(f"  ✓ {added_t} tenants added, {added_l} leases created")


# ── Invoices & Payments ───────────────────────────────────────────────────────

def _seed_invoices_and_payments(db):
    from app.db.models import (
        LeaseAgreement, LeaseStatus, Invoice, InvoiceStatus,
        Payment, PaymentMethod
    )
    from app.services.invoice_service import generate_invoice
    from app.services.receipt_service import create_receipt

    leases = db.query(LeaseAgreement).filter(
        LeaseAgreement.status == LeaseStatus.ACTIVE
    ).all()

    today = date.today()
    added_inv = 0
    added_pay = 0

    import calendar
    for lease in leases:
        # Generate invoices for the last 3 months
        for months_back in range(3, 0, -1):
            month = today.month - months_back
            year  = today.year
            while month <= 0:
                month += 12
                year  -= 1

            from datetime import date as _date
            last_day = calendar.monthrange(year, month)[1]
            period_start = _date(year, month, 1)
            period_end   = _date(year, month, last_day)
            due          = period_end

            inv, err = generate_invoice(
                db,
                lease_id=lease.id,
                billing_period_start=period_start,
                billing_period_end=period_end,
                due_date=due,
            )
            if err or not inv:
                continue
            added_inv += 1

            # Pay the oldest two, leave the most recent unpaid
            if months_back > 1:
                payment = Payment(
                    invoice_id=inv.id,
                    tenant_id=lease.tenant_id,
                    amount=inv.amount,
                    payment_method=PaymentMethod.CARD,
                    payment_date=datetime(year, month, 28),
                    reference=f"**** **** **** {1000 + lease.id:04d}",
                )
                db.add(payment)
                db.flush()
                inv.status = InvoiceStatus.PAID
                create_receipt(db, payment)
                added_pay += 1

    db.commit()
    print(f"  ✓ {added_inv} invoices generated, {added_pay} payments recorded")


# ── Maintenance Tickets ───────────────────────────────────────────────────────

def _seed_maintenance_tickets(db):
    from app.db.models import (
        LeaseAgreement, LeaseStatus, MaintenanceTicket,
        MaintenancePriority, MaintenanceStatus, MaintenanceUpdate,
        Apartment, Property, City, User, Role, RoleName
    )

    leases = db.query(LeaseAgreement).filter(
        LeaseAgreement.status == LeaseStatus.ACTIVE
    ).all()

    TICKETS = [
        {"title":"Boiler not heating",      "priority":"high",   "status":"in_progress", "note":"Engineer booked"},
        {"title":"Leaking tap in bathroom", "priority":"medium", "status":"resolved",    "note":"Fixed, new washer fitted"},
        {"title":"Broken window latch",     "priority":"low",    "status":"new",         "note":""},
        {"title":"Damp patch on ceiling",   "priority":"urgent", "status":"triaged",     "note":"Surveyor visit arranged"},
        {"title":"No hot water",            "priority":"urgent", "status":"closed",      "note":"Boiler replaced"},
    ]

    added = 0
    for i, lease in enumerate(leases[:8]):  # First 8 leases get tickets
        template = TICKETS[i % len(TICKETS)]

        # Check if ticket already exists for this apartment
        existing = db.query(MaintenanceTicket).filter(
            MaintenanceTicket.apartment_id == lease.apartment_id,
            MaintenanceTicket.title == template["title"],
        ).first()
        if existing:
            continue

        # Find maintenance staff in same city
        apt = db.query(Apartment).filter(Apartment.id == lease.apartment_id).first()
        prop = db.query(Property).filter(Property.id == apt.property_id).first() if apt else None
        maint_role = db.query(Role).filter(Role.name == RoleName.MAINTENANCE_STAFF).first()
        staff = None
        if prop and maint_role:
            staff = db.query(User).filter(
                User.role_id == maint_role.id,
                User.city_id == prop.city_id,
                User.is_active == True,
            ).first()

        ticket = MaintenanceTicket(
            apartment_id=lease.apartment_id,
            tenant_id=lease.tenant_id,
            title=template["title"],
            priority=MaintenancePriority(template["priority"]),
            status=MaintenanceStatus(template["status"]),
            assigned_to=staff.id if staff else None,
            created_at=datetime.now() - timedelta(days=10 - i),
        )
        db.add(ticket)
        db.flush()

        if template["note"]:
            db.add(MaintenanceUpdate(
                ticket_id=ticket.id,
                updated_by=staff.id if staff else None,
                old_status=MaintenanceStatus.NEW,
                new_status=MaintenanceStatus(template["status"]),
                note=template["note"],
                created_at=datetime.now() - timedelta(days=5),
            ))
        added += 1

    db.commit()
    print(f"  ✓ {added} maintenance tickets added")


# ── Complaints ────────────────────────────────────────────────────────────────

def _seed_complaints(db):
    from app.db.models import (
        LeaseAgreement, LeaseStatus, Complaint,
        ComplaintCategory, ComplaintStatus
    )

    leases = db.query(LeaseAgreement).filter(
        LeaseAgreement.status == LeaseStatus.ACTIVE
    ).all()

    COMPLAINTS = [
        {"subject":"Noise from upstairs neighbour",  "cat":"noise",       "status":"open"},
        {"subject":"Overcharged on last invoice",    "cat":"billing",     "status":"under_review"},
        {"subject":"Hallway light not working",      "cat":"maintenance", "status":"resolved",
         "resolution":"Bulb replaced by maintenance team."},
        {"subject":"Rude response from front desk",  "cat":"staff_conduct","status":"closed",
         "resolution":"Issue reviewed and addressed with staff member."},
    ]

    added = 0
    for i, lease in enumerate(leases[:6]):
        template = COMPLAINTS[i % len(COMPLAINTS)]

        existing = db.query(Complaint).filter(
            Complaint.tenant_id == lease.tenant_id,
            Complaint.subject == template["subject"],
        ).first()
        if existing:
            continue

        complaint = Complaint(
            tenant_id=lease.tenant_id,
            category=ComplaintCategory(template["cat"]),
            subject=template["subject"],
            status=ComplaintStatus(template["status"]),
            resolution_notes=template.get("resolution"),
        )
        db.add(complaint)
        added += 1

    db.commit()
    print(f"  ✓ {added} complaints added")


if __name__ == "__main__":
    seed()