# Empowered Academy — API Reference

> Base URL: `https://your-api-domain.com`  
> Interactive docs: `{base_url}/docs`  
> All request/response bodies are JSON unless noted.

---

## Authentication

Most endpoints require a Bearer token:

```
Authorization: Bearer <access_token>
```

### Token Lifecycle

| Token | TTL | Purpose |
|---|---|---|
| `access_token` | 5 min | Authenticate API requests |
| `refresh_token` | 10 min | Get a new access token |

When an access token expires, call `POST /auth/refresh` with the refresh token to get new tokens. If the refresh token also expires, the user must log in again.

**Status codes used for auth:**
- `401` — access token is missing, invalid, or expired
- `403` — authenticated but not allowed (wrong role)
- `400` — invalid credentials at login

---

## Auth `/auth`

### POST `/auth/register`

**How it works:**
The user submits their name, email, phone, and password. The backend checks if the email is already registered — if it is, it returns `400`. If not, it hashes the password and saves the user details in a temporary `pending_users` table (not the real users table yet). A random 6-digit OTP is generated, stored with a 10-minute expiry, and emailed to the user asynchronously. The account is only created after OTP verification.

**Request**
```json
{
  "email": "user@example.com",
  "password": "Secret123",
  "full_name": "John Doe",
  "phone_number": "9876543210"
}
```

**Response `200`**
```json
{ "message": "OTP sent to user@example.com. Valid for 10 minutes." }
```

**Errors:** `400` email already registered

---

### POST `/auth/verify-otp`

**How it works:**
The user submits their email and the OTP they received. The backend looks up the pending registration, checks if the OTP has expired (returns `410` if so), and validates the OTP matches. If everything is correct, it creates the actual `User` record, deletes the pending entry, and returns a fresh access + refresh token pair so the user is immediately logged in.

**Request**
```json
{
  "email": "user@example.com",
  "otp": "123456"
}
```

**Response `200`**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:** `400` invalid OTP · `404` no pending registration · `410` OTP expired

---

### POST `/auth/login`

**How it works:**
The user submits their email and password. The backend fetches the user by email, then uses bcrypt to verify the password against the stored hash. If either the user doesn't exist or the password is wrong, it returns the same generic `400` error (avoids leaking which one failed). On success, it generates a new access + refresh token pair and returns them.

**Request**
```json
{
  "email": "user@example.com",
  "password": "Secret123"
}
```

**Response `200`**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Errors:** `400` invalid credentials

---

### POST `/auth/refresh`

**How it works:**
The client sends the refresh token. The backend decodes it, verifies it's a refresh token type (not an access token), extracts the user ID, and checks the user still exists in the DB. If all checks pass, it issues a brand new access + refresh token pair. This is how the frontend silently keeps the user logged in without them having to re-enter their password.

**Request**
```json
{ "refresh_token": "eyJ..." }
```

**Response `200`** — same as login response

**Errors:** `400` invalid/expired refresh token · `404` user not found

---

### POST `/auth/forgot-password`

**How it works:**
User submits their email. The backend checks if the account exists — if it doesn't, it returns `404`. If it does, it generates a 6-digit OTP, stores it with a 10-minute expiry in a `password_reset_otps` table (upserts if one already exists), and emails it. The OTP must then be used in the reset-password step.

**Request**
```json
{ "email": "user@example.com" }
```

**Response `200`**
```json
{ "message": "If this email is registered, an OTP has been sent." }
```

**Errors:** `404` email not found

---

### POST `/auth/reset-password`

**How it works:**
The user sends email, OTP, and their new password in one call. The backend finds the OTP record, validates it hasn't expired, checks it matches, finds the user, hashes the new password, saves it, and deletes the OTP record. No separate "verify OTP" step — everything is done atomically in one request.

**Request**
```json
{
  "email": "user@example.com",
  "otp": "123456",
  "new_password": "NewPass456"
}
```

**Response `200`**
```json
{ "message": "Password reset successfully. You can now log in." }
```

**Errors:** `400` invalid OTP · `404` not found · `410` OTP expired

---

## Profile `/profile` 🔒

### GET `/profile/me`

**How it works:**
Extracts the user from the Bearer token. Looks up or auto-creates a `user_profiles` row for them. Fetches all submitted test attempts, calculates `tests_taken` and `average_score` from them. Takes the most recent attempt to calculate rank and percentile against all other users using SQL aggregates (no data loaded into memory). Fetches all enrollments and joins with course data to build the `enrolled_courses` list. Returns everything in one response.

**Response `200`**
```json
{
  "user_id": "uuid",
  "name": "John Doe",
  "email": "user@example.com",
  "phone_number": "9876543210",
  "date_of_birth": "2000-01-15",
  "gender": "Male",
  "target_exam": "NEET UG",
  "level": "Class 12",
  "preferred_subjects": ["Biology", "Chemistry"],
  "study_goal": "Top 100 rank",
  "rank": 142,
  "percentile": 98.5,
  "average_score": 112.4,
  "tests_taken": 18,
  "latest_test_marks": 340.0,
  "enrolled_courses": [...]
}
```

