from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import uuid
import logging
import json

from app.core.database import get_db
from app.core.security import get_current_user, require_page_admin, get_current_user_optional
from app.models.course import Course, Enrollment
from app.utils.mail import send_trial_enrollment_email, send_crash_course_enrollment_email
from app.models.test_attempt import TestAttempt, AttemptStatus
from app.models.analytics import TestResult
from app.models.response import Response
from app.schemas.course import CourseCreate, CourseOut, EnrollmentOut, MyCourseOut
from app.utils.question_engine import generate_questions, evaluate_answers
from app.utils.rank_service import calculate_rank_and_percentile
from app.utils.mentor_engine import generate_mentor_advice
from app.schemas.test import SubmitAnswersRequest
import random

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sync_expiry(enrollment: Enrollment, db: Session) -> None:
    """Flip expired enrollments to locked in-place (does not commit)."""
    now = datetime.now(timezone.utc)
    if enrollment.payment_status == "trial" and enrollment.trial_ends_at:
        if now > enrollment.trial_ends_at:
            enrollment.payment_status = "locked"
    elif enrollment.payment_status == "free" and enrollment.trial_ends_at:
        if now > enrollment.trial_ends_at:
            enrollment.payment_status = "locked"
    elif enrollment.payment_status == "paid" and enrollment.plan_expires_at:
        if now > enrollment.plan_expires_at:
            enrollment.payment_status = "locked"


def _get_active_enrollment(course_id: str, user_id: str, db: Session) -> Enrollment:
    """
    Three-step access check:
      1. payment_status — locked/cancelled → blocked immediately
      2. expiry         — trial/free/paid expiry check
      3. returns enrollment so caller can read limits
    """
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == str(user_id), Enrollment.course_id == str(course_id))
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    # Step 2 — sync expiry, then commit if status changed
    old_status = enrollment.payment_status
    _sync_expiry(enrollment, db)
    if enrollment.payment_status != old_status:
        db.commit()

    # Step 1 — check final status
    if enrollment.payment_status == "locked":
        raise HTTPException(status_code=403, detail="Access locked. Please purchase a plan to continue.")
    if enrollment.payment_status == "cancelled":
        raise HTTPException(status_code=403, detail="Enrollment cancelled.")
    if enrollment.payment_status == "pending_payment":
        raise HTTPException(status_code=403, detail="Payment pending. Please complete your purchase.")

    return enrollment


def _get_limits(enrollment: Enrollment, db: Session) -> dict:
    """
    Return the applicable limits for this enrollment:
      - trial / free → course free limits
      - paid         → course paid limits (questions_per_test, daily_test_limit)
    """
    course = db.query(Course).filter(Course.id == enrollment.course_id).first()
    if not course:
        return {"questions_per_test": None, "daily_test_limit": None}

    if enrollment.payment_status == "paid":
        return {
            "questions_per_test": course.questions_per_test,
            "daily_test_limit": course.daily_test_limit,
        }

    # trial or free
    return {
        "questions_per_test": course.free_questions_per_test,
        "daily_test_limit": course.free_daily_test_limit,
    }


# ── Course CRUD ───────────────────────────────────────────────────────────────

