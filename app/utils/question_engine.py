"""
question_engine.py — Unified NEET UG + PG question loader and evaluator.

Real UG JSON format:
    {"question_bank": [{"subject": "BIOLOGY", "module": "CELL_BIOLOGY", "mcqs": [
        {"id": "CELL_BIOLOGY_Q1", "question": "...", "options": ["A","B","C","D"],
         "answer": "D", "explanation": "...", "difficulty": "easy", "time_sec": 60}
    ]}]}

Real PG JSON format (flat list):
    [{"question_id": "M12_001", "question": "...",
      "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
      "correct_answer": "A", "subject": "Medicine", "module": "DEC",
      "system": "...", "difficulty": "H", "explanation": "..."}]

Both normalised to internal shape:
    {
        "question_id":    str,
        "question":       str,
        "options":        {"A": str, "B": str, "C": str, "D": str},
        "correct_answer": str,   # "A" | "B" | "C" | "D"
        "subject":        str,
        "topic":          str,
        "difficulty":     str,
        "explanation":    str,
    }
"""
import json
import random
import logging
import threading
from app.utils.paths import NEET_UG_DATA_PATH, NEET_PG_DATA_PATH

logger = logging.getLogger(__name__)

_UG_LIST: list[dict] = []
_PG_LIST: list[dict] = []
_UG_MAP:  dict[str, dict] = {}
_PG_MAP:  dict[str, dict] = {}
_lock = threading.Lock()


def _load_ug() -> None:
    """Load and normalise UG dataset — thread-safe."""
    global _UG_LIST, _UG_MAP
    if _UG_LIST:
        return
    with _lock:
        if _UG_LIST:  # double-checked locking
            return
        with open(NEET_UG_DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)

    items: list[dict] = []
    for module in raw.get("question_bank", []):
        subj  = module.get("subject", "").title()   # normalise BIOLOGY -> Biology
        topic = module.get("module", "")
        for q in module.get("mcqs", []):
            # UG options are a list ["A","B","C","D"] — actual option text IS the letter
            # The option labels are the answer choices; answer is "A"/"B"/"C"/"D"
            opts = q.get("options", ["A", "B", "C", "D"])
            answer = q.get("answer", "")
            if answer not in ("A", "B", "C", "D"):
                continue  # skip malformed
            items.append({
                "question_id":    str(q["id"]),
                "question":       q.get("question", ""),
                "options":        {
                    "A": opts[0] if len(opts) > 0 else "A",
                    "B": opts[1] if len(opts) > 1 else "B",
                    "C": opts[2] if len(opts) > 2 else "C",
                    "D": opts[3] if len(opts) > 3 else "D",
                },
                "correct_answer": answer,
                "subject":        subj,
                "topic":          topic,
                "difficulty":     q.get("difficulty", ""),
                "explanation":    q.get("explanation", ""),
            })

    _UG_LIST = items
    _UG_MAP  = {item["question_id"]: item for item in items}
    logger.info(f"UG dataset loaded: {len(_UG_LIST)} questions across "
                f"{len(set(i['subject'] for i in items))} subjects")


def _load_pg() -> None:
    """Load and normalise PG dataset — thread-safe."""
    global _PG_LIST, _PG_MAP
    if _PG_LIST:
        return
    with _lock:
        if _PG_LIST:  # double-checked locking
            return
        with open(NEET_PG_DATA_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)

    items: list[dict] = []
    skipped = 0
    for q in raw:
        answer = q.get("correct_answer", "").strip()
        if answer not in ("A", "B", "C", "D"):
            skipped += 1
            continue  # skip 3384 empty + 670 free-text answers
        items.append({
            "question_id":    str(q.get("question_id", "")),
            "question":       q.get("question", ""),
            "options":        {
                "A": q.get("option_a", ""),
                "B": q.get("option_b", ""),
                "C": q.get("option_c", ""),
                "D": q.get("option_d", ""),
            },
            "correct_answer": answer,
            "subject":        q.get("subject", ""),
            "topic":          q.get("module", ""),
            "difficulty":     q.get("difficulty", ""),
            "explanation":    q.get("explanation", ""),
        })

    _PG_LIST = items
    _PG_MAP  = {item["question_id"]: item for item in items}
    logger.info(f"PG dataset loaded: {len(_PG_LIST)} usable questions "
                f"({skipped} skipped — missing/non-ABCD answers)")


def load_exam(exam: str) -> None:
    """Pre-load dataset. Idempotent."""
    if exam == "UG":
        _load_ug()
    elif exam == "PG":
        _load_pg()
    else:
        raise ValueError(f"Unknown exam type: {exam!r}")


def generate_questions(exam: str, limit: int = 50) -> list[dict]:
    """Return a random sample of questions for the given exam."""
    load_exam(exam)
    pool = _UG_LIST if exam == "UG" else _PG_LIST
    if not pool:
        raise FileNotFoundError(f"No questions loaded for exam={exam!r}")
    sample = random.sample(pool, min(limit, len(pool)))
    # Return safe copy — strip correct_answer for client
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
    mapping = _UG_MAP if exam == "UG" else _PG_MAP
    return mapping.get(question_id)


def evaluate_answers(exam: str, answers: dict[str, str]) -> dict:
    """
    Score answers dict {question_id: selected_letter}.
    Returns score, total, accuracy, weak_areas, per_answer.
    """
    load_exam(exam)
    correct = 0
    total   = 0
    topic_stats: dict[str, dict] = {}
    per_answer: list[dict] = []

    for q_id, selected in answers.items():
        q = get_question(exam, q_id)
        if not q:
            logger.warning(f"Q {q_id!r} not found in {exam} — skipped")
            continue
        total     += 1
        is_correct = selected.strip().upper() == q["correct_answer"]
        if is_correct:
            correct += 1

        topic = q["topic"]
        if topic not in topic_stats:
            topic_stats[topic] = {"correct": 0, "total": 0, "subject": q["subject"]}
        topic_stats[topic]["total"]   += 1
        topic_stats[topic]["correct"] += int(is_correct)

        per_answer.append({
            "question_id": q_id,
            "subject":     q["subject"],
            "topic":       topic,
            "selected":    selected,
            "correct":     q["correct_answer"],
            "is_correct":  is_correct,
            "explanation": q.get("explanation", ""),
        })

    accuracy   = round((correct / total) * 100, 1) if total > 0 else 0.0
    weak_areas = [
        topic for topic, s in topic_stats.items()
        if s["total"] > 0 and (s["correct"] / s["total"]) * 100 < 60
    ]

    return {
        "score":      correct,
        "total":      total,
        "accuracy":   accuracy,
        "weak_areas": weak_areas,
        "per_answer": per_answer,
    }
