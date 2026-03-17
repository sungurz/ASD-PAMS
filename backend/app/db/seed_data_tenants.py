"""
app/db/seed_demo_tenants.py
============================
Seeds 8 realistic UK demo tenants for testing.
Safe to run multiple times — skips existing emails.

Run with:
    python -m app.db.seed_demo_tenants
"""

from datetime import date
from app.db.database import SessionLocal, engine
from app.db.models import Base, Tenant


DEMO_TENANTS = [
    {
        "full_name":               "James Hartley",
        "email":                   "james.hartley@gmail.com",
        "phone":                   "07712345601",
        "date_of_birth":           date(1990, 3, 14),
        "ni_number_masked":        "JH ** ** 14 A",
        "occupation":              "Software Engineer",
        "employer_name":           "TechCorp Ltd",
        "employer_phone":          "01174561200",
        "annual_income":           62000,
        "emergency_contact_name":  "Susan Hartley",
        "emergency_contact_phone": "07712345600",
    },
    {
        "full_name":               "Priya Nair",
        "email":                   "priya.nair@outlook.com",
        "phone":                   "07823456702",
        "date_of_birth":           date(1995, 7, 22),
        "ni_number_masked":        "PN ** ** 22 B",
        "occupation":              "Marketing Manager",
        "employer_name":           "BrandWave Agency",
        "employer_phone":          "02071234567",
        "annual_income":           48000,
        "emergency_contact_name":  "Ravi Nair",
        "emergency_contact_phone": "07823456700",
    },
    {
        "full_name":               "Oliver Bennett",
        "email":                   "oliver.bennett@yahoo.co.uk",
        "phone":                   "07934567803",
        "date_of_birth":           date(1988, 11, 5),
        "ni_number_masked":        "OB ** ** 05 C",
        "occupation":              "Architect",
        "employer_name":           "Bennett & Partners",
        "employer_phone":          "01174009988",
        "annual_income":           75000,
        "emergency_contact_name":  "Claire Bennett",
        "emergency_contact_phone": "07934567800",
    },
    {
        "full_name":               "Sophie Walsh",
        "email":                   "sophie.walsh@hotmail.com",
        "phone":                   "07645678904",
        "date_of_birth":           date(1997, 1, 30),
        "ni_number_masked":        "SW ** ** 30 D",
        "occupation":              "Nurse",
        "employer_name":           "Bristol Royal Infirmary",
        "employer_phone":          "01179230000",
        "annual_income":           38000,
        "emergency_contact_name":  "Tom Walsh",
        "emergency_contact_phone": "07645678900",
    },
    {
        "full_name":               "Mohammed Al-Rashid",
        "email":                   "m.alrashid@gmail.com",
        "phone":                   "07756789005",
        "date_of_birth":           date(1985, 6, 18),
        "ni_number_masked":        "MA ** ** 18 E",
        "occupation":              "Financial Analyst",
        "employer_name":           "Barclays Capital",
        "employer_phone":          "02071234000",
        "annual_income":           90000,
        "emergency_contact_name":  "Fatima Al-Rashid",
        "emergency_contact_phone": "07756789000",
    },
    {
        "full_name":               "Emily Carter",
        "email":                   "emily.carter@icloud.com",
        "phone":                   "07867890106",
        "date_of_birth":           date(1993, 9, 9),
        "ni_number_masked":        "EC ** ** 09 F",
        "occupation":              "Graphic Designer",
        "employer_name":           "Creative Studio Ltd",
        "employer_phone":          "02920123456",
        "annual_income":           35000,
        "emergency_contact_name":  "David Carter",
        "emergency_contact_phone": "07867890100",
    },
    {
        "full_name":               "Liam O'Connor",
        "email":                   "liam.oconnor@gmail.com",
        "phone":                   "07978901207",
        "date_of_birth":           date(1991, 4, 25),
        "ni_number_masked":        "LO ** ** 25 G",
        "occupation":              "Civil Engineer",
        "employer_name":           "UrbanBuild Contractors",
        "employer_phone":          "01612345678",
        "annual_income":           55000,
        "emergency_contact_name":  "Mary O'Connor",
        "emergency_contact_phone": "07978901200",
    },
    {
        "full_name":               "Aisha Patel",
        "email":                   "aisha.patel@gmail.com",
        "phone":                   "07589012308",
        "date_of_birth":           date(1999, 12, 3),
        "ni_number_masked":        "AP ** ** 03 H",
        "occupation":              "Junior Accountant",
        "employer_name":           "Deloitte UK",
        "employer_phone":          "02073036000",
        "annual_income":           29000,
        "emergency_contact_name":  "Raj Patel",
        "emergency_contact_phone": "07589012300",
    },
]


def seed_tenants():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    added = 0
    skipped = 0

    try:
        for data in DEMO_TENANTS:
            existing = db.query(Tenant).filter(Tenant.email == data["email"]).first()
            if existing:
                skipped += 1
                continue

            tenant = Tenant(
                full_name=data["full_name"],
                email=data["email"],
                phone=data["phone"],
                date_of_birth=data.get("date_of_birth"),
                ni_number_masked=data.get("ni_number_masked"),
                occupation=data.get("occupation"),
                employer_name=data.get("employer_name"),
                employer_phone=data.get("employer_phone"),
                annual_income=data.get("annual_income"),
                emergency_contact_name=data.get("emergency_contact_name"),
                emergency_contact_phone=data.get("emergency_contact_phone"),
                is_active=True,
            )
            db.add(tenant)
            added += 1

        db.commit()
        print(f"\nDemo tenants seeded:")
        print(f"  ✓ {added} tenant(s) added")
        if skipped:
            print(f"  — {skipped} already existed, skipped")
        print("\nTenants added:")
        for t in DEMO_TENANTS:
            print(f"  {t['full_name']} — {t['occupation']} — £{t['annual_income']:,}/yr")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_tenants()