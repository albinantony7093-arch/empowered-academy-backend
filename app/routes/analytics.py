import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_token
from app.models.analytics import TestResult
from app.models.response import Response
from app.models.test_attempt import TestAttempt
from app.models.course import Course
from app.utils.rank_service import calculate_rank_and_percentile

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard")
def get_dashboard(
    course_id: str,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """
    Returns dashboard data filtered by course_id.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    exam = course.exam.upper()

    try:
        attempt_ids = [
            a.id for a in db.query(TestAttempt).filter(
                TestAttempt.user_id == user_id,
                TestAttempt.course_id == course_id,
            ).all()
        ]

        results = (
            db.query(TestResult)
            .filter(TestResult.user_id == user_id, TestResult.attempt_id.in_(attempt_ids))
            .order_by(TestResult.created_at.desc())
            .limit(20)
            .all()
        )

        recent_scores = [r.score for r in results if r.score is not None]

        responses = (
            db.query(Response)
            .filter(Response.attempt_id.in_(attempt_ids))
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

    topic_details.sort(key=lambda x: x["accuracy"])

    latest_score = recent_scores[0] if recent_scores else None
    rank_data = calculate_rank_and_percentile(latest_score, exam, db) if latest_score is not None else {"rank": None, "percentile": None}

    return {
        "user_id":       user_id,
        "exam":          exam,
        "course_id":     course_id,
        "recent_scores": recent_scores,
        "rank":          rank_data["rank"],
        "percentile":    rank_data["percentile"],
        "weak_areas":    weak_areas,
        "topic_details": topic_details,
    }
