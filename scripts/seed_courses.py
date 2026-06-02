"""
Seed Script — Empowered Academy Course Data
============================================

PURPOSE:
    Creates or updates the 5 course cards in the database.
    Each plan (GOLD, PLATINUM) is its own Course row — the frontend
    groups them by the 'exam' field to show category headers.

    Resulting course cards:
        NEET UG category:
            - NEET UG GOLD     (paid, 1-year validity)
            - NEET UG PLATINUM (paid, lifetime)

        NEET PG category:
            - NEET PG GOLD     (paid, 1-year validity)
            - NEET PG PLATINUM (paid, 1-year validity)

        CRASH COURSE category:
            - Crash Course     (free, 15-day access)

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
        # Smart Recovery Engine Gold — 1 year access.
        # Trial: 4 days, 30 questions/test, 4 tests/day
        # Paid:  1 year, 45 questions/test, 6 tests/day
        "title": "NEET UG GOLD",
        "description": (
            "AI-powered NEET UG preparation ecosystem with 10,000+ MCQs, adaptive mock tests, "
            "concept clarity videos, and smart revision tools — 1 year access."
        ),
        "detailed_description": (
            "Smart Recovery Engine Gold is built for serious NEET UG aspirants who need structured, "
            "AI-powered preparation over one full year. This is not a passive lecture platform — it is "
            "an intelligent preparation ecosystem that continuously analyses your mock test performance, "
            "MCQ mistakes, weak concepts, and revision patterns to guide you toward the areas that need "
            "immediate improvement. Get access to 10,000+ high-quality NEET MCQs covering Physics, "
            "Chemistry, and Biology, curated by NEET weightage, PYQ trends, and AIR discriminator concepts. "
            "Practice with chapter-wise, subject-wise, and full-length mock tests with adaptive analytics "
            "that identify weak chapters, repeated mistakes, and low-confidence zones. "
            "High-quality animated concept clarity videos are recommended intelligently based on your "
            "test weaknesses and MCQ error patterns. Chapter-wise and subject-wise flashcards help with "
            "rapid revision, formula retention, and active recall. The AIR-Oriented Intelligence Engine "
            "prioritises high-scoring topics and rank discriminator concepts to maximise your marks "
            "efficiently. Adaptive spaced repeat revision automatically resurfaces forgotten concepts "
            "and unstable memory areas. The Calm Corner — a dedicated mental wellness space — helps you "
            "reduce stress, recover confidence, and avoid burnout during long-term preparation. "
            "Ideal for Class 12 students and repeaters targeting the upcoming NEET UG cycle."
        ),
        "exam": "NEET UG",
        "price": 9999,
        "is_free": False,
        "is_flagship": True,
        "free_questions_per_test": 30,
        "free_daily_test_limit": 4,
        "free_trial_days": 4,
        "questions_per_test": 45,
        "daily_test_limit": 6,
        "validity_days": 365,            # 1 year
        "keypoints": [
            "1 year access",
            "10,000+ high-quality NEET MCQs",
            "Adaptive mock tests & weak area analytics",
            "Animated concept clarity videos",
            "Flashcards & spaced repeat revision",
            "AIR-oriented intelligence engine",
            "Calm Corner — mental wellness support",
            "AI-powered performance analytics",
        ],
    },
    {
        # ── NEET UG PLATINUM ─────────────────────────────────────────────────
        # Smart Recovery Engine Platinum — lifetime access, deeper AI features.
        # Trial: 4 days, 30 questions/test, 4 tests/day
        # Paid:  lifetime, 75 questions/test, 6 tests/day
        "title": "NEET UG PLATINUM",
        "description": (
            "The most advanced NEET UG AI preparation ecosystem — lifetime access with elite AIR analytics, "
            "adaptive intelligence, and everything in Gold, enhanced."
        ),
        "detailed_description": (
            "Smart Recovery Engine Platinum is the most advanced NEET UG preparation ecosystem — "
            "with lifetime access and elite adaptive intelligence features designed for AIR-oriented "
            "rank optimisation. Everything in the Gold plan is included, plus deeper tools for serious "
            "rank improvement: extended test coverage, advanced AIR analytics, premium revision workflows, "
            "enhanced concept tracking, and deeper adaptive recommendations. "
            "The platform continuously analyses your performance, weak concepts, retention gaps, "
            "mock test behaviour, revision consistency, and scoring patterns to create a personalised "
            "recovery and improvement pathway that adapts throughout your entire preparation journey. "
            "Practice with 75 questions per test session from a 10,000+ question bank covering the "
            "full NEET syllabus across Physics, Chemistry, Botany, and Zoology, curated for NEET "
            "weightage, PYQ trends, and high-discriminator concepts. Intelligent video recommendations, "
            "flashcard engine, adaptive spaced repeat revision, and the Calm Corner wellness space are "
            "all included. With lifetime access, there is no time pressure — keep practising and "
            "improving until you reach your target rank. Best suited for students who want the highest "
            "level of AI-powered NEET preparation with no access deadline."
        ),
        "exam": "NEET UG",
        "price": 14999,
        "is_free": False,
        "is_flagship": True,
        "free_questions_per_test": 30,
        "free_daily_test_limit": 4,
        "free_trial_days": 4,
        "questions_per_test": 75,
        "daily_test_limit": 6,
        "validity_days": None,           # None = lifetime
        "keypoints": [
            "Lifetime access",
            "10,000+ high-quality NEET MCQs",
            "Advanced AIR analytics & rank prediction",
            "Adaptive difficulty testing",
            "Premium revision workflows",
            "Deeper adaptive AI recommendations",
            "Calm Corner — mental wellness support",
            "Everything in Gold, enhanced",
        ],
    },
    {
        # ── NEET PG GOLD ─────────────────────────────────────────────────────
        # Smart Recovery Engine Gold for NEET PG — 1 year, ₹14,999.
        # Trial: 7 days, 30 questions/test, 4 tests/day
        # Paid:  1 year, 45 questions/test, 6 tests/day
        "title": "NEET PG GOLD",
        "description": (
            "AI-powered NEET PG preparation with 12,000+ clinical MCQs, smart recovery engine, "
            "and adaptive analytics — 1 year access with a 7-day free trial."
        ),
        "detailed_description": (
            "Smart Recovery Engine Gold for NEET PG is an AI-powered preparation ecosystem built for "
            "MBBS graduates targeting NEET PG and NExT. This is not a traditional lecture-heavy LMS — "
            "it is an intelligent system focused on active learning, adaptive testing, weakness correction, "
            "clinical reasoning, and rank optimisation. "
            "Get access to 12,000+ high-yield MCQs across all 19 NEET PG subjects, framed in the "
            "clinical vignette style of the actual exam — including Medicine, Surgery, Pathology, "
            "Pharmacology, PSM, and more. Subject-wise tests, full-length mock tests, and clinical "
            "case simulations are all included. The Smart Recovery Engine detects your weak areas and "
            "guides systematic recovery with AI-powered analytics, flashcards, spaced repetition, "
            "and PYQ mapping. Performance analytics highlight which specialties need more attention, "
            "and rank tracking lets you compare your standing with other NEET PG aspirants. "
            "Includes a 7-day free trial to explore all AI features before subscribing. "
            "A solid choice for interns and fresh MBBS graduates beginning their PG prep journey."
        ),
        "exam": "NEET PG",
        "price": 14999,
        "is_free": False,
        "is_flagship": True,
        "free_questions_per_test": 30,
        "free_daily_test_limit": 4,
        "free_trial_days": 7,            # 7-day free trial per PG doc
        "questions_per_test": 45,
        "daily_test_limit": 6,
        "validity_days": 365,            # 1 year
        "keypoints": [
            "1 year access",
            "12,000+ high-yield NEET PG MCQs",
            "Clinical case simulations",
            "Smart Recovery Engine — AI weak area detection",
            "Subject-wise tests & full mock tests",
            "Flashcards, spaced repetition & PYQ mapping",
            "Performance analytics & rank tracking",
            "4-day free trial",
        ],
    },
    {
        # ── NEET PG PLATINUM ─────────────────────────────────────────────────
        # Smart Recovery Engine Platinum for NEET PG — 1 year, ₹24,999.
        # Everything in Gold plus advanced AI analytics, rank prediction, adaptive difficulty.
        "title": "NEET PG PLATINUM",
        "description": (
            "The most intensive NEET PG AI preparation — 12,000+ MCQs, dynamic AIR rank prediction, "
            "personalised recovery plans, and adaptive difficulty testing. 1 year access."
        ),
        "detailed_description": (
            "Smart Recovery Engine Platinum for NEET PG is the most intensive AI-powered preparation "
            "experience for NEET PG and NExT — designed for aspirants who want dynamic rank prediction, "
            "personalised recovery plans, and elite adaptive intelligence. "
            "Everything in the Gold plan is included, plus: Advanced AI Analytics that go beyond "
            "subject-level tracking to provide deep topic-wise insights; Dynamic Rank Prediction that "
            "models your AIR trajectory based on real performance data; Personalised Recovery Plans "
            "built around your specific weak subjects and error patterns; Adaptive Difficulty Testing "
            "that calibrates question complexity to your current preparation level; an AI Revision "
            "Scheduler that builds a structured revision timeline around your exam date; an Advanced "
            "Mock Ecosystem with clinical decision simulations; Premium Recovery Sessions for targeted "
            "concept strengthening; and Priority Support. "
            "Practice with 75 questions per test across all 19 NEET PG subjects from a 12,000+ MCQ "
            "bank that is continuously updated with exam recalls, new clinical guidelines, and "
            "high-yield flagged topics. Includes a 7-day free trial. "
            "Recommended for serious PG aspirants who want a full-year, data-driven preparation "
            "strategy aimed at AIR optimisation."
        ),
        "exam": "NEET PG",
        "price": 24999,
        "is_free": False,
        "is_flagship": True,
        "free_questions_per_test": 30,
        "free_daily_test_limit": 4,
        "free_trial_days": 7,            # 7-day free trial per PG doc
        "questions_per_test": 75,
        "daily_test_limit": 6,
        "validity_days": 365,            # 1 year
        "keypoints": [
            "1 year access",
            "12,000+ high-yield NEET PG MCQs",
            "Advanced AI analytics & AIR rank prediction",
            "Personalised recovery plans",
            "Adaptive difficulty testing",
            "AI revision scheduler",
            "Clinical decision simulations",
            "Priority support",
            "4-day free trial",
        ],
    },
    {
        # ── CRASH COURSE (15 Days) ────────────────────────────────────────────
        # Free course — Smart Recovery Engine 15-day programme.
        # No payment, no upgrade path. Access expires after 15 days.
        # free_* limits are permanent (not just trial limits).
        "title": "Crash Course",
        "description": (
            "Free 15-day AI-powered NEET revision sprint — 5,200+ high-yield MCQs, adaptive recovery "
            "engine, and weak area analytics. No payment required."
        ),
        "detailed_description": (
            "Smart Recovery Engine 15-Day Crash Course is a free, high-intensity NEET revision "
            "programme by Empowered Academy — designed for students in the final stretch before "
            "the exam. This is more than a test series: it is an intelligent NEET rank recovery "
            "ecosystem. The platform continuously analyses your mock test performance, MCQ mistakes, "
            "weak concepts, retention gaps, and revision patterns, then guides you toward the areas "
            "that need immediate improvement. "
            "Get access to 5,200+ carefully curated Physics, Chemistry, and Biology MCQs focused on "
            "NEET weightage, PYQ patterns, and AIR-level concepts. Adaptive mock tests and weak area "
            "analytics identify weak chapters, recurring mistakes, conceptual gaps, and "
            "low-confidence zones — helping you revise smarter instead of studying blindly. "
            "No payment required. Just enrol and start your 15-day recovery sprint immediately. "
            "Best used alongside your existing study material as a focused final revision booster "
            "before exam day."
        ),
        "exam": "CRASH COURSE",
        "price": 0,
        "is_free": True,
        "is_flagship": False,
        "free_questions_per_test": 75,
        "free_daily_test_limit": 3,
        "free_trial_days": 15,           # 15-day access window (changed from 30)
        "questions_per_test": None,
        "daily_test_limit": None,
        "validity_days": None,
        "keypoints": [
            "15-day access",
            "5,200+ high-quality NEET MCQs",
            "Adaptive mock tests & weak area analytics",
            "AI-powered recovery engine",
            "PYQ patterns & AIR-level concepts",
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
    course.detailed_description=data["detailed_description"]
    course.exam = data["exam"]
    course.price = data["price"]
    course.is_free = data["is_free"]
    course.is_flagship = data["is_flagship"]
    # Crash Course starts inactive; scheduler will activate it during its window
    course.is_active = False if data["title"] == "Crash Course" else True
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