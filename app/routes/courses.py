from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta, timezone
import uuid
import logging

from app.core.database import get_db
from app.core.security import get_current_user, require_admin, require_page_admin
from app.models.course import Course, Enrollment
from app.models.test_attempt import TestAttempt, AttemptStatus
from app.models.analytics import TestResult
from app.models.response import Response
from app.schemas.course import CourseCreate, CourseOut, EnrollmentOut, MyCourseOut
from app.utils.question_engine import generate_questions, evaluate_answers
from app.utils.rank_service import calculate_rank_and_percentile
from app.schemas.test import SubmitAnswersRequest

logger = logging.getLogger(__name__)
router = APIRouter()

TRIAL_DAYS = 4
DAILY_TEST_LIMIT = 4
QUESTIONS_PER_TEST = 30


def _get_active_enrollment(course_id: str, user_id: str, db: Session) -> Enrollment:
    """Return enrollment if student has active access, else raise 403."""
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == str(user_id), Enrollment.course_id == str(course_id))
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in this course")

    # Sync trial → locked if expired
    if enrollment.payment_status == "trial" and enrollment.trial_ends_at:
        if datetime.now(timezone.utc) > enrollment.trial_ends_at:
            enrollment.payment_status = "locked"
            db.commit()

    if enrollment.payment_status == "locked":
        raise HTTPException(status_code=403, detail="Trial expired. Please pay to continue.")
    if enrollment.payment_status == "cancelled":
        raise HTTPException(status_code=403, detail="Enrollment cancelled.")

    return enrollment


@router.get("/", response_model=List[CourseOut])
def list_courses(db: Session = Depends(get_db)):
    """Public — list all active courses."""
    try:
        courses = db.query(Course).filter(Course.is_active == True).all()
        return courses
    except Exception as e:
        logger.error(f"Failed to list courses: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "COURSES_FETCH_FAILED",
                "message": "Unable to fetch courses. Please try again later.",
                "user_friendly": True
            }
        )


@router.post("/", response_model=CourseOut, status_code=201)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_page_admin),
):
    """Admin only — add a new course."""
    course = Course(
        title=payload.title,
        description=payload.description,
        exam=payload.exam.upper(),
        price=payload.price,
        created_by=admin.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.post("/{course_id}/enroll", response_model=EnrollmentOut, status_code=201)
def enroll_in_course(
    course_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Enroll in a course. Student gets a 4-day free trial.
    After trial expires the enrollment is locked until payment.
    """
    try:
        course = db.query(Course).filter(Course.id == course_id, Course.is_active == True).first()
        if not course:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": "COURSE_NOT_FOUND",
                    "message": "Course not found or is no longer available.",
                    "user_friendly": True
                }
            )

        existing = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409, 
                detail={
                    "error": "ALREADY_ENROLLED",
                    "message": "You are already enrolled in this course.",
                    "user_friendly": True
                }
            )

        now = datetime.now(timezone.utc)
        # Trial ends at end of day (23:59:59) on the 4th day from enrollment date.
        # e.g. enroll May 4 → access through May 8 23:59:59 UTC
        trial_end_date = (now + timedelta(days=TRIAL_DAYS)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        enrollment = Enrollment(
            user_id=current_user.id,
            course_id=course_id,
            payment_status="trial",
            trial_ends_at=trial_end_date,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        logger.error(f"Failed to enroll user {current_user.id} in course {course_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ENROLLMENT_FAILED",
                "message": "Unable to enroll in course. Please try again later.",
                "user_friendly": True
            }
        )


@router.get("/my", response_model=List[MyCourseOut])
def my_enrollments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List current user's enrollments with course details. Syncs expired trials to 'locked' on the fly."""
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == current_user.id)
        .all()
    )
    now = datetime.now(timezone.utc)
    locked_ids = [
        e.id for e in enrollments
        if e.payment_status == "trial" and e.trial_ends_at and now > e.trial_ends_at
    ]
    if locked_ids:
        db.query(Enrollment).filter(Enrollment.id.in_(locked_ids)).update(
            {"payment_status": "locked"}, synchronize_session="fetch"
        )
        db.commit()
        for e in enrollments:
            if e.id in locked_ids:
                e.payment_status = "locked"

    course_ids = [e.course_id for e in enrollments]
    courses = {c.id: c for c in db.query(Course).filter(Course.id.in_(course_ids)).all()}

    return [
        MyCourseOut(
            enrollment_id=e.id,
            payment_status=e.payment_status,
            course_id=e.course_id,
            title=courses[e.course_id].title,
            description=courses[e.course_id].description,
            exam=courses[e.course_id].exam,
            price=float(courses[e.course_id].price),
            keypoints=courses[e.course_id].keypoints,
            is_active=courses[e.course_id].is_active,
        )
        for e in enrollments
        if e.course_id in courses
    ]


@router.get("/{course_id}/test/start")
def start_course_test(
    course_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Start a test for a course. Enforces:
    - Student must be enrolled with active access (trial or paid)
    - Max 4 tests per calendar day per course
    - 30 random questions per test
    """
    _get_active_enrollment(course_id, user_id=current_user.id, db=db)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    exam = course.exam.upper()

    # Count tests started today for this course
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
    if tests_today >= DAILY_TEST_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached. You can take up to {DAILY_TEST_LIMIT} tests per day.",
        )

    questions = generate_questions(exam, limit=QUESTIONS_PER_TEST)
    test_id = str(uuid.uuid4())

    attempt = TestAttempt(
        user_id=current_user.id,
        test_id=test_id,
        exam=exam,
        course_id=course_id,
        status=AttemptStatus.generated,
    )
    db.add(attempt)
    db.commit()

    return {
        "test_id": test_id,
        "exam": exam,
        "course_id": course_id,
        "total_questions": len(questions),
        "tests_taken_today": tests_today + 1,
        "tests_remaining_today": DAILY_TEST_LIMIT - tests_today - 1,
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

    # Validate enrollment using course_id from the attempt
    if attempt.course_id:
        _get_active_enrollment(attempt.course_id, user_id=current_user.id, db=db)

    result = evaluate_answers(attempt.exam, payload.answers)

    attempt.status = AttemptStatus.submitted
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.score = float(result["score"])
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
        score=float(result["score"]),
        weak_areas=result["weak_areas"],
    ))

    db.commit()

    rank_data = calculate_rank_and_percentile(result["score"], attempt.exam, db)

    return {
        "test_id": payload.test_id,
        "score": result["score"],
        "total": result["total"],
        "accuracy": result["accuracy"],
        "weak_areas": result["weak_areas"],
        "rank": rank_data["rank"],
        "percentile": rank_data["percentile"],
        "per_answer": result["per_answer"],
    }