---

### PATCH `/profile/me`

**How it works:**
Only the fields you send are updated — unset fields are ignored (Pydantic `exclude_unset`). `full_name` is saved on the `users` table, all other fields go to `user_profiles`. `preferred_subjects` is a list on the API but stored as a JSON string in the DB — the backend handles serialization/deserialization automatically. After saving, it calls the same logic as `GET /profile/me` and returns the full updated profile.

**Request** (all fields optional)
```json
{
  "full_name": "Jane Doe",
  "phone_number": "9876543210",
  "date_of_birth": "2000-01-15",
  "gender": "Female",
  "target_exam": "NEET UG",
  "level": "Class 12",
  "preferred_subjects": ["Biology"],
  "study_goal": "Get into AIIMS"
}
```

**Response `200`** — same as `GET /profile/me`

**Errors:** `400` no data provided or invalid field value

---

## Courses `/courses`

### GET `/courses/`

**How it works:**
Fetches all active courses from the DB. If a user token is present (optional auth), it also fetches that user's enrollments and maps them to courses — so each course in the response has `is_enrolled`, `payment_status`, `trial_ends_at`, and `plan_expires_at` fields populated. Unauthenticated users get `null` for those fields. Useful for rendering the course listing page with the correct CTA (Enroll / Continue Trial / Upgrade / Access Locked).

**Auth:** Optional

---

### POST `/courses/{course_id}/enroll` 🔒

**How it works:**
Checks the course exists and is active. If the user already has an enrollment, returns `409` (except for a special case where `pending_payment` enrollments with no trial started can be re-initialized). For new enrollments:
- **Crash Course** (`is_free=true`) → status set to `"free"`, expiry set to a fixed date
- **Paid courses** (NEET UG/PG) → status set to `"trial"`, expiry set to `now + free_trial_days` (default 4 days)

After saving, sends an enrollment welcome email in a background thread.

**Response `201`** — enrollment object with `payment_status` and `trial_ends_at`

**Errors:** `404` course not found · `409` already enrolled

---

### GET `/courses/my` 🔒

**How it works:**
Fetches all of the user's enrollments. On every call, it syncs expiry — if a trial/free/paid period has ended, the `payment_status` is flipped to `"locked"` in the DB automatically. This means the frontend always gets accurate, up-to-date access status without a separate cron job.

---

### GET `/courses/{course_id}/test/start` 🔒

**How it works:**
First calls the enrollment access check — validates enrollment exists, syncs expiry, and blocks if status is `locked`, `cancelled`, or `pending_payment`. If access is valid, determines the applicable limits (trial limits vs paid limits). Checks daily test count against the limit. Generates random questions from the question bank based on `questions_per_test` limit. Creates a `TestAttempt` record with status `generated` and saves the question list (question IDs + difficulties) as JSON. Returns the full question objects to the client.

**Errors:** `403` not enrolled / access locked · `429` daily limit reached

---

### POST `/courses/test/submit` 🔒

**How it works:**
Looks up the `TestAttempt` by `test_id` and verifies it belongs to the current user. Re-checks enrollment access (in case trial expired between start and submit). Evaluates the answers against the correct answers from the question bank, applying difficulty-weighted scoring (easy=1pt, medium=2pt, hard=3pt). Saves the attempt as `submitted`, stores each individual answer in the `responses` table, and writes a summary to `test_results` (used for rank calculation). Calculates rank/percentile using SQL aggregates. Generates 3 personalised mentor advice messages. Returns the full result.

**Errors:** `404` test not found · `409` already submitted · `403` enrollment not active

---

## Analytics `/analytics` 🔒

### GET `/analytics/dashboard?course_id={id}`

**How it works:**
Filters all test attempts and responses for the given `course_id`. Uses the most recent submitted attempt to get the latest test details (score, marks, accuracy). Aggregates all responses across all attempts by topic to identify weak areas — any topic with accuracy below 60% is flagged. Calculates rank and percentile from the latest score. Generates 3 random mentor advice messages from a pool of personalised + general advice, shuffled each time so users see variety across visits.

**Errors:** `404` course not found

---

## Diagnostic `/diagnostic` 🔒

### GET `/diagnostic/test/start`

**How it works:**
Same flow as course test start, but no enrollment check — any authenticated user can take unlimited diagnostic tests. Generates 30 questions from the diagnostic question bank (a separate dataset). Creates a `DiagnosticAttempt` record and returns the questions. Designed to assess a new user's level before they enroll in a course.

---

### POST `/diagnostic/test/submit`

**How it works:**
Evaluates answers against the diagnostic question bank. Saves the result directly on the `DiagnosticAttempt` row (no separate responses table — responses are stored as inline JSON for simplicity). Returns the same result structure as a course test, but `rank` and `percentile` are always `null` since diagnostic tests don't count toward ranking.

