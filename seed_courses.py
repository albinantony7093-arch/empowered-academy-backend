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
        "detailed_description": (
            "Our NEET UG course is a comprehensive, structured program designed to take students from foundational concepts "
            "to exam-ready mastery. The curriculum covers all three core subjects — Physics, Chemistry, and Biology — "
            "aligned with the latest NTA syllabus.\n\n"
            "Physics: Mechanics, Thermodynamics, Optics, Electrostatics, Magnetism, Modern Physics, and more. "
            "Each topic is broken down with concept clarity videos, formula sheets, and application-based questions.\n\n"
            "Chemistry: Physical, Organic, and Inorganic Chemistry covered in depth. Special focus on reaction mechanisms, "
            "periodic trends, and high-weightage chapters like Coordination Compounds and Biomolecules.\n\n"
            "Biology: Detailed coverage of Botany and Zoology including Cell Biology, Genetics, Human Physiology, "
            "Ecology, and Evolution. NCERT-based approach with additional high-yield question banks.\n\n"
            "The course includes 3000+ practice questions, full-length mock tests modeled on the actual NEET UG pattern, "
            "previous year papers with detailed solutions, and performance analytics to track your progress. "
            "Ideal for Class 11, Class 12, and repeater students aiming for top medical colleges."
        ),
        "keypoints": ["3000+ Questions", "Previous Year Papers", "Mock Tests", "Detailed Solutions"],
        "price": 0,
        "is_flagship": True,
    },
    {
        "title": "NEET PG",
        "exam": "PG",
        "description": "Comprehensive preparation for NEET Postgraduate covering all clinical and pre-clinical subjects.",
        "detailed_description": (
            "Our NEET PG course is built for MBBS graduates targeting postgraduate medical admissions. "
            "It covers the complete NBE-prescribed syllabus across all 19 subjects with a strong emphasis on "
            "clinical reasoning, image-based questions, and recent advances.\n\n"
            "Pre-clinical & Para-clinical Subjects: Anatomy, Physiology, Biochemistry, Pathology, Microbiology, "
            "Pharmacology, and Forensic Medicine — each covered with high-yield notes and subject-wise question banks.\n\n"
            "Clinical Subjects: Medicine, Surgery, Obstetrics & Gynaecology, Paediatrics, Orthopaedics, "
            "Ophthalmology, ENT, Psychiatry, Dermatology, Radiology, and Anaesthesia — with case-based questions "
            "and clinical vignettes that mirror the actual exam format.\n\n"
            "The course features 10,000+ questions with detailed explanations, previous year NEET PG and INI-CET papers, "
            "grand mock tests with all-India ranking, revision modules for rapid recall, and regular updates "
            "incorporating the latest guidelines and exam trends. "
            "Designed for focused, time-efficient preparation to help you secure your preferred specialty and college."
        ),
        "keypoints": ["10000+ Questions", "Previous Year Papers", "Mock Tests", "Detailed Solutions"],
        "price": 0,
        "is_flagship": True,
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
                # Update keypoints, description, and flagship flag if already seeded
                exists.description = data["description"]
                exists.detailed_description = data.get("detailed_description")
                exists.keypoints = data["keypoints"]
                exists.is_flagship = data.get("is_flagship", False)
                flag_modified(exists, "keypoints")
                db.commit()
                print(f"  [update] course '{data['title']}' updated")
                continue
            course = Course(
                title=data["title"],
                description=data["description"],
                detailed_description=data.get("detailed_description"),
                exam=data["exam"],
                keypoints=data["keypoints"],
                price=data["price"],
                is_flagship=data.get("is_flagship", False),
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
