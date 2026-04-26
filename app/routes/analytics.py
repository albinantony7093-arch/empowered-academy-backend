import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_token
from app.models.analytics import TestResult
from app.models.response import Response
from app.models.test_attempt import TestAttempt

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard")
def get_dashboard(
    exam: str = "UG",
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Returns dashboard data for a specific exam type.
    Includes recent scores, topic-level accuracy, and weak areas.
    """
    exam = exam.upper()
    if exam not in ("UG", "PG"):
        raise HTTPException(status_code=400, detail="Invalid exam type. Choose UG or PG.")

    try:
        results = (
            db.query(TestResult)
            .join(TestAttempt, TestResult.attempt_id == TestAttempt.id)
            .filter(TestResult.user_id == user_id, TestAttempt.exam == exam)
            .order_by(TestResult.created_at.desc())
            .limit(20)
            .all()
        )

        recent_scores = [r.score for r in results if r.score is not None]

        responses = (
            db.query(Response)
            .join(TestAttempt, Response.attempt_id == TestAttempt.id)
            .filter(TestAttempt.user_id == user_id, Response.exam == exam)
            .all()
        )
    except Exception as e:
        logger.error(f"Dashboard DB query failed for user {user_id}: {e}")
        raise HTTPException(status_code=503, detail="Could not fetch dashboard data")

    topic_stats: dict[str, dict] = {}
    for r in responses:
        if not r.topic:
            continue
        if r.topic not in topic_stats:
            topic_stats[r.topic] = {"correct": 0, "total": 0, "subject": r.subject}
        topic_stats[r.topic]["total"]   += 1
        topic_stats[r.topic]["correct"] += int(r.is_correct)

    topic_details = []
    weak_areas    = []
    for topic, s in topic_stats.items():
        acc = round((s["correct"] / s["total"]) * 100, 1) if s["total"] else 0.0
        topic_details.append({
            "topic":    topic,
            "subject":  s["subject"],
            "accuracy": acc,
            "answered": s["total"],
        })
        if acc < 60:
            weak_areas.append(topic)

    # Sort topic details by accuracy ascending (weakest first)
    topic_details.sort(key=lambda x: x["accuracy"])

    return {
        "user_id":       user_id,
        "exam":          exam,
        "recent_scores": recent_scores,
        "weak_areas":    weak_areas,
        "topic_details": topic_details,
    }
