"""
Adds detailed_description column to courses table and populates it for NEET UG and NEET PG.

Usage:
    docker compose exec api python migrate_detailed_description.py
"""
from app.core.database import engine
from sqlalchemy import text

NEET_UG_DETAIL = """Our NEET UG course is a comprehensive, structured program designed to take students from foundational concepts to exam-ready mastery. The curriculum covers all three core subjects — Physics, Chemistry, and Biology — aligned with the latest NTA syllabus.

Physics: Mechanics, Thermodynamics, Optics, Electrostatics, Magnetism, Modern Physics, and more. Each topic is broken down with concept clarity videos, formula sheets, and application-based questions.

Chemistry: Physical, Organic, and Inorganic Chemistry covered in depth. Special focus on reaction mechanisms, periodic trends, and high-weightage chapters like Coordination Compounds and Biomolecules.

Biology: Detailed coverage of Botany and Zoology including Cell Biology, Genetics, Human Physiology, Ecology, and Evolution. NCERT-based approach with additional high-yield question banks.

The course includes 3000+ practice questions, full-length mock tests modeled on the actual NEET UG pattern, previous year papers with detailed solutions, and performance analytics to track your progress. Ideal for Class 11, Class 12, and repeater students aiming for top medical colleges."""

NEET_PG_DETAIL = """Our NEET PG course is built for MBBS graduates targeting postgraduate medical admissions. It covers the complete NBE-prescribed syllabus across all 19 subjects with a strong emphasis on clinical reasoning, image-based questions, and recent advances.

Pre-clinical & Para-clinical Subjects: Anatomy, Physiology, Biochemistry, Pathology, Microbiology, Pharmacology, and Forensic Medicine — each covered with high-yield notes and subject-wise question banks.

Clinical Subjects: Medicine, Surgery, Obstetrics & Gynaecology, Paediatrics, Orthopaedics, Ophthalmology, ENT, Psychiatry, Dermatology, Radiology, and Anaesthesia — with case-based questions and clinical vignettes that mirror the actual exam format.

The course features 10,000+ questions with detailed explanations, previous year NEET PG and INI-CET papers, grand mock tests with all-India ranking, revision modules for rapid recall, and regular updates incorporating the latest guidelines and exam trends. Designed for focused, time-efficient preparation to help you secure your preferred specialty and college."""


def migrate():
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE courses
            ADD COLUMN IF NOT EXISTS detailed_description TEXT
        """))
        conn.commit()
        print("[done] Added detailed_description column")

        conn.execute(text("""
            UPDATE courses SET detailed_description = :detail WHERE title = 'NEET UG'
        """), {"detail": NEET_UG_DETAIL})

        conn.execute(text("""
            UPDATE courses SET detailed_description = :detail WHERE title = 'NEET PG'
        """), {"detail": NEET_PG_DETAIL})

        conn.commit()
        print("[done] Populated detailed_description for NEET UG and NEET PG")


if __name__ == "__main__":
    migrate()
