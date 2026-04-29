from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import json
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.course import Course, Enrollment
from app.models.test_attempt import TestAttempt, AttemptStatus
from app.models.analytics import TestResult
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.utils.rank_service import calculate_rank_and_percentile

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/me", response_model=ProfileOut)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's profile with statistics and enrolled courses."""
    
    try:
        # Get or create user profile
        user_profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
        if not user_profile:
            user_profile = UserProfile(user_id=current_user.id)
            db.add(user_profile)
            db.commit()
            db.refresh(user_profile)
        
        # Get user's test statistics - all tests since registration
        test_attempts = (
            db.query(TestAttempt)
            .filter(
                TestAttempt.user_id == current_user.id,
                TestAttempt.status == AttemptStatus.submitted  # Only count completed tests
            )
            .all()
        )
        
        # Calculate statistics based on all submitted tests
        tests_taken = len(test_attempts)
        scores = [attempt.score for attempt in test_attempts if attempt.score is not None]
        average_score = round(sum(scores) / len(scores), 1) if scores else None
        
        # Get latest score for rank calculation from most recent test
        latest_score = None
        latest_exam_type = "UG"  # Default
        
        if test_attempts:
            # Sort by submission date to get the most recent
            sorted_attempts = sorted(test_attempts, key=lambda x: x.submitted_at or x.created_at, reverse=True)
            latest_attempt = sorted_attempts[0]
            latest_score = latest_attempt.score
            latest_exam_type = latest_attempt.exam
        
        # Calculate rank based on latest score and exam type
        rank_data = None
        if latest_score is not None:
            try:
                # Use exam type from user profile if available, otherwise from latest test
                exam_type = user_profile.target_exam
                if exam_type == "NEET PG":
                    exam_type = "PG"
                elif exam_type == "NEET UG":
                    exam_type = "UG"
                else:
                    # Fallback to latest test exam type
                    exam_type = latest_exam_type
                
                rank_data = calculate_rank_and_percentile(latest_score, exam_type, db)
            except Exception as e:
                logger.warning(f"Failed to calculate rank for user {current_user.id}: {e}")
                rank_data = {"rank": None, "percentile": None}
        
        # Get enrolled courses
        enrollments = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == current_user.id)
            .all()
        )
        
        course_ids = [e.course_id for e in enrollments]
        courses = {c.id: c for c in db.query(Course).filter(Course.id.in_(course_ids)).all()}
        
        enrolled_courses = [
            {
                "enrollment_id": e.id,
                "payment_status": e.payment_status,
                "course_id": e.course_id,
                "title": courses[e.course_id].title,
                "description": courses[e.course_id].description,
                "exam": courses[e.course_id].exam,
                "price": float(courses[e.course_id].price),
                "keypoints": courses[e.course_id].keypoints or [],
                "is_active": courses[e.course_id].is_active,
            }
            for e in enrollments
            if e.course_id in courses
        ]
        
        # Parse preferred subjects from JSON string
        preferred_subjects = None
        if user_profile.preferred_subjects:
            try:
                preferred_subjects = json.loads(user_profile.preferred_subjects)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse preferred_subjects for user {current_user.id}: {e}")
                preferred_subjects = None
        
        return ProfileOut(
            user_id=current_user.id,
            name=current_user.full_name or "",
            email=current_user.email,
            phone_number=user_profile.phone_number,
            date_of_birth=user_profile.date_of_birth,
            gender=user_profile.gender,
            target_exam=user_profile.target_exam,
            level=user_profile.level,
            preferred_subjects=preferred_subjects,
            study_goal=user_profile.study_goal,
            rank=rank_data["rank"] if rank_data else None,
            average_score=average_score,
            tests_taken=tests_taken,
            enrolled_courses=enrolled_courses,
        )
        
    except Exception as e:
        logger.error(f"Failed to get profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "PROFILE_FETCH_FAILED",
                "message": "Unable to fetch profile information. Please try again later.",
                "user_friendly": True
            }
        )


@router.patch("/me", response_model=ProfileOut)
def update_profile(
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user's profile information."""
    
    try:
        # Get or create user profile
        user_profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
        if not user_profile:
            user_profile = UserProfile(user_id=current_user.id)
            db.add(user_profile)
        
        # Update only provided fields
        update_data = profile_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "NO_DATA_PROVIDED",
                    "message": "No data provided for update.",
                    "user_friendly": True
                }
            )
        
        for field, value in update_data.items():
            try:
                if field == "full_name":
                    current_user.full_name = value
                elif field == "phone_number":
                    user_profile.phone_number = value
                elif field == "date_of_birth":
                    user_profile.date_of_birth = value
                elif field == "gender":
                    user_profile.gender = value
                elif field == "target_exam":
                    user_profile.target_exam = value
                elif field == "level":
                    user_profile.level = value
                elif field == "preferred_subjects":
                    # Convert list to JSON string for storage
                    if value is not None:
                        try:
                            user_profile.preferred_subjects = json.dumps(value)
                        except (TypeError, ValueError) as e:
                            logger.warning(f"Failed to serialize preferred_subjects for user {current_user.id}: {e}")
                            raise HTTPException(
                                status_code=400,
                                detail={
                                    "error": "INVALID_PREFERRED_SUBJECTS",
                                    "message": "Invalid format for preferred subjects.",
                                    "user_friendly": True
                                }
                            )
                    else:
                        user_profile.preferred_subjects = None
                elif field == "study_goal":
                    user_profile.study_goal = value
            except Exception as e:
                logger.error(f"Failed to update field {field} for user {current_user.id}: {e}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "FIELD_UPDATE_FAILED",
                        "message": f"Failed to update {field}. Please check the data format.",
                        "user_friendly": True
                    }
                )
        
        db.commit()
        db.refresh(current_user)
        db.refresh(user_profile)
        
        # Return updated profile (reuse the GET logic)
        return get_profile(db=db, current_user=current_user)
        
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        logger.error(f"Failed to update profile for user {current_user.id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "PROFILE_UPDATE_FAILED",
                "message": "Unable to update profile. Please try again later.",
                "user_friendly": True
            }
        )