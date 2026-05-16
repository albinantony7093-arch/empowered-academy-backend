from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta, timezone
import uuid
import logging

from app.core.database import get_db
from app.core.security import get_current_user, require_admin, require_page_admin, get_current_user_optional
from app.models.course import Course, Enrollment
from app.utils.mail import send_trial_enrollment_email
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
        raise HTTPException(status_code=500, detail="Not enrolled in this course")

    # Sync trial → locked if expired
    if enrollment.payment_status == "trial" and enrollment.trial_ends_at:
        if datetime.now(timezone.utc) > enrollment.trial_ends_at:
            enrollment.payment_status = "locked"
            db.commit()

    if enrollment.payment_status == "locked":
        raise HTTPException(status_code=500, detail="Trial expired. Please pay to continue.")
    if enrollment.payment_status == "pending_payment":
        raise HTTPException(status_code=500, detail="Payment pending. Please complete your purchase to access this course.")
    if enrollment.payment_status == "cancelled":
        raise HTTPException(status_code=500, detail="Enrollment cancelled.")

    return enrollment


@router.get("/", response_model=List[CourseOut])
def list_courses(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    """Public — list all active courses with enrollment status."""
    try:
        logger.info(f"list_courses called - current_user: {current_user.id if current_user else 'None'}")
        courses = db.query(Course).filter(Course.is_active == True).all()
        
        # Get user's enrollments with payment status if authenticated
        enrollment_map = {}
        if current_user:
            enrollments = db.query(Enrollment).filter(
                Enrollment.user_id == current_user.id
            ).all()
            
            # Create map of course_id -> enrollment info (exclude pending_payment)
            for e in enrollments:
                if e.payment_status == "pending_payment":
                    continue
                enrollment_map[e.course_id] = {
                    "is_enrolled": True,
                    "payment_status": e.payment_status,
                    "trial_ends_at": e.trial_ends_at.isoformat() if e.trial_ends_at else None
                }
            
            logger.info(f"User enrolled in {len(enrollment_map)} courses")
        
        # Add enrollment and payment status to each course
        result = []
        for course in courses:
            enrollment_info = enrollment_map.get(course.id, {
                "is_enrolled": False,
                "payment_status": None,
                "trial_ends_at": None
            })
            
            course_dict = {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "detailed_description": course.detailed_description,
                "exam": course.exam,
                "price": float(course.price),
                "keypoints": course.keypoints,
                "is_active": course.is_active,
                "is_flagship": course.is_flagship,
                "created_by": course.created_by,
                "is_enrolled": enrollment_info["is_enrolled"] if current_user else None,
                "payment_status": enrollment_info["payment_status"] if current_user else None,
                "trial_ends_at": enrollment_info["trial_ends_at"] if current_user else None
            }
            result.append(course_dict)
        
        return result
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
                detail="Course not found or is no longer available."
            )

        existing = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id)
            .first()
        )
        if existing:
            # Allow switching from pending_payment to trial ONLY if they never had a trial
            if existing.payment_status == "pending_payment" and existing.trial_ends_at is None:
                now = datetime.now(timezone.utc)
                trial_end_date = (now + timedelta(days=TRIAL_DAYS)).replace(
                    hour=23, minute=59, second=59, microsecond=0
                )
                existing.payment_status = "trial"
                existing.trial_ends_at = trial_end_date
                db.commit()
                db.refresh(existing)
                try:
                    import asyncio
                    trial_end_str = trial_end_date.strftime("%B %d, %Y")
                    asyncio.run(
                        send_trial_enrollment_email(current_user.email, current_user.full_name or "", course.title, trial_end_str)
                    )
                except Exception as e:
                    logger.warning(f"Failed to send trial enrollment email: {e}")
                return existing
            raise HTTPException(
                status_code=409,
                detail="You are already enrolled in this course."
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
        try:
            import asyncio
            trial_end_str = trial_end_date.strftime("%B %d, %Y")
            asyncio.run(
                send_trial_enrollment_email(current_user.email, current_user.full_name or "", course.title, trial_end_str)
            )
        except Exception as e:
            logger.warning(f"Failed to send trial enrollment email: {e}")
        return enrollment
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        logger.error(f"Failed to enroll user {current_user.id} in course {course_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to enroll in course. Please try again later."
        )


@router.get("/my", response_model=List[MyCourseOut])
def my_enrollments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List current user's enrollments with course details. Syncs expired trials to 'locked' on the fly."""
    enrollments = (
        db.query(Enrollment)
        .filter(
            Enrollment.user_id == current_user.id,
            Enrollment.payment_status != "pending_payment"
        )
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

    raw_exam = course.exam.upper()
    if "PG" in raw_exam:
        exam = "PG"
    elif "UG" in raw_exam:
        exam = "UG"
    else:
        exam = raw_exam

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
    if not attempt.course_id:
        raise HTTPException(status_code=400, detail="Invalid test attempt")
    _get_active_enrollment(attempt.course_id, user_id=current_user.id, db=db)

    raw_exam = attempt.exam.upper() if attempt.exam else ""
    if "PG" in raw_exam:
        normalized_exam = "PG"
    elif "UG" in raw_exam:
        normalized_exam = "UG"
    else:
        normalized_exam = raw_exam

    result = evaluate_answers(normalized_exam, payload.answers)

    attempt.status = AttemptStatus.submitted
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.score     = float(result["total_correct"])
    attempt.marks     = float(result["marks"])
    attempt.max_marks = float(result["max_marks"])
    attempt.accuracy  = result["accuracy"]

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

    # Generate 3 random mentor advices based on test performance
    try:
        mentor_advice = generate_mentor_advice(result["total_correct"], result["accuracy"], result["weak_areas"])
        
        # Extended pool of general advice for better variety
        general_advice = [
            "Practice regularly to maintain consistency in your performance.",
            "Focus on understanding concepts rather than memorizing answers.",
            "Take breaks between study sessions to improve retention.",
            "Review your mistakes to avoid repeating them in future tests.",
            "Time management is crucial - practice solving questions within time limits.",
            "Create a study schedule and stick to it for better preparation.",
            "Use active recall techniques while studying for better memory retention.",
            "Solve previous year papers to understand exam patterns.",
            "Join study groups to discuss difficult concepts with peers.",
            "Take mock tests regularly to assess your preparation level.",
            "Focus on your weak subjects but don't neglect your strong ones.",
            "Maintain a healthy lifestyle with proper sleep and nutrition.",
            "Use mnemonics and visual aids to remember complex information.",
            "Practice meditation or relaxation techniques to manage exam stress.",
            "Set realistic daily and weekly study goals.",
            "Reward yourself after completing study milestones.",
            "Keep revision notes handy for quick last-minute reviews.",
            "Stay updated with current affairs if relevant to your exam.",
            "Don't compare your progress with others, focus on your own journey.",
            "Seek help from teachers or mentors when you're stuck on topics."
        ]
        
        # Combine personalized and general advice for larger pool
        combined_advice = list(mentor_advice) + general_advice
        
        # Shuffle the combined list and pick 3 random unique advices
        random.shuffle(combined_advice)
        random_advice = []
        seen_advice = set()
        
        for advice in combined_advice:
            if advice not in seen_advice and len(random_advice) < 3:
                random_advice.append(advice)
                seen_advice.add(advice)
            if len(random_advice) == 3:
                break
        
        # Fallback if somehow we don't have 3 advices (very unlikely)
        while len(random_advice) < 3:
            fallback_advice = f"Keep practicing and stay motivated! Attempt #{len(random_advice) + 1}"
            random_advice.append(fallback_advice)
            
    except Exception as e:
        logger.warning(f"Failed to generate mentor advice for test {payload.test_id}: {e}")
        random_advice = [
            "Great job completing the test! Keep practicing to improve your performance.",
            "Review your incorrect answers to understand the concepts better.",
            "Stay consistent with your study schedule and practice regularly."
        ]

    return {
        "test_id":          payload.test_id,
        "total_correct":    result["total_correct"],
        "total_attempted":  result["total_attempted"],
        "marks":            result["marks"],
        "max_marks":        result["max_marks"],
        "accuracy":         result["accuracy"],
        "weak_areas":       result["weak_areas"],
        "rank":             rank_data["rank"],
        "percentile":       rank_data["percentile"],
        "mentor_advice":    random_advice,
        "per_answer":       result["per_answer"],
    }