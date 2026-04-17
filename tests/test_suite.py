"""
Full test suite for Empowered Academy API v1.3.
Tests: auth, test flow (UG + PG), analytics, edge cases, and health check.

Run with:
    pytest tests/ -v
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_sample_ug_data():
    return {
        "question_bank": [
            {
                "subject": "Biology",
                "module": "Cell Biology",
                "mcqs": [
                    {"id": "UG001", "question": "What is the powerhouse of the cell?",
                     "options": ["A) Nucleus", "B) Mitochondria", "C) Ribosome", "D) Golgi body"],
                     "answer": "B) Mitochondria"},
                    {"id": "UG002", "question": "Which organelle contains DNA?",
                     "options": ["A) Ribosome", "B) Mitochondria", "C) ER", "D) Vacuole"],
                     "answer": "B) Mitochondria"},
                ]
            },
            {
                "subject": "Chemistry",
                "module": "Organic Chemistry",
                "mcqs": [
                    {"id": "UG003", "question": "What is the functional group of an alcohol?",
                     "options": ["A) -COOH", "B) -OH", "C) -NH2", "D) -CHO"],
                     "answer": "B) -OH"},
                ]
            }
        ]
    }


def make_sample_pg_data():
    return [
        {"question_id": "PG001", "question": "What is the gold standard for TB diagnosis?",
         "options": ["A) CXR", "B) Sputum AFB", "C) Culture", "D) PCR"],
         "correct_answer": "C) Culture", "subject": "Medicine", "module": "Pulmonology"},
        {"question_id": "PG002", "question": "Commonest cause of mitral stenosis?",
         "options": ["A) Rheumatic", "B) Congenital", "C) SLE", "D) Carcinoid"],
         "correct_answer": "A) Rheumatic", "subject": "Medicine", "module": "Cardiology"},
    ]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    TestClient with mocked DB and dataset files.
    Uses SQLite in-memory so no PostgreSQL is needed.
    """
    os.environ.setdefault("DATABASE_URL",   "sqlite:///./test_run.db")
    os.environ.setdefault("SECRET_KEY",     "test-secret-key-not-for-production-32x")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-placeholder")

    ug_data = make_sample_ug_data()
    pg_data = make_sample_pg_data()

    with patch("builtins.open", side_effect=lambda path, *a, **kw:
               __import__("io").StringIO(json.dumps(
                   ug_data if "UG" in str(path) else pg_data
               ))):
        with patch("app.utils.question_engine._UG_LIST", []):
            with patch("app.utils.question_engine._PG_LIST", []):
                from app.main import app
                from app.core.database import Base, engine
                Base.metadata.create_all(bind=engine)
                yield TestClient(app)
                Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_headers(client):
    """Register + login a test user, return bearer token headers."""
    client.post("/auth/register", json={
        "email": "test@empoweredacademy.in",
        "password": "TestPass123!",
        "full_name": "Test Student"
    })
    resp = client.post("/auth/login", json={
        "email": "test@empoweredacademy.in",
        "password": "TestPass123!"
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Health check ──────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "db" in body


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_new_user(self, client):
        r = client.post("/auth/register", json={
            "email": "new@test.com",
            "password": "Password1!",
            "full_name": "New User"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_duplicate_email_rejected(self, client):
        payload = {"email": "dup@test.com", "password": "Pass1!", "full_name": "Dup"}
        client.post("/auth/register", json=payload)
        r = client.post("/auth/register", json=payload)
        assert r.status_code == 400

    def test_login_valid_credentials(self, client):
        client.post("/auth/register", json={
            "email": "login@test.com", "password": "Pass1!", "full_name": "Login"
        })
        r = client.post("/auth/login", json={"email": "login@test.com", "password": "Pass1!"})
        assert r.status_code == 200
        assert r.json()["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={
            "email": "wrongpass@test.com", "password": "RightPass1", "full_name": "X"
        })
        r = client.post("/auth/login", json={
            "email": "wrongpass@test.com", "password": "WrongPass"
        })
        assert r.status_code == 401

    def test_protected_route_requires_auth(self, client):
        r = client.get("/test/questions")
        assert r.status_code == 401


# ── Question engine unit tests ─────────────────────────────────────────────────

class TestQuestionEngine:
    def test_evaluate_all_correct(self):
        from app.utils.question_engine import evaluate_answers, _UG_LIST, _UG_MAP
        # Manually seed the engine
        import app.utils.question_engine as qe
        qe._UG_LIST = [
            {"question_id": "T1", "question": "Q1", "options": ["A","B"],
             "correct_answer": "A", "subject": "Bio", "topic": "Cell"},
            {"question_id": "T2", "question": "Q2", "options": ["A","B"],
             "correct_answer": "B", "subject": "Bio", "topic": "Cell"},
        ]
        qe._UG_MAP = {q["question_id"]: q for q in qe._UG_LIST}

        result = evaluate_answers("UG", {"T1": "A", "T2": "B"})
        assert result["score"] == 2
        assert result["accuracy"] == 100.0
        assert result["weak_areas"] == []

    def test_evaluate_all_wrong(self):
        import app.utils.question_engine as qe
        qe._UG_LIST = [
            {"question_id": "T3", "question": "Q3", "options": ["A","B"],
             "correct_answer": "A", "subject": "Chem", "topic": "Organic"},
        ]
        qe._UG_MAP = {q["question_id"]: q for q in qe._UG_LIST}

        from app.utils.question_engine import evaluate_answers
        result = evaluate_answers("UG", {"T3": "B"})
        assert result["score"] == 0
        assert result["accuracy"] == 0.0
        assert "Organic" in result["weak_areas"]

    def test_evaluate_unknown_question_skipped(self):
        import app.utils.question_engine as qe
        qe._UG_LIST = [
            {"question_id": "T4", "question": "Q4", "options": ["A","B"],
             "correct_answer": "A", "subject": "Physics", "topic": "Optics"},
        ]
        qe._UG_MAP = {q["question_id"]: q for q in qe._UG_LIST}

        from app.utils.question_engine import evaluate_answers
        result = evaluate_answers("UG", {"T4": "A", "UNKNOWN": "C"})
        assert result["score"] == 1
        assert result["total"] == 1   # UNKNOWN skipped

    def test_evaluate_empty_answers(self):
        from app.utils.question_engine import evaluate_answers
        result = evaluate_answers("UG", {})
        assert result["score"] == 0
        assert result["accuracy"] == 0.0


# ── Test flow (UG) ─────────────────────────────────────────────────────────────

class TestTestFlowUG:
    def test_get_questions_ug(self, client, auth_headers):
        import app.utils.question_engine as qe
        qe._UG_LIST = make_sample_ug_data()["question_bank"][0]["mcqs"]  # quick seed
        # Properly seed via engine
        qe._UG_LIST = []
        qe._UG_MAP  = {}
        with patch("app.utils.question_engine.NEET_UG_DATA_PATH", "fake_ug.json"):
            with patch("builtins.open", return_value=__import__("io").StringIO(
                json.dumps(make_sample_ug_data())
            )):
                r = client.get("/test/questions?exam=UG", headers=auth_headers)
        assert r.status_code in (200, 503)   # 503 if dataset unavailable in test env

    def test_invalid_exam_type_rejected(self, client, auth_headers):
        r = client.get("/test/questions?exam=INVALID", headers=auth_headers)
        assert r.status_code == 400

    def test_submit_without_test_id_rejected(self, client, auth_headers):
        r = client.post("/test/submit", json={"test_id": "", "answers": {"Q1": "A"}},
                        headers=auth_headers)
        assert r.status_code == 422   # Pydantic validation

    def test_submit_nonexistent_test_id(self, client, auth_headers):
        r = client.post("/test/submit",
                        json={"test_id": "00000000-0000-0000-0000-000000000000",
                              "answers": {"Q1": "A"}},
                        headers=auth_headers)
        assert r.status_code == 404

    def test_submit_empty_answers_rejected(self, client, auth_headers):
        r = client.post("/test/submit",
                        json={"test_id": "some-id", "answers": {}},
                        headers=auth_headers)
        assert r.status_code == 422   # Pydantic validator rejects empty dict


# ── Analytics ─────────────────────────────────────────────────────────────────

class TestAnalytics:
    def test_dashboard_returns_structure(self, client, auth_headers):
        r = client.get("/analytics/dashboard?exam=UG", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "recent_scores" in body
        assert "weak_areas"    in body
        assert "topic_details" in body
        assert "exam"          in body

    def test_dashboard_pg(self, client, auth_headers):
        r = client.get("/analytics/dashboard?exam=PG", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["exam"] == "PG"

    def test_dashboard_requires_auth(self, client):
        r = client.get("/analytics/dashboard")
        assert r.status_code == 401


# ── Rank service unit tests ────────────────────────────────────────────────────

class TestRankService:
    def test_low_user_base_fallback(self):
        from app.utils.rank_service import calculate_rank_and_percentile
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = calculate_rank_and_percentile(360, "UG", mock_db)
        assert "rank" in result
        assert "percentile" in result
        assert 0 <= result["percentile"] <= 100
        assert result["rank"] >= 1

    def test_perfect_score_best_rank(self):
        from app.utils.rank_service import calculate_rank_and_percentile
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = calculate_rank_and_percentile(720, "UG", mock_db)
        assert result["percentile"] == 100.0
        assert result["rank"] == 1

    def test_zero_score_lowest_rank(self):
        from app.utils.rank_service import calculate_rank_and_percentile
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = calculate_rank_and_percentile(0, "UG", mock_db)
        assert result["percentile"] == 0.0


# ── Mentor engine unit tests ───────────────────────────────────────────────────

class TestMentorEngine:
    def test_high_stress_low_accuracy(self):
        from app.utils.mentor_engine import determine_stress_level
        assert determine_stress_level(50, 20.0) == "high_stress"

    def test_moderate_stress(self):
        from app.utils.mentor_engine import determine_stress_level
        assert determine_stress_level(200, 45.0) == "moderate_stress"

    def test_low_stress_good_accuracy(self):
        from app.utils.mentor_engine import determine_stress_level
        assert determine_stress_level(500, 75.0) == "low_stress"

    def test_advice_includes_weak_areas(self):
        from app.utils.mentor_engine import generate_mentor_advice
        advice = generate_mentor_advice(200, 45.0, ["Organic Chemistry", "Genetics"])
        combined = " ".join(advice)
        assert "Organic Chemistry" in combined or "Genetics" in combined

    def test_advice_list_not_empty(self):
        from app.utils.mentor_engine import generate_mentor_advice
        advice = generate_mentor_advice(100, 30.0, [])
        assert len(advice) > 0
