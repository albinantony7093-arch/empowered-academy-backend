# Empowered Academy API

Backend API for the Empowered Academy platform — a NEET UG/PG preparation app with courses, tests, analytics, AI mentoring, and payments.

Built with **FastAPI**, **PostgreSQL**, and **Docker**.

---

## Tech Stack

- **FastAPI** 0.111 — API framework
- **PostgreSQL** — primary database (hosted on AWS RDS)
- **SQLAlchemy** 2.0 — ORM
- **Alembic** — database migrations
- **JWT** (python-jose) — access + refresh token auth
- **bcrypt** — password hashing
- **OpenAI** — AI mentor responses
- **Cashfree** — payment gateway
- **Resend** — transactional email (OTP, password reset)
- **Sentry** — error monitoring
- **Docker** + **docker-compose** — containerization

---

## Project Structure

```
app/
├── core/           # config, database, security
├── models/         # SQLAlchemy ORM models
├── routes/         # API route handlers
├── schemas/        # Pydantic request/response schemas
├── utils/          # question engine, rank service, mentor engine, mail
├── middleware/      # request logging
├── templates/      # admin HTML pages
└── data/           # question bank JSON files
scripts/            # seed scripts
tests/              # pytest test suite
```

---

## Setup

### 1. Clone and configure

```bash
cp .env.example .env
# Fill in your values in .env
```

### 2. Run with Docker

```bash
docker compose up --build
```

API available at `http://localhost:8000`

### 3. Run locally (without Docker)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing secret (min 32 chars) |
| `ALGORITHM` | JWT algorithm (default: HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | Refresh token TTL |
| `ALLOWED_ORIGINS` | CORS origins (JSON array) |
| `OPENAI_API_KEY` | OpenAI API key |
| `CASHFREE_APP_ID` | Cashfree app ID |
| `CASHFREE_SECRET_KEY` | Cashfree secret key |
| `CASHFREE_ENV` | `sandbox` or `production` |
| `MAIL_USERNAME` | SMTP email address |
| `MAIL_PASSWORD` | SMTP app password |
| `SENTRY_DSN` | Sentry DSN (optional) |
| `FRONTEND_URL` | Frontend base URL |

---

## API Routes

| Prefix | Module | Description |
|---|---|---|
| `/auth` | auth.py | Register, OTP verify, login, refresh, forgot/reset password |
| `/profile` | profile.py | Get and update user profile |
| `/courses` | courses.py | List courses, enroll, test start/submit |
| `/test` | test.py | Standalone test questions and submission |
| `/analytics` | analytics.py | Dashboard, scores, weak areas, rank |
| `/ai` | ai.py | AI mentor chat |
| `/payment` | payment.py | Cashfree payment initiation and webhook |
| `/diagnostic` | diagnostic.py | Diagnostic test flow |
| `/dashboard` | admin.py | Admin dashboard (HTML) |
| `/health` | main.py | Health check |

Full interactive docs: `http://localhost:8000/docs`

---

## Authentication

All protected routes require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Token flow:
1. `POST /auth/login` → returns `access_token` + `refresh_token`
2. Access token expires → `POST /auth/refresh` with `refresh_token` to get new tokens
3. `401` means access token is invalid or expired
4. `403` means authenticated but not authorized (wrong role)

---

## Admin Panel

- Login: `http://localhost:8000/admin-login`
- Dashboard: `http://localhost:8000/dashboard` (admin role required)

To create an admin user:

```bash
docker compose exec api python -c "
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
db = SessionLocal()
u = User(email='admin@example.com', hashed_password=hash_password('Admin@123'), full_name='Admin', role='admin')
db.add(u)
db.commit()
print('Done:', u.email)
"
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use SQLite in-memory — no real DB or API keys needed.

---

## Database

Check admin users:

```bash
docker compose exec db psql -U postgres -d postgres -c \
  "SELECT id, full_name, email, role FROM users WHERE role IN ('admin', 'page_admin');"
```