---

### GET `/diagnostic/history`

**How it works:**
Fetches all `DiagnosticAttempt` rows for the current user ordered by most recent first. Returns a summary of each test — score, marks, accuracy, and timestamps. Useful for showing a student their progress over multiple diagnostic attempts.

---

## Payment `/payment` 🔒

### POST `/payment/create-order`

**How it works:**
Two flows depending on `direct_purchase`:
- `false` (default) — user must already have a trial/locked enrollment. Common case: trial expired, user wants to upgrade.
- `true` — creates a `pending_payment` enrollment on the fly. For users who want to skip the trial.

Checks for an existing `created` payment order and returns it if found (idempotent — safe to call multiple times). Saves a `Payment` row with status `"created"` to the DB *before* calling Cashfree — this prevents lost payments if the API call succeeds but the save fails. Calls Cashfree Orders API with retry logic (up to 3 attempts with exponential backoff). Returns the `payment_session_id` which the frontend passes to the Cashfree JS SDK to open the payment sheet.

**Request**
```json
{
  "course_id": "uuid",
  "direct_purchase": false
}
```

**Response `200`**
```json
{
  "order_id": "uuid",
  "payment_session_id": "session_...",
  "amount": 4999.0,
  "currency": "INR"
}
```

---

### POST `/payment/webhook`

**How it works:**
Cashfree calls this automatically after a payment event. The backend verifies the webhook signature (HMAC-SHA256 with base64 encoding) to ensure the request is genuinely from Cashfree. On `PAYMENT_SUCCESS_WEBHOOK`, it marks the payment as `"paid"`, sets `paid_at`, saves card/UPI details, and calls `_unlock_enrollment` which sets enrollment status to `"paid"` and sets `plan_expires_at` based on `validity_days`. On failure events, marks the payment as `"failed"`. Idempotent — if the payment is already `"paid"`, it skips processing silently. Sends a confirmation email asynchronously after unlock.

> This is the authoritative source of truth for payment status. Do not rely solely on the frontend verify call.

---

### GET `/payment/verify/{order_id}`

**How it works:**
Frontend calls this after the Cashfree JS SDK returns. The backend queries Cashfree's API directly for the latest order status and scans the payments list for a `SUCCESS` entry. If found and not already marked paid in our DB, it performs the same unlock logic as the webhook. Acts as a safety net for cases where the webhook arrives late (common in sandbox/localhost environments). Returns `{ "status": "paid" }`, `{ "status": "failed" }`, or `{ "status": "created" }` (still pending).

---

### GET `/payment/history`

**How it works:**
Simple DB query — fetches all `Payment` rows for the current user ordered by most recent first. Returns full payment details including method, card info, UPI VPA, error messages (if failed), and timestamps.

---

## Health Check

### GET `/health`

**How it works:**
Runs a `SELECT 1` against the database to verify connectivity. Returns `"connected"` or `"unreachable"` for the DB status. No auth required — safe to hit from load balancers or uptime monitors.

**Response `200`**
```json
{
  "status": "ok",
  "version": "1.3.0",
  "db": "connected"
}
```

---

## Error Response Format

All errors return a consistent JSON body:

```json
{ "message": "Human readable error description" }
```

Some domain errors include extra fields:
```json
{
  "message": "Unable to fetch profile information. Please try again later.",
  "error": "PROFILE_FETCH_FAILED",
  "user_friendly": true
}
```

---

## Status Code Summary

| Code | Meaning |
|---|---|
| `200` | Success |
| `201` | Created |
| `400` | Bad request / invalid input / wrong credentials |
| `401` | Access token missing, invalid, or expired |
| `403` | Authenticated but not authorized (wrong role or locked enrollment) |
| `404` | Resource not found |
| `409` | Conflict (already exists / already submitted) |
| `410` | Gone (OTP expired) |
| `422` | Validation error (missing or wrong type fields) |
| `429` | Rate limited (daily test limit reached) |
| `500` | Internal server error |
| `503` | External service unavailable (payment gateway) |

---

## Notes for Frontend Integration

- Store `access_token` and `refresh_token` in `localStorage` after login.
- On any `401` response, call `POST /auth/refresh`. If that also fails, redirect to login.
- On `403` from a course test, check enrollment `payment_status` — the trial may have expired. Show an upgrade prompt.
- The Cashfree payment flow:
  1. `POST /payment/create-order` → get `payment_session_id`
  2. Open Cashfree JS SDK with `payment_session_id`
  3. After SDK callback, call `GET /payment/verify/{order_id}` to confirm status
  4. Webhook runs in parallel on the backend — never rely solely on frontend verify for granting access.
- OTPs expire in **10 minutes**.
- Free trial lasts **4 days** for paid courses (NEET UG/PG).
- Always call `GET /courses/my` after enrollment or payment to get the latest access status.
