from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.security import require_admin
from app.core.database import get_db
from app.models.user import User
from app.models.course import Course, Enrollment
from app.utils.paths import APP_DIR

router = APIRouter()

_DASHBOARD_HTML = Path(APP_DIR) / "templates" / "dashboard.html"
_LOGIN_HTML     = Path(APP_DIR) / "templates" / "admin_login.html"


@router.get("/admin-login", response_class=HTMLResponse, tags=["admin"], include_in_schema=False)
def admin_login_page():
    return HTMLResponse(content=_LOGIN_HTML.read_text())


@router.get("/dashboard", response_class=HTMLResponse, tags=["admin"], include_in_schema=False)
def admin_dashboard():
    return HTMLResponse(content=_DASHBOARD_HTML.read_text())


@router.get("/dashboard/data", tags=["admin"])
def admin_dashboard_data(user=Depends(require_admin), db: Session = Depends(get_db)):
    # All non-admin users
    users = (
        db.query(User)
        .filter(User.role != "admin")
        .order_by(User.created_at.desc())
        .all()
    )

    # Enrollment count per user
    enrollment_counts = {
        row.user_id: row.count
        for row in db.query(Enrollment.user_id, func.count(Enrollment.id).label("count"))
                      .group_by(Enrollment.user_id)
                      .all()
    }

    # Latest enrolled course title per user
    latest_enrollment = (
        db.query(Enrollment.user_id, Course.title)
        .join(Course, Course.id == Enrollment.course_id)
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    latest_course = {}
    for row in latest_enrollment:
        if row.user_id not in latest_course:
            latest_course[row.user_id] = row.title

    users_data = [
        {
            "id":          u.id,
            "name":        u.full_name or "—",
            "email":       u.email,
            "role":        u.role,
            "created_at":  u.created_at.strftime("%d %b %Y") if u.created_at else "—",
            "course":      latest_course.get(u.id, "—"),
            "enrollments": enrollment_counts.get(u.id, 0),
        }
        for u in users
    ]

    # Courses
    courses = db.query(Course).order_by(Course.created_at.desc()).all()
    enroll_per_course = {
        row.course_id: row.count
        for row in db.query(Enrollment.course_id, func.count(Enrollment.id).label("count"))
                      .group_by(Enrollment.course_id)
                      .all()
    }
    courses_data = [
        {
            "id":       c.id,
            "name":     c.title,
            "category": c.exam,
            "enrolled": enroll_per_course.get(c.id, 0),
            "status":   "Active" if c.is_active else "Inactive",
            "price":    float(c.price),
        }
        for c in courses
    ]

    stats = {
        "total_users":   len(users_data),
        "active_courses": sum(1 for c in courses if c.is_active),
        "total_enrollments": db.query(func.count(Enrollment.id)).scalar() or 0,
    }

    return JSONResponse({"users": users_data, "courses": courses_data, "stats": stats})

@router.get("/admins", tags=["admin"])
def list_admins(user=Depends(require_admin), db: Session = Depends(get_db)):
    admins = db.query(User).filter(User.role.in_(["admin", "page_admin"])).all()
    return [
        {"id": a.id, "name": a.full_name, "email": a.email, "role": a.role, "created_at": str(a.created_at)}
        for a in admins
    ]
