"""
Seeds:
  1. A page_admin user  (username=academyadmin, password=academyadmin)
  2. NEET UG and NEET PG courses

Usage:
    docker compose exec web python seed_courses.py
"""
from app.core.database import SessionLocal, engine, Base
import app.models.user
import app.models.course
import app.models.test_attempt

from app.models.user import User
from app.models.course import Course
from app.core.security import hash_password
from sqlalchemy.orm.attributes import flag_modified

PAGE_ADMIN_EMAIL    = "academyadmin"
PAGE_ADMIN_PASSWORD = "academyadmin"

COURSES = [
    {
        "title": "NEET UG",
        "exam": "UG",
        "description": "Complete preparation for NEET covering Physics, Chemistry and Biology.",
        "keypoints": ["3000+ Questions", "Previous Year Papers", "Mock Tests", "Detailed Solutions"],
        "price": 0,
    },
    {
        "title": "NEET PG",
        "exam": "PG",
        "description": "Comprehensive preparation for NEET Postgraduate covering all clinical and pre-clinical subjects.",
        "keypoints": ["10000+ Questions", "Previous Year Papers", "Mock Tests", "Detailed Solutions"],
        "price": 0,
    },
]


def seed():
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    try:
        # ── 1. Create page_admin user ─────────────────────────────────────────
        existing = db.query(User).filter(User.email == PAGE_ADMIN_EMAIL).first()
        if existing:
            print(f"  [skip] page_admin '{PAGE_ADMIN_EMAIL}' already exists")
            page_admin = existing
        else:
            page_admin = User(
                email=PAGE_ADMIN_EMAIL,
                hashed_password=hash_password(PAGE_ADMIN_PASSWORD),
                full_name="Academy Admin",
                role="page_admin",
            )
            db.add(page_admin)
            db.commit()
            db.refresh(page_admin)
            print(f"  [add]  page_admin user '{PAGE_ADMIN_EMAIL}' created")

        # ── 2. Seed courses ───────────────────────────────────────────────────
        for data in COURSES:
            exists = db.query(Course).filter(Course.title == data["title"]).first()
            if exists:
                # Update keypoints and description if already seeded
                exists.description = data["description"]
                exists.keypoints = data["keypoints"]
                flag_modified(exists, "keypoints")
                db.commit()
                print(f"  [update] course '{data['title']}' keypoints updated")
                continue
            course = Course(
                title=data["title"],
                description=data["description"],
                exam=data["exam"],
                keypoints=data["keypoints"],
                price=data["price"],
                created_by=page_admin.id,
            )
            db.add(course)
            print(f"  [add]  course '{data['title']}'")

        db.commit()
        print("\nSeed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
