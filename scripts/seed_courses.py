"""
Seed Script — Empowered Academy Course Data
============================================

PURPOSE:
    Creates or updates the 5 course cards in the database.
    Each plan (GOLD, PLATINUM) is its own Course row — the frontend
    groups them by the 'exam' field to show category headers.

    Resulting course cards:
        NEET UG category:
            - NEET UG GOLD     (paid, 6-month validity)
            - NEET UG PLATINUM (paid, lifetime)

        NEET PG category:
            - NEET PG GOLD     (paid, 6-month validity)
            - NEET PG PLATINUM (paid, 1-year validity)

        CRASH COURSE category:
            - Crash Course     (free, 30-day access)

HOW TO RUN:
    docker cp scripts/seed_courses.py empowered-academy-backend-api-1:/app/seed_courses.py
    docker exec empowered-academy-backend-api-1 python3 /app/seed_courses.py

BEHAVIOR:
    - Course doesn't exist → INSERT
    - Course already exists → UPDATE all fields
    - Safe to run multiple times (idempotent)

HOW LIMITS WORK:
    Trial period (before payment):
        free_questions_per_test  → questions per test during trial
        free_daily_test_limit    → max tests per day during trial
        free_trial_days          → how many days the trial lasts

    After payment:
        questions_per_test       → questions per test (NULL = unlimited)
        daily_test_limit         → max tests per day (NULL = unlimited)
        validity_days            → how long paid access lasts (NULL = lifetime)

    Crash Course (is_free=True):
        Uses free_* limits permanently — no payment, no upgrade.
        Access expires after free_trial_days days.
"""

import sys
sys.path.insert(0, "/app")

from app.core.database import SessionLocal
from app.models.user import User
from app.models.course import Course

db = SessionLocal()

# ── Find creator user ─────────────────────────────────────────────────────────
# Prefer admin role; fall back to any user if no admin exists yet.
admin = db.query(User).filter(User.role == "admin").first()
if not admin:
    admin = db.query(User).first()
if not admin:
    print("ERROR: No users found. Register a user first via POST /auth/register")
    sys.exit(1)

print(f"Using creator: {admin.email} (role={admin.role})\n")

