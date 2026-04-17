"""
Rank Service — calculates rank and percentile from historical scores.
Supports filtering by exam type (UG / PG) so UG and PG leaderboards are separate.
Falls back to a simulated pool of 5000 when real data is sparse (< 50 entries).
"""
from sqlalchemy.orm import Session
from app.models.analytics import TestResult

NEET_UG_MAX_SCORE = 720   # 180 questions × 4 marks
NEET_PG_MAX_SCORE = 800   # 200 questions × 4 marks (adjust if your exam differs)


def _max_score(exam: str) -> int:
    return NEET_PG_MAX_SCORE if exam == "PG" else NEET_UG_MAX_SCORE


def calculate_rank_and_percentile(
    user_score: float,
    exam: str,
    db: Session,
) -> dict:
    """
    Compare user_score against all stored scores for the same exam.
    Returns {"rank": int, "percentile": float}.
    """
    max_score = _max_score(exam)

    all_scores = [
        r.score
        for r in db.query(TestResult.score)
                   .filter(TestResult.subject == exam)
                   .all()
        if r.score is not None
    ]
    total = len(all_scores)

    # Low user base fallback — use a simulated pool so rank is meaningful from day 1
    if total < 50:
        simulated_total = 5000
        ratio      = min(user_score / max_score, 1.0) if max_score > 0 else 0.0
        percentile = round(ratio * 100, 1)
        rank       = max(1, int((1 - ratio) * simulated_total))
        return {"rank": rank, "percentile": percentile}

    # Correct rank for duplicate scores — count users strictly above
    rank      = sum(1 for s in all_scores if s > user_score) + 1
    beaten    = sum(1 for s in all_scores if s < user_score)
    percentile = round((beaten / total) * 100, 1)

    return {"rank": rank, "percentile": percentile}
