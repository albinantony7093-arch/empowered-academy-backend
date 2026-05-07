"""
Adds is_flagship column to courses table and marks NEET UG and NEET PG as flagship.

Usage:
    docker compose exec web python migrate_flagship_column.py
"""
from app.core.database import SessionLocal, engine
from sqlalchemy import text


def migrate():
    with engine.connect() as conn:
        # Add column if it doesn't exist
        conn.execute(text("""
            ALTER TABLE courses
            ADD COLUMN IF NOT EXISTS is_flagship BOOLEAN NOT NULL DEFAULT FALSE
        """))
        conn.commit()
        print("[done] Added is_flagship column to courses table")

        # Mark NEET UG and NEET PG as flagship
        result = conn.execute(text("""
            UPDATE courses
            SET is_flagship = TRUE
            WHERE title IN ('NEET UG', 'NEET PG')
        """))
        conn.commit()
        print(f"[done] Marked {result.rowcount} course(s) as flagship")


if __name__ == "__main__":
    migrate()
