import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_token
from app.models.test_attempt import TestAttempt, AttemptStatus
from app.models.analytics import TestResult
from app.models.response import Response
from app.utils.question_engine import generate_questions, evaluate_answers
from app.utils.mentor_engine import generate_mentor_advice, determine_stress_level
from app.utils.rank_service import calculate_rank_and_percentile
from app.schemas.test import SubmitAnswersRequest
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_EXAMS = {"UG", "PG"}


@router.get("/questions")
def get_questions(
    exam: str = "UG",
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    exam = exam.upper()
    if exam not in VALID_EXAMS:
        raise HTTPException(status_code=400, detail="Invalid exam type. Choose UG or PG.")

    try:
        questions = generate_questions(exam, limit=50)
    except FileNotFoundError as e:
        logger.error(f"Dataset missing for exam={exam}: {e}")
        raise HTTPException(status_code=503, detail=f"Question dataset unavailable for {exam}")

    test_id = str(uuid.uuid4())

    attempt = TestAttempt(
        user_id=user_id,
        test_id=test_id,
        exam=exam,
        status=AttemptStatus.generated,
    )
    db.add(attempt)
    db.commit()

    # Strip correct_answer before sending to client
    safe_questions = [
        {
            "id":      q["question_id"],
            "text":    q["question"],
            "options": q["options"],
            "subject": q["subject"],
            "topic":   q["topic"],
        }
        for q in questions
    ]


    return {"test_id": test_id, "exam": exam, "questions": safe_questions}


@router.post("/submit")
def submit_test(
    payload: SubmitAnswersRequest,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    # Validate test session belongs to this user
    attempt = db.query(TestAttempt).filter(
        TestAttempt.test_id == payload.test_id,
        TestAttempt.user_id == user_id,
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test session not found")
    if attempt.status == AttemptStatus.submitted:
        raise HTTPException(status_code=409, detail="Test already submitted")

    exam = attempt.exam  # Use the exam type stored when test was created

    # Evaluate answers against dataset
    try:
        result = evaluate_answers(exam, payload.answers)
    except FileNotFoundError as e:
        logger.error(f"Dataset missing during submit for exam={exam}: {e}")
        raise HTTPException(status_code=503, detail="Question dataset unavailable")

    score      = result["score"]
    total      = result["total"]
    accuracy   = result["accuracy"]
    weak_areas = result["weak_areas"]

    # Mark attempt as submitted
    attempt.status       = AttemptStatus.submitted
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.score        = float(score)
    attempt.accuracy     = accuracy
    db.flush()

    # Save per-answer Response rows
    for ans in result["per_answer"]:
        db.add(Response(
            attempt_id=attempt.id,
            question_id=ans["question_id"],
            exam=exam,
            subject=ans["subject"],
            topic=ans["topic"],
            selected_answer=ans["selected"],
            correct_answer=ans["correct"],
            is_correct=ans["is_correct"],
        ))

    # Save aggregate TestResult row for dashboard/rank queries
    db.add(TestResult(
        user_id=user_id,
        attempt_id=attempt.id,
        subject=exam,
        score=float(score),
        weak_areas=weak_areas,
    ))

    db.commit()

    # Rank & percentile
    rank_data = calculate_rank_and_percentile(score, exam, db)

    # Stress level + mentor advice
    stress_level  = determine_stress_level(score, accuracy)
    mentor_advice = generate_mentor_advice(score, accuracy, weak_areas)

    return {
        "test_id":       payload.test_id,
        "exam":          exam,
        "score":         score,
        "total":         total,
        "accuracy":      accuracy,
        "weak_areas":    weak_areas,
        "rank":          rank_data["rank"],
        "percentile":    rank_data["percentile"],
        "stress_level":  stress_level,
        "mentor_advice": mentor_advice,
    }
