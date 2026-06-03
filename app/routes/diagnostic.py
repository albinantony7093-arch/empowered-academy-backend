import json
import uuid
import random
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.diagnostic import DiagnosticAttempt, DiagnosticStatus
from app.schemas.test import SubmitAnswersRequest
from app.utils.question_engine import (
    generate_diagnostic_questions,
    evaluate_diagnostic_answers,
    load_diagnostic,
)
from app.utils.mentor_engine import generate_mentor_advice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostic", tags=["Diagnostic"])

QUESTIONS_PER_TEST = 30


@router.get("/test/start")
def start_diagnostic_test(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Start a new 30-question diagnostic test.
    Students can take unlimited tests.
    """
    questions = generate_diagnostic_questions(limit=QUESTIONS_PER_TEST)
    test_id   = str(uuid.uuid4())

    attempt = DiagnosticAttempt(
        user_id   = str(current_user.id),
        test_id   = test_id,
        status    = DiagnosticStatus.generated,
        questions = json.dumps([
            {"question_id": q["question_id"], "difficulty": q["difficulty"]}
            for q in questions
        ]),
    )
    db.add(attempt)
    db.commit()

    return {
        "test_id":         test_id,
        "exam":            "DIAGNOSTIC",
        "course_id":       None,
        "total_questions": len(questions),
        "tests_taken_today":      None,
        "tests_remaining_today":  None,
        "questions": [
            {
                "id":      q["question_id"],
                "text":    q["question"],
                "options": q["options"],
                "subject": q["subject"],
                "topic":   q["topic"],
            }
            for q in questions
        ],
    }


@router.post("/test/submit")
def submit_diagnostic_test(
    payload: SubmitAnswersRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit answers for a diagnostic test and get results."""
    attempt = db.query(DiagnosticAttempt).filter(
        DiagnosticAttempt.test_id == payload.test_id,
        DiagnosticAttempt.user_id == str(current_user.id),
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test session not found")
    if attempt.status == DiagnosticStatus.submitted:
        raise HTTPException(status_code=409, detail="Test already submitted")

    all_questions = json.loads(attempt.questions) if attempt.questions else []

    result = evaluate_diagnostic_answers(payload.answers, all_questions)

    attempt.status       = DiagnosticStatus.submitted
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.score        = float(result["total_correct"])
    attempt.marks        = float(result["marks"])
    attempt.max_marks    = float(result["max_marks"])
    attempt.accuracy     = result["accuracy"]
    attempt.responses    = result["per_answer"]   # stored inline, no FK dependency

    db.commit()

    try:
        mentor_advice = generate_mentor_advice(
            result["total_correct"], result["accuracy"], result["weak_areas"]
        )
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
        "test_id":          payload.test_id,
        "total_questions":  result["total_questions"],
        "total_correct":    result["total_correct"],
        "total_attempted":  result["total_attempted"],
        "marks":            result["marks"],
        "max_marks":        result["max_marks"],
        "accuracy":         result["accuracy"],
        "weak_areas":       result["weak_areas"],
        "rank":             None,
        "percentile":       None,
        "mentor_advice":    random_advice,
        "per_answer":       result["per_answer"],
    }


@router.get("/history")
def get_diagnostic_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return all diagnostic tests taken by the current student,
    most recent first.
    """
    attempts = (
        db.query(DiagnosticAttempt)
        .filter(DiagnosticAttempt.user_id == str(current_user.id))
        .order_by(DiagnosticAttempt.created_at.desc())
        .all()
    )

    return {
        "total_tests": len(attempts),
        "history": [
            {
                "test_id":      a.test_id,
                "status":       a.status,
                "score":        a.score,
                "marks":        a.marks,
                "max_marks":    a.max_marks,
                "accuracy":     a.accuracy,
                "started_at":   a.created_at.isoformat() if a.created_at else None,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            }
            for a in attempts
        ],
    }
