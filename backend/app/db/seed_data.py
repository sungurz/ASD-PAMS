"""
Seeds the database with:
  1. All 6 roles with their permission sets
  2. The 4 Paragon cities
  3. A default system admin account

Run ONCE after create_tables has run.
"""
from app.db.database import SessionLocal, engine
from app.db.models import Base, Role, RoleName, City, User
from app.auth.security import hash_password


# ── Permission sets per role
# Format: "module.action"  — checked in the service layer
ROLE_PERMISSIONS = {
    RoleName.TENANT: [
        "dashboard.view",
        "invoice.view_own",
        "payment.view_own",
        "payment.make",
        "maintenance.create",
        "maintenance.view_own",
        "complaint.create",
        "complaint.view_own",
        "notification.view_own",
    ],
    RoleName.FRONT_DESK: [
        "tenant.create",
        "tenant.view",
        "tenant.update",
        "tenant.archive",
        "lease.create",
        "lease.view",
        "apartment.view",
        "complaint.create",
        "complaint.view",
        "complaint.update",
        "maintenance.create",
        "maintenance.view",
        "maintenance.update",
        "notification.send",
    ],
    RoleName.FINANCE_MANAGER: [
        "invoice.create",
        "invoice.view",
        "invoice.update",
        "invoice.void",
        "payment.create",
        "payment.view",
        "payment.update",
        "receipt.create",
        "receipt.view",
        "late_payment.view",
        "late_payment.flag",
        "report.finance",
        "tenant.view",
        "lease.view",
    ],
    RoleName.MAINTENANCE_STAFF: [
        "maintenance.view",
        "maintenance.create",
        "maintenance.update",
        "maintenance.close",
        "apartment.view",
        "tenant.view",
    ],
    RoleName.LOCATION_ADMIN: [
        # Full control within their city
        "user.create",
        "user.view",
        "user.update",
        "user.deactivate",
        "tenant.create",
        "tenant.view",
        "tenant.update",
        "tenant.archive",
        "tenant.view_ni",
        "apartment.create",
        "apartment.view",
        "apartment.update",
        "lease.create",
        "lease.view",
        "lease.update",
        "lease.terminate",
        "invoice.create",
        "invoice.view",
        "invoice.void",
        "payment.create",
        "payment.view",
        "maintenance.create",
        "maintenance.view",
        "maintenance.update",
        "maintenance.assign",
        "complaint.create",
        "complaint.view",
        "complaint.update",
        "complaint.assign",
        "report.local",
        "audit_log.view",
        "notification.send",
    ],
    RoleName.MANAGER: [
        # Cross-city oversight
        "user.create",
        "user.view",
        "user.update",
        "user.deactivate",
        "tenant.create",
        "tenant.view",
        "tenant.update",
        "tenant.archive",
        "tenant.view_ni",
        "apartment.create",
        "apartment.view",
        "apartment.update",
        "lease.create",
        "lease.view",
        "lease.update",
        "lease.terminate",
        "invoice.create",
        "invoice.view",
        "invoice.void",
        "payment.create",
        "payment.view",
        "maintenance.create",
        "maintenance.view",
        "maintenance.update",
        "maintenance.assign",
        "complaint.create",
        "complaint.view",
        "complaint.update",
        "complaint.assign",
        "report.local",
        "report.crosscity",
        "report.finance",
        "city.create",
        "city.view",
        "audit_log.view",
        "notification.send",
    ],
}

ROLE_DESCRIPTIONS = {
    RoleName.TENANT:            "Tenant portal access — self-service only",
    RoleName.FRONT_DESK:        "Registers tenants, creates complaints and maintenance requests",
    RoleName.FINANCE_MANAGER:   "Manages invoices, payments, and financial reports",
    RoleName.MAINTENANCE_STAFF: "Views and updates assigned maintenance jobs",
    RoleName.LOCATION_ADMIN:    "Full operational control within one city",
    RoleName.MANAGER:           "Cross-city oversight and reporting",
}


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── 1. Roles ──────────────────────────────────────────────────────────
        print("Seeding roles...")
        role_map = {}
        for role_name, perms in ROLE_PERMISSIONS.items():
            existing = db.query(Role).filter(Role.name == role_name).first()
            if existing:
                existing.permissions = ",".join(perms)
                role_map[role_name] = existing
            else:
                role = Role(
                    name=role_name,
                    description=ROLE_DESCRIPTIONS[role_name],
                    permissions=",".join(perms),
                )
                db.add(role)
                db.flush()
                role_map[role_name] = role
        db.commit()
        print(f"  ✓ {len(role_map)} roles ready")

        # ── 2. Cities ─────────────────────────────────────────────────────────
        print("Seeding cities...")
        cities = ["Bristol", "Cardiff", "London", "Manchester"]
        for city_name in cities:
            if not db.query(City).filter(City.name == city_name).first():
                db.add(City(name=city_name))
        db.commit()
        print(f"  ✓ {len(cities)} cities ready")

        # ── 3. System admin user ──────────────────────────────────────────────
        print("Seeding admin user...")
        admin_role = db.query(Role).filter(Role.name == RoleName.MANAGER).first()
        if not db.query(User).filter(User.username == "admin").first():
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="System Administrator",
                email="admin@paragon.co.uk",
                role_id=admin_role.id,
                city_id=None,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print("   Admin created  |  username: admin  |  password: admin123")
        else:
            print("   Admin already exists")

        print("\nSeed complete. Paragon database is ready.")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()