# ── Course definitions ────────────────────────────────────────────────────────
courses_data = [
    {
        # ── NEET UG GOLD ──────────────────────────────────────────────────────
        # Entry-level paid plan for NEET UG aspirants.
        # Trial: 4 days, 30 questions/test, 4 tests/day
        # Paid:  6 months, 45 questions/test, 6 tests/day
        "title": "NEET UG GOLD",
        "description": (
            "The NEET UG Gold plan is designed for serious NEET UG aspirants who want structured, "
            "exam-focused practice over 6 months. Get access to thousands of high-yield MCQs across "
            "Physics, Chemistry, and Biology — curated from previous years' papers and the latest NMC syllabus. "
            "Each test is timed and mirrors the real NEET UG pattern with 45 questions per session. "
            "After every test, detailed subject-wise analytics show your strengths and weak areas so you "
            "can focus your revision where it matters most. Track your rank and percentile among all Gold "
            "plan students to benchmark your preparation. The built-in AI mentor reviews your performance "
            "and gives personalised feedback on topics you're struggling with. Ideal for students in Class 12 "
            "or repeaters targeting the upcoming NEET UG cycle."
        ),
        "exam": "NEET UG",          # groups this card under NEET UG category
        "price": 1999,
        "is_free": False,
        "is_flagship": True,
        "free_questions_per_test": 30,   # trial limit
        "free_daily_test_limit": 4,      # trial limit
        "free_trial_days": 4,            # trial lasts 4 days
        "questions_per_test": 45,        # paid limit
        "daily_test_limit": 6,           # paid limit
        "validity_days": 180,            # 6 months
        "keypoints": [
            "6 months access",
            "45 questions per test",
            "6 tests per day",
            "Subject-wise analytics",
            "Rank & percentile tracking",
            "AI mentor feedback",
        ],
    },
    {
        # ── NEET UG PLATINUM ─────────────────────────────────────────────────
        # Premium plan for NEET UG — lifetime access, higher question count.
        # Trial: same as GOLD (4 days, 30 questions, 4 tests)
        # Paid:  lifetime, 75 questions/test, 6 tests/day
        "title": "NEET UG PLATINUM",
        "description": (
            "The NEET UG Platinum plan is the most comprehensive preparation package for NEET UG — "
            "with lifetime access so you can keep practising until you crack it. Get 75 questions per "
            "test session, covering the full NMC syllabus across Physics, Chemistry, Botany, and Zoology. "
            "Questions are regularly updated to reflect the latest exam trends, new NCERT additions, and "
            "high-frequency topics from recent NEET UG papers. Deep subject-wise and chapter-wise analytics "
            "help you build a data-driven revision strategy. Rank tracking puts you on a live leaderboard "
            "among Platinum students nationwide. The AI mentor provides topic-level guidance, flags your "
            "recurring mistakes, and suggests targeted revision plans. Best suited for students who want "
            "the highest level of preparation with no time pressure on their access."
        ),
        "exam": "NEET UG",
        "price": 3499,
        "is_free": False,
        "is_flagship": True,
        "free_questions_per_test": 30,
        "free_daily_test_limit": 4,
        "free_trial_days": 4,
        "questions_per_test": 75,        # more questions than GOLD
        "daily_test_limit": 6,
        "validity_days": None,           # None = lifetime, plan_expires_at never set
        "keypoints": [
            "Lifetime access",
            "75 questions per test",
            "6 tests per day",
            "Subject-wise analytics",
            "Rank & percentile tracking",
            "AI mentor feedback",
        ],
    },
    {
        # ── NEET PG GOLD ─────────────────────────────────────────────────────
        # Entry-level paid plan for NEET PG aspirants.
        # Same structure as NEET UG GOLD but PG-level content and higher price.
        "title": "NEET PG GOLD",
        "description": (
            "The NEET PG Gold plan is built for MBBS graduates preparing for the National Exit Test (NExT) "
            "and NEET PG entrance. Get 6 months of focused practice with 45 clinical and theory-based MCQs "
            "per test, covering all 19 subjects of the NEET PG syllabus — from Medicine and Surgery to "
            "Pathology, Pharmacology, and PSM. Questions are framed in the clinical vignette style used in "
            "the actual exam, helping you develop the reasoning skills needed to tackle case-based scenarios. "
            "Subject-wise performance analytics highlight which specialties need more attention. Rank and "
            "percentile tracking lets you compare your standing with other PG aspirants. AI mentor feedback "
            "identifies pattern-based errors and recommends high-yield revision topics. A solid choice for "
            "interns and fresh MBBS graduates starting their PG prep journey."
        ),
        "exam": "NEET PG",
        "price": 2499,
        "is_free": False,
        "is_flagship": True,
        "free_questions_per_test": 30,
        "free_daily_test_limit": 4,
        "free_trial_days": 4,
        "questions_per_test": 45,
        "daily_test_limit": 6,
        "validity_days": 180,
        "keypoints": [
            "6 months access",
            "45 questions per test",
            "6 tests per day",
            "Clinical case-based questions",
            "Rank & percentile among PG aspirants",
            "AI mentor feedback",
        ],
    },
    {
        # ── NEET PG PLATINUM ─────────────────────────────────────────────────
        # Premium plan for NEET PG — 1 year access (not lifetime like UG Platinum).
        "title": "NEET PG PLATINUM",
        "description": (
            "The NEET PG Platinum plan offers the most intensive preparation experience for NEET PG and NExT, "
            "with 1 full year of unlimited access. Practice with 75 questions per test across all major "
            "clinical and pre-clinical subjects, including high-difficulty case-based questions that mirror "
            "the evolving NEET PG exam pattern. The question bank is continuously updated with recent exam "
            "recalls, new clinical guidelines, and high-yield topics flagged by toppers. Advanced analytics "
            "break down your performance by subject, chapter, and difficulty level — giving you a precise "
            "picture of where you stand. Live rank tracking among Platinum PG students keeps you motivated "
            "and competitive. The AI mentor goes deeper here — analysing your test history over time, "
            "spotting knowledge gaps, and building a personalised study plan around your weak subjects. "
            "Recommended for serious PG aspirants who want a full-year, data-driven preparation strategy."
        ),
        "exam": "NEET PG",
        "price": 4499,
        "is_free": False,
        "is_flagship": True,
        "free_questions_per_test": 30,
        "free_daily_test_limit": 4,
        "free_trial_days": 4,
        "questions_per_test": 75,
        "daily_test_limit": 6,
        "validity_days": 365,            # 1 year
        "keypoints": [
            "1 year access",
            "75 questions per test",
            "6 tests per day",
            "Clinical case-based questions",
            "Rank & percentile among PG aspirants",
            "AI mentor feedback",
        ],
    },
    {
        # ── CRASH COURSE ─────────────────────────────────────────────────────
        # Free course — no payment, no upgrade path.
        # Student gets 30-day access on enrollment (status = "free").
        # free_* limits are permanent (not just trial limits).
        # After 30 days → locked permanently.
        "title": "Crash Course",
        "description": (
            "The Crash Course is a free, high-intensity revision programme designed for NEET aspirants "
            "in the final stretch before the exam. Over 30 days, practise with 75 high-yield questions "
            "per session — carefully selected from the most frequently tested topics across Physics, "
            "Chemistry, and Biology. Every question comes with a detailed explanation so you can quickly "
            "understand concepts without going back to textbooks. The format is built for speed: short, "
            "focused tests that fit into a busy last-minute revision schedule. No payment required — "
            "just enrol and start practising immediately. Best used alongside your existing study material "
            "as a final confidence booster before exam day."
        ),
        "exam": "CRASH COURSE",
        "price": 0,
        "is_free": True,             # enrollment status = "free", no payment needed
        "is_flagship": False,
        "free_questions_per_test": 75,   # generous for revision
        "free_daily_test_limit": 3,
        "free_trial_days": 30,           # 30-day access window
        "questions_per_test": None,      # not used (no paid state)
        "daily_test_limit": None,        # not used
        "validity_days": None,           # not used
        "keypoints": [
            "30-day access",
            "75 questions per test",
            "3 tests per day",
            "High-yield questions",
            "Quick revision format",
            "No payment required",
        ],
    },
]

# ── Upsert ────────────────────────────────────────────────────────────────────
for data in courses_data:
    course = db.query(Course).filter(Course.title == data["title"]).first()

    if not course:
        course = Course(created_by=admin.id)
        db.add(course)
        action = "CREATED"
    else:
        action = "UPDATED"

    # Apply all fields (works for both insert and update)
    course.title = data["title"]
    course.description = data["description"]
    course.exam = data["exam"]
    course.price = data["price"]
    course.is_free = data["is_free"]
    course.is_flagship = data["is_flagship"]
    course.is_active = True
    course.keypoints = data["keypoints"]
    course.free_questions_per_test = data["free_questions_per_test"]
    course.free_daily_test_limit = data["free_daily_test_limit"]
    course.free_trial_days = data["free_trial_days"]
    course.questions_per_test = data["questions_per_test"]
    course.daily_test_limit = data["daily_test_limit"]
    course.validity_days = data["validity_days"]

    db.flush()
    print(f"{action}: '{data['title']}' | exam={data['exam']} | price=₹{data['price']}")

db.commit()
db.close()
print("\nSeeding complete.")
