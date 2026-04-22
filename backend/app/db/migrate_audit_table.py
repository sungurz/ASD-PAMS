# Ahmet (24034408) 
from app.db.database import engine
from sqlalchemy import text, inspect


def migrate():
    inspector = inspect(engine)

    # Check if audit_logs table exists at all
    if "audit_logs" not in inspector.get_table_names():
        print("audit_logs table not found — running create_tables first...")
        from app.db.database import Base
        from app.db.models import AuditLog  # noqa — ensure model is loaded
        Base.metadata.create_all(bind=engine)
        print("✓ audit_logs table created")
        return

    # Get existing columns
    existing = {col["name"] for col in inspector.get_columns("audit_logs")}
    print(f"Existing columns: {existing}")

    COLUMNS_TO_ADD = [
        ("username",  "VARCHAR(100)"),
        ("entity",    "VARCHAR(100)"),
        ("entity_id", "INT"),
        ("detail",    "TEXT"),
    ]

    with engine.connect() as conn:
        added = 0
        for col_name, col_type in COLUMNS_TO_ADD:
            if col_name not in existing:
                conn.execute(text(
                    f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}"
                ))
                print(f"  ✓ Added column: {col_name}")
                added += 1
            else:
                print(f"  — Column already exists: {col_name}")
        conn.commit()

    if added:
        print(f"\n✓ Migration complete — {added} column(s) added")
    else:
        print("\n✓ Already up to date — no changes needed")


if __name__ == "__main__":
    migrate()