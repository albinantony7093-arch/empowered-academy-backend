# Crash Course Auto-Activation & Email Notification

## What it does

When the crash course window opens (June 5, 2026 5:00 AM IST), the system automatically:
1. Sets `is_active = True` on the Crash Course in the database
2. Sends a "Course is Now Live" email to **every student account**

When the window closes (June 21, 2026 5:00 PM IST):
1. Sets `is_active = False` on the Crash Course

## How it works

- **APScheduler** runs a background job every 1 minute
- Compares current time against `CRASH_COURSE_START` and `CRASH_COURSE_END` from `.env`
- Activates/deactivates course and sends emails exactly once per activation

## Configuration

In `.env`:
```env
CRASH_COURSE_START=2026-06-05T05:00:00+05:30
CRASH_COURSE_END=2026-06-21T17:00:00+05:30
```

## Email Template

Subject: `🌟 NEET Crash Course is Now Live — Empowered Academy`

Content includes:
- Notification that the crash course is active
- Access window end date
- Direct link to courses page
- Key features (5,200+ MCQs, AI recovery engine, etc.)

## Safety

- Only touches the "Crash Course" row (other courses untouched)
- Emails sent exactly once per activation window
- Requires `MAIL_USERNAME` and `MAIL_PASSWORD` in `.env` (already configured)
- Gracefully handles mail failures per-user (logs warning, continues)

## Dependencies Added

`requirements.txt`:
- `APScheduler==3.10.4`

## Files Modified

1. `requirements.txt` — added APScheduler
2. `app/core/config.py` — added CRASH_COURSE_START/END
3. `app/main.py` — added scheduler startup/shutdown + tick job
4. `app/utils/mail.py` — added crash course live email template
5. `.env` — added crash course date config

## Testing Locally

To test immediately, temporarily set dates in `.env`:
```env
CRASH_COURSE_START=2025-01-01T10:00:00+05:30
CRASH_COURSE_END=2025-12-31T23:59:00+05:30
```

Then restart the container:
```bash
docker-compose restart api
docker logs -f empowered-academy-backend-api-1
```

You should see:
```
Crash course scheduler started
Crash Course activated
Sending crash course live emails to N students
Crash course live emails sent
```

Check student inboxes for the email.
