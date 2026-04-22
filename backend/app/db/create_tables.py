# Ahmet (24034408)
"""
Run this once to create all  tables in  database.
Safe to run multiple times — uses checkfirst so it won't
drop existing tables.

"""
from app.db.database import engine
from app.db.models import Base


def create_tables():
    print("Creating Paragon tables...")
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print("Done. All tables are ready.")


if __name__ == "__main__":
    create_tables()