@router.get("/", response_model=List[CourseOut])
def list_courses(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    """Public — list all active courses with enrollment status."""
    courses = db.query(Course).filter(Course.is_active == True).all()

    enrollment_map = {}
    if current_user:
        enrollments = db.query(Enrollment).filter(
            Enrollment.user_id == current_user.id,
            Enrollment.payment_status != "pending_payment",
        ).all()
        for e in enrollments:
            enrollment_map[e.course_id] = e

    result = []
    for course in courses:
        e = enrollment_map.get(course.id)
        result.append({
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "detailed_description": course.detailed_description,
            "exam": course.exam,
            "price": float(course.price),
            "is_free": course.is_free,
            "is_active": course.is_active,
            "is_flagship": course.is_flagship,
            "keypoints": course.keypoints,
            "free_questions_per_test": course.free_questions_per_test,
            "free_daily_test_limit": course.free_daily_test_limit,
            "free_trial_days": course.free_trial_days,
            "questions_per_test": course.questions_per_test,
            "daily_test_limit": course.daily_test_limit,
            "validity_days": course.validity_days,
            "created_by": course.created_by,
            "is_enrolled": bool(e) if current_user else None,
            "payment_status": e.payment_status if e else None,
            "trial_ends_at": e.trial_ends_at.isoformat() if e and e.trial_ends_at else None,
            "plan_expires_at": e.plan_expires_at.isoformat() if e and e.plan_expires_at else None,
        })
    return result


@router.post("/", response_model=CourseOut, status_code=201)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_page_admin),
):
    """
    Admin only — create a course and its plans atomically.
    Crash Course: is_free=True, no plans needed.
    NEET UG/PG:   is_free=False, plans required.
    """
    exam = payload.exam.upper()

    try:
        course = Course(
            title=payload.title,
            description=payload.description,
            detailed_description=payload.detailed_description,
            exam=exam,
            price=payload.price,
            is_free=payload.is_free,
            is_flagship=payload.is_flagship,
            keypoints=payload.keypoints,
            free_questions_per_test=payload.free_questions_per_test,
            free_daily_test_limit=payload.free_daily_test_limit,
            free_trial_days=payload.free_trial_days,
            questions_per_test=payload.questions_per_test,
            daily_test_limit=payload.daily_test_limit,
            validity_days=payload.validity_days,
            created_by=admin.id,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        return {**course.__dict__, "is_enrolled": None, "payment_status": None, "trial_ends_at": None, "plan_expires_at": None}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create course: {e}")
        raise HTTPException(status_code=500, detail="Failed to create course.")


# ── Enrollment ────────────────────────────────────────────────────────────────

@router.post("/{course_id}/enroll", response_model=EnrollmentOut, status_code=201)
def enroll_in_course(
    course_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Enroll in a course.
    - Crash Course (is_free=True)  → status = "free",  expires after free_trial_days
    - NEET UG/PG  (is_free=False) → status = "trial", expires after free_trial_days
    """
    course = db.query(Course).filter(Course.id == course_id, Course.is_active == True).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found or no longer available.")

    existing = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id)
        .first()
    )
    if existing:
        # Allow pending_payment → trial if trial hasn't started yet
        if existing.payment_status == "pending_payment" and existing.trial_ends_at is None:
            _set_initial_enrollment(existing, course)
            db.commit()
            db.refresh(existing)
            _send_enrollment_email(current_user, course, existing.trial_ends_at)
            return existing
        raise HTTPException(status_code=409, detail="Already enrolled in this course.")

    enrollment = Enrollment(
        user_id=current_user.id,
        course_id=course_id,
    )
    _set_initial_enrollment(enrollment, course)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    _send_enrollment_email(current_user, course, enrollment.trial_ends_at)
    return enrollment


def _set_initial_enrollment(enrollment: Enrollment, course: Course) -> None:
    """Set payment_status and expiry based on course type."""
    now = datetime.now(timezone.utc)

    if course.is_free and course.title == "Crash Course":
        # Crash Course: fixed expiry on June 20 2026 10:00 PM IST (UTC+5:30 = 16:30 UTC)
        expiry = datetime(2026, 6, 20, 16, 30, 0, tzinfo=timezone.utc)
        enrollment.payment_status = "free"
    else:
        days = course.free_trial_days or 4
        expiry = (now + timedelta(days=days)).replace(hour=23, minute=59, second=59, microsecond=0)
        enrollment.payment_status = "free" if course.is_free else "trial"

    enrollment.trial_ends_at = expiry


def _send_enrollment_email(user, course: Course, trial_ends_at) -> None:
    import threading
    import asyncio

    email = user.email
    full_name = user.full_name or ""
    end_str = trial_ends_at.strftime("%B %d, %Y") if trial_ends_at else ""
    is_crash = course.is_free and course.title == "Crash Course"
    course_title = course.title

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if is_crash:
                coro = send_crash_course_enrollment_email(email, full_name, end_str)
            else:
                coro = send_trial_enrollment_email(email, full_name, course_title, end_str)
            loop.run_until_complete(coro)
        except Exception as e:
            logger.warning(f"Failed to send enrollment email: {e}")
        finally:
            loop.close()

    threading.Thread(target=_run, daemon=True).start()


# ── My Courses ────────────────────────────────────────────────────────────────

@router.get("/my", response_model=List[MyCourseOut])
def my_enrollments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List current user's enrollments. Syncs expiry on the fly."""
    enrollments = (
        db.query(Enrollment)
        .filter(
            Enrollment.user_id == current_user.id,
            Enrollment.payment_status != "pending_payment",
        )
        .all()
    )

    changed = False
    for e in enrollments:
        old = e.payment_status
        _sync_expiry(e, db)
        if e.payment_status != old:
            changed = True
    if changed:
        db.commit()

    course_ids = [e.course_id for e in enrollments]
    courses = {c.id: c for c in db.query(Course).filter(Course.id.in_(course_ids)).all()}

    return [
        MyCourseOut(
            enrollment_id=e.id,
            payment_status=e.payment_status,
            trial_ends_at=e.trial_ends_at,
            plan_expires_at=e.plan_expires_at,
            course_id=e.course_id,
            title=courses[e.course_id].title,
            description=courses[e.course_id].description,
            exam=courses[e.course_id].exam,
            price=float(courses[e.course_id].price),
            is_free=courses[e.course_id].is_free,
            is_active=courses[e.course_id].is_active,
            is_flagship=courses[e.course_id].is_flagship,
            keypoints=courses[e.course_id].keypoints,
            free_questions_per_test=courses[e.course_id].free_questions_per_test,
            free_daily_test_limit=courses[e.course_id].free_daily_test_limit,
            free_trial_days=courses[e.course_id].free_trial_days,
            questions_per_test=courses[e.course_id].questions_per_test,
            daily_test_limit=courses[e.course_id].daily_test_limit,
            validity_days=courses[e.course_id].validity_days,
        )
        for e in enrollments
        if e.course_id in courses
    ]


# ── Test Start / Submit ───────────────────────────────────────────────────────

@router.get("/{course_id}/test/start")
def start_course_test(
    course_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Start a test. Enforces per-enrollment limits:
    - daily_test_limit  (NULL = unlimited)
    - questions_per_test (NULL = unlimited, default 30)
    """
    enrollment = _get_active_enrollment(course_id, user_id=current_user.id, db=db)
    limits = _get_limits(enrollment, db)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    raw_exam = course.exam.upper()
    exam = "PG" if "PG" in raw_exam else ("UG" if "UG" in raw_exam else raw_exam)

    # Enforce daily test limit
    daily_limit = limits["daily_test_limit"]
    if daily_limit is not None:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        tests_today = (
            db.query(TestAttempt)
            .filter(
                TestAttempt.user_id == str(current_user.id),
                TestAttempt.course_id == str(course_id),
                TestAttempt.created_at >= today_start,
            )
            .count()
        )
        if tests_today >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit reached. You can take up to {daily_limit} tests per day.",
            )
    else:
        tests_today = 0

    q_limit = limits["questions_per_test"] or 30
    questions = generate_questions(exam, limit=q_limit)
    test_id = str(uuid.uuid4())

    attempt = TestAttempt(
        user_id=current_user.id,
        test_id=test_id,
        exam=exam,
        course_id=course_id,
        status=AttemptStatus.generated,
        questions=json.dumps([
            {"question_id": q["question_id"], "difficulty": q["difficulty"]}
            for q in questions
        ]),
    )
    db.add(attempt)
    db.commit()

    return {
        "test_id": test_id,
        "exam": exam,
        "course_id": course_id,
        "total_questions": len(questions),
        "tests_taken_today": tests_today + 1,
        "tests_remaining_today": (daily_limit - tests_today - 1) if daily_limit is not None else None,
        "questions": [
            {
                "id": q["question_id"],
                "text": q["question"],
                "options": q["options"],
                "subject": q["subject"],
                "topic": q["topic"],
            }
            for q in questions
        ],
    }


@router.post("/test/submit")
def submit_course_test(
    payload: SubmitAnswersRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit answers for a course test and get results."""
    attempt = db.query(TestAttempt).filter(
        TestAttempt.test_id == payload.test_id,
        TestAttempt.user_id == current_user.id,
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test session not found")
    if attempt.status == AttemptStatus.submitted:
        raise HTTPException(status_code=409, detail="Test already submitted")
    if not attempt.course_id:
        raise HTTPException(status_code=400, detail="Invalid test attempt")

    _get_active_enrollment(attempt.course_id, user_id=current_user.id, db=db)

    raw_exam = attempt.exam.upper() if attempt.exam else ""
    normalized_exam = "PG" if "PG" in raw_exam else ("UG" if "UG" in raw_exam else raw_exam)

    result = evaluate_answers(
        normalized_exam, payload.answers,
        all_questions=json.loads(attempt.questions) if attempt.questions else None,
    )

    attempt.status = AttemptStatus.submitted
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.score = float(result["total_correct"])
    attempt.marks = float(result["marks"])
    attempt.max_marks = float(result["max_marks"])
    attempt.accuracy = result["accuracy"]

    for ans in result["per_answer"]:
        db.add(Response(
            attempt_id=attempt.id,
            question_id=ans["question_id"],
            exam=attempt.exam,
            subject=ans["subject"],
            topic=ans["topic"],
            selected_answer=ans["selected"],
            correct_answer=ans["correct"],
            is_correct=ans["is_correct"],
        ))

    db.add(TestResult(
        user_id=current_user.id,
        attempt_id=attempt.id,
        subject=attempt.exam,
        score=float(result["total_correct"]),
        weak_areas=result["weak_areas"],
    ))

    db.commit()

    rank_data = calculate_rank_and_percentile(result["total_correct"], attempt.exam, db)

    try:
        mentor_advice = generate_mentor_advice(result["total_correct"], result["accuracy"], result["weak_areas"])
        general_advice = [
            "Practice regularly to maintain consistency in your performance.",
            "Focus on understanding concepts rather than memorizing answers.",
            "Take breaks between study sessions to improve retention.",
            "Review your mistakes to avoid repeating them in future tests.",
            "Time management is crucial - practice solving questions within time limits.",
            "Create a study schedule and stick to it for better preparation.",
            "Use active recall techniques while studying for better memory retention.",
            "Solve previous year papers to understand exam patterns.",
        ]
        combined = list(mentor_advice) + general_advice
        random.shuffle(combined)
        seen, random_advice = set(), []
        for advice in combined:
            if advice not in seen:
                random_advice.append(advice)
                seen.add(advice)
            if len(random_advice) == 3:
                break
        while len(random_advice) < 3:
            random_advice.append("Keep practicing and stay motivated!")
    except Exception as e:
        logger.warning(f"Failed to generate mentor advice: {e}")
        random_advice = [
            "Great job completing the test! Keep practicing.",
            "Review your incorrect answers to understand the concepts better.",
            "Stay consistent with your study schedule.",
        ]

    return {
        "test_id": payload.test_id,
        "total_questions": result["total_questions"],
        "total_correct": result["total_correct"],
        "total_attempted": result["total_attempted"],
        "marks": result["marks"],
        "max_marks": result["max_marks"],
        "accuracy": result["accuracy"],
        "weak_areas": result["weak_areas"],
        "rank": rank_data["rank"],
        "percentile": rank_data["percentile"],
        "mentor_advice": random_advice,
        "per_answer": result["per_answer"],
    }
