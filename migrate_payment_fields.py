"""
Adds all new payment tracking columns to the payments table.

Usage:
    docker compose exec api python migrate_payment_fields.py
"""
from app.core.database import engine
from sqlalchemy import text

NEW_COLUMNS = [
    ("amount_due",       "NUMERIC(10,2)"),
    ("amount_paid",      "NUMERIC(10,2)"),
    ("bank",             "VARCHAR"),
    ("wallet",           "VARCHAR"),
    ("vpa",              "VARCHAR"),
    ("card_network",     "VARCHAR"),
    ("card_issuer",      "VARCHAR"),
    ("card_last4",       "VARCHAR"),
    ("international",    "VARCHAR"),
    ("contact",          "VARCHAR"),
    ("email",            "VARCHAR"),
    ("error_code",       "VARCHAR"),
    ("error_source",     "VARCHAR"),
    ("error_step",       "VARCHAR"),
    ("error_reason",     "VARCHAR"),
    ("dispute_id",       "VARCHAR"),
    ("dispute_reason",   "VARCHAR"),
    ("dispute_amount",   "NUMERIC(10,2)"),
    ("receipt",          "VARCHAR"),
    ("notes",            "JSONB"),
    ("webhook_payload",  "JSONB"),
    ("paid_at",          "TIMESTAMPTZ"),
    ("failed_at",        "TIMESTAMPTZ"),
    ("refunded_at",      "TIMESTAMPTZ"),
]

def migrate():
    with engine.connect() as conn:
        for col_name, col_type in NEW_COLUMNS:
            conn.execute(text(f"""
                ALTER TABLE payments
                ADD COLUMN IF NOT EXISTS {col_name} {col_type}
            """))
            print(f"  [ok] {col_name} {col_type}")

        # Index dispute_id for quick lookups
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_payments_dispute_id
            ON payments (dispute_id)
        """))

        conn.commit()
        print("\n[done] payments table updated with all new columns")


if __name__ == "__main__":
    migrate()
