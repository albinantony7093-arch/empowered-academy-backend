"""
question_engine.py — Unified question loader and evaluator for all 5 courses.

Current JSON format (shared across all courses — neet 1.json):
    [{"id": "BIO-001", "subject": "Biology", "topic": "...",
      "difficulty": "easy"|"moderate"|"hard",
      "question": "...",
      "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
      "answer": "B", "explanation": "..."}]

All normalised to internal shape:
    {
        "question_id":    str,
        "question":       str,
        "options":        {"A": str, "B": str, "C": str, "D": str},
        "correct_answer": str,   # "A" | "B" | "C" | "D"
        "subject":        str,
        "topic":          str,
        "difficulty":     str,   # "easy" | "moderate" | "hard"
        "explanation":    str,
    }

Scoring: easy=1, moderate/medium=2, hard=3

NOTE: All 5 courses share one dataset for now.
      To use separate datasets per exam, update paths.py and restore
      individual loaders (_load_ug, _load_pg) with their original formats.
"""
import json
import random
import logging
import threading
from app.utils.paths import NEET_UG_DATA_PATH, NEET_PG_DATA_PATH, NEET_CRASH_DATA_PATH

logger = logging.getLogger(__name__)

# Each exam type gets its own pool/map so swapping datasets later is isolated.
# For now all three paths point to the same file (see paths.py).
_POOLS: dict[str, list[dict]] = {"UG": [], "PG": [], "CRASH COURSE": []}
_MAPS:  dict[str, dict[str, dict]] = {"UG": {}, "PG": {}, "CRASH COURSE": {}}
_loaded: set[str] = set()
_lock = threading.Lock()

_EXAM_PATHS = {
    "UG":           NEET_UG_DATA_PATH,
    "PG":           NEET_PG_DATA_PATH,
    "CRASH COURSE": NEET_CRASH_DATA_PATH,
}


def _parse_flat_list(raw: list) -> tuple[list[dict], int]:
    """
    Parse the shared flat-list JSON format:
        id / question_id  → question_id
        answer / correct_answer → correct_answer (must be A/B/C/D)
        option_a/b/c/d    → options dict
        difficulty        → easy | moderate | medium | hard
    """
    items: list[dict] = []
    skipped = 0
    for q in raw:
        # Support both field name variants
        answer = (q.get("answer") or q.get("correct_answer") or "").strip().upper()
        if answer not in ("A", "B", "C", "D"):
            skipped += 1
            continue
        items.append({
            "question_id":    str(q.get("id") or q.get("question_id") or ""),
            "question":       q.get("question", ""),
            "options":        {
                "A": q.get("option_a", ""),
                "B": q.get("option_b", ""),
                "C": q.get("option_c", ""),
                "D": q.get("option_d", ""),
            },
            "correct_answer": answer,
            "subject":        q.get("subject", ""),
            "topic":          q.get("topic") or q.get("module", ""),
            "difficulty":     (q.get("difficulty") or "easy").lower(),
            "explanation":    q.get("explanation", ""),
        })
    return items, skipped


def load_exam(exam: str) -> None:
    """Pre-load dataset for the given exam type. Idempotent."""
    if exam not in _EXAM_PATHS:
        raise ValueError(f"Unknown exam type: {exam!r}")
    if exam in _loaded:
        return
    with _lock:
        if exam in _loaded:
            return
        path = _EXAM_PATHS[exam]
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # raw is always a flat list in the current shared format
        items, skipped = _parse_flat_list(raw)
        _POOLS[exam] = items
        _MAPS[exam]  = {item["question_id"]: item for item in items}
        _loaded.add(exam)
        logger.info(f"{exam} dataset loaded: {len(items)} questions "
                    f"({skipped} skipped) from {path}")


def generate_questions(exam: str, limit: int = 50) -> list[dict]:
    """Return a random sample of questions for the given exam."""
    load_exam(exam)
    pool = _POOLS[exam]
    if not pool:
        raise FileNotFoundError(f"No questions loaded for exam={exam!r}")
    sample = random.sample(pool, min(limit, len(pool)))
    # Strip correct_answer before sending to client
    return [
        {
            "question_id": q["question_id"],
            "question":    q["question"],
            "options":     q["options"],
            "subject":     q["subject"],
            "topic":       q["topic"],
            "difficulty":  q["difficulty"],
        }
        for q in sample
    ]


def get_question(exam: str, question_id: str) -> dict | None:
    """Return full question dict (including answer) by ID."""
    load_exam(exam)
    return _MAPS[exam].get(question_id)


_DIFFICULTY_MARKS = {
    "easy":     1,
    "medium":   2,
    "moderate": 2,
    "hard":     3,
    # PG single-letter codes (kept for future PG dataset)
    "l": 1,
    "m": 2,
    "h": 3,
}


def _marks_for_difficulty(difficulty: str) -> int:
    """easy=1, moderate/medium=2, hard=3. Defaults to 1 if unknown."""
    return _DIFFICULTY_MARKS.get(difficulty.strip().lower(), 1)


def evaluate_answers(
    exam: str,
    answers: dict[str, str],
    all_questions: list[dict] | None = None,
) -> dict:
    """
    Score answers dict {question_id: selected_letter}.
    Marks weighted by difficulty: easy=1, medium/moderate=2, hard=3.

    all_questions: full list of {question_id, difficulty} for the test.
    If provided, max_marks covers all questions regardless of how many were answered.
    """
    load_exam(exam)
    correct   = 0
    marks     = 0
    max_marks = 0
    total     = 0
    topic_stats: dict[str, dict] = {}
    per_answer: list[dict] = []

    if all_questions:
        for q_meta in all_questions:
            q = get_question(exam, q_meta["question_id"])
            if q:
                max_marks += _marks_for_difficulty(q_meta.get("difficulty") or q.get("difficulty", ""))

    for q_id, selected in answers.items():
        q = get_question(exam, q_id)
        if not q:
            logger.warning(f"Q {q_id!r} not found in {exam} — skipped")
            continue
        total  += 1
        q_marks = _marks_for_difficulty(q.get("difficulty", ""))
        if not all_questions:
            max_marks += q_marks
        is_correct = selected.strip().upper() == q["correct_answer"]
        if is_correct:
            correct += 1
            marks   += q_marks

        topic = q["topic"]
        if topic not in topic_stats:
            topic_stats[topic] = {"correct": 0, "total": 0, "subject": q["subject"]}
        topic_stats[topic]["total"]   += 1
        topic_stats[topic]["correct"] += int(is_correct)

        per_answer.append({
            "question_id":  q_id,
            "subject":      q["subject"],
            "topic":        topic,
            "difficulty":   q.get("difficulty", ""),
            "marks":        q_marks,
            "selected":     selected,
            "correct":      q["correct_answer"],
            "is_correct":   is_correct,
            "marks_earned": q_marks if is_correct else 0,
            "explanation":  q.get("explanation", ""),
        })

    accuracy   = round((correct / total) * 100, 1) if total > 0 else 0.0
    weak_areas = [
        topic for topic, s in topic_stats.items()
        if s["total"] > 0 and (s["correct"] / s["total"]) * 100 < 60
    ]

    return {
        "total_correct":   correct,
        "total_attempted": total,
        "total_questions": len(all_questions) if all_questions else total,
        "marks":           marks,
        "max_marks":       max_marks,
        "accuracy":        accuracy,
        "weak_areas":      weak_areas,
        "per_answer":      per_answer,
    }
