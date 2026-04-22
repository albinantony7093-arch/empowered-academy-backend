"""
Rank Service — calculates rank and percentile using SQL aggregates.
Never loads all scores into Python memory.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.analytics import TestResult

NEET_UG_MAX_SCORE = 720
NEET_PG_MAX_SCORE = 800


def _max_score(exam: str) -> int:
    return NEET_PG_MAX_SCORE if exam == "PG" else NEET_UG_MAX_SCORE


def calculate_rank_and_percentile(user_score: float, exam: str, db: Session) -> dict:
    max_score = _max_score(exam)

    total: int = db.query(func.count(TestResult.id))\
                   .filter(TestResult.subject == exam)\
                   .scalar() or 0

    # Low user base fallback
    if total < 50:
        ratio      = min(user_score / max_score, 1.0) if max_score > 0 else 0.0
        percentile = round(ratio * 100, 1)
        rank       = max(1, int((1 - ratio) * 5000))
        return {"rank": rank, "percentile": percentile}

    # Count users strictly above (rank) and strictly below (percentile) via SQL
    above: int = db.query(func.count(TestResult.id))\
                   .filter(TestResult.subject == exam, TestResult.score > user_score)\
                   .scalar() or 0

    below: int = db.query(func.count(TestResult.id))\
                   .filter(TestResult.subject == exam, TestResult.score < user_score)\
                   .scalar() or 0

    rank       = above + 1
    percentile = round((below / total) * 100, 1)

    return {"rank": rank, "percentile": percentile}
