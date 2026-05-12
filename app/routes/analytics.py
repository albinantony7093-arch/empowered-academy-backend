import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.analytics import TestResult
from app.models.response import Response
from app.models.test_attempt import TestAttempt
from app.models.course import Course
from app.utils.rank_service import calculate_rank_and_percentile
from app.utils.mentor_engine import generate_mentor_advice
import random

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard")
def get_dashboard(
    course_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    """
    Returns dashboard data filtered by course_id.
    """
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": "COURSE_NOT_FOUND",
                    "message": "Course not found.",
                    "user_friendly": True
                }
            )
        exam = course.exam.upper()

        try:
            attempt_ids = [
                a.id for a in db.query(TestAttempt).filter(
                    TestAttempt.user_id == user_id,
                    TestAttempt.course_id == course_id,
                ).all()
            ]

            results = (
                db.query(TestResult)
                .filter(TestResult.user_id == user_id, TestResult.attempt_id.in_(attempt_ids))
                .order_by(TestResult.created_at.desc())
                .limit(20)
                .all()
            )

            # Get detailed recent scores with accuracy and total questions
            recent_scores = []
            latest_test_details = None
            
            for i, result in enumerate(results):
                if result.score is not None:
                    recent_scores.append(result.score)
                    
                    # Get details for the most recent test (first result)
                    if i == 0:
                        try:
                            # Get attempt details for this result
                            attempt = db.query(TestAttempt).filter(TestAttempt.id == result.attempt_id).first()
                            
                            # Count total questions and correct answers for this attempt
                            attempt_responses = db.query(Response).filter(Response.attempt_id == result.attempt_id).all()
                            total_questions = len(attempt_responses)
                            correct_answers = sum(1 for r in attempt_responses if r.is_correct)
                            accuracy = round((correct_answers / total_questions * 100), 1) if total_questions > 0 else 0.0
                            
                            latest_test_details = {
                                "latest_score": result.score,
                                "total_questions": total_questions,
                                "correct_answers": correct_answers,
                                "accuracy": accuracy
                            }
                        except Exception as e:
                            logger.warning(f"Failed to get latest test details for user {user_id}: {e}")
                            latest_test_details = {
                                "latest_score": result.score,
                                "total_questions": None,
                                "correct_answers": None,
                                "accuracy": None
                            }

            responses = (
                db.query(Response)
                .filter(Response.attempt_id.in_(attempt_ids))
                .all()
            )
        except Exception as e:
            logger.error(f"Dashboard DB query failed for user {user_id}: {e}")
            raise HTTPException(
                status_code=500, 
                detail={
                    "error": "DATABASE_ERROR",
                    "message": "Unable to fetch dashboard data. Please try again later.",
                    "user_friendly": True
                }
            )

        try:
            topic_stats: dict[str, dict] = {}
            for r in responses:
                if not r.topic:
                    continue
                if r.topic not in topic_stats:
                    topic_stats[r.topic] = {"correct": 0, "total": 0, "subject": r.subject}
                topic_stats[r.topic]["total"]   += 1
                topic_stats[r.topic]["correct"] += int(r.is_correct)

            weak_areas = []
            for topic, s in topic_stats.items():
                acc = round((s["correct"] / s["total"]) * 100, 1) if s["total"] else 0.0
                if acc < 60:
                    weak_areas.append(topic)

            latest_score = recent_scores[0] if recent_scores else None
            rank_data = {"rank": None, "percentile": None}
            
            if latest_score is not None:
                try:
                    rank_data = calculate_rank_and_percentile(latest_score, exam, db)
                except Exception as e:
                    logger.warning(f"Failed to calculate rank for user {user_id}: {e}")

            # Calculate overall accuracy for mentor advice
            total_responses = len(responses)
            correct_responses = sum(1 for r in responses if r.is_correct)
            overall_accuracy = (correct_responses / total_responses * 100) if total_responses > 0 else 0

            # Generate 3 random mentor advices with enhanced randomization
            try:
                all_advice = generate_mentor_advice(latest_score or 0, overall_accuracy, weak_areas)
                
                # Extended pool of general advice for better variety
                general_advice = [
                    "Practice regularly to maintain consistency in your performance.",
                    "Focus on understanding concepts rather than memorizing answers.",
                    "Take breaks between study sessions to improve retention.",
                    "Review your mistakes to avoid repeating them in future tests.",
                    "Time management is crucial - practice solving questions within time limits.",
                    "Create a study schedule and stick to it for better preparation.",
                    "Use active recall techniques while studying for better memory retention.",
                    "Solve previous year papers to understand exam patterns.",
                    "Join study groups to discuss difficult concepts with peers.",
                    "Take mock tests regularly to assess your preparation level.",
                    "Focus on your weak subjects but don't neglect your strong ones.",
                    "Maintain a healthy lifestyle with proper sleep and nutrition.",
                    "Use mnemonics and visual aids to remember complex information.",
                    "Practice meditation or relaxation techniques to manage exam stress.",
                    "Set realistic daily and weekly study goals.",
                    "Reward yourself after completing study milestones.",
                    "Keep revision notes handy for quick last-minute reviews.",
                    "Stay updated with current affairs if relevant to your exam.",
                    "Don't compare your progress with others, focus on your own journey.",
                    "Seek help from teachers or mentors when you're stuck on topics."
                ]
                
                # Combine personalized and general advice for larger pool
                combined_advice = list(all_advice) + general_advice
                
                # Shuffle the combined list and pick 3 random unique advices
                random.shuffle(combined_advice)
                random_advice = []
                seen_advice = set()
                
                for advice in combined_advice:
                    if advice not in seen_advice and len(random_advice) < 3:
                        random_advice.append(advice)
                        seen_advice.add(advice)
                    if len(random_advice) == 3:
                        break
                
                # Fallback if somehow we don't have 3 advices (very unlikely)
                while len(random_advice) < 3:
                    fallback_advice = f"Keep practicing and stay motivated! Attempt #{len(random_advice) + 1}"
                    random_advice.append(fallback_advice)
                    
            except Exception as e:
                logger.warning(f"Failed to generate mentor advice for user {user_id}: {e}")
                random_advice = [
                    "Keep practicing regularly to improve your performance.",
                    "Focus on your weak areas and review concepts thoroughly.",
                    "Stay motivated and maintain a consistent study schedule."
                ]

            return {
                "user_id":       user_id,
                "exam":          exam,
                "course_id":     course_id,
                "recent_scores": recent_scores,
                "latest_score": latest_test_details["latest_score"] if latest_test_details else None,
                "total_questions": latest_test_details["total_questions"] if latest_test_details else None,
                "correct_answers": latest_test_details["correct_answers"] if latest_test_details else None,
                "accuracy": latest_test_details["accuracy"] if latest_test_details else None,
                "rank":          rank_data["rank"],
                "percentile":    rank_data["percentile"],
                "weak_areas":    weak_areas,
                "mentor_advice": random_advice,
            }
            
        except Exception as e:
            logger.error(f"Failed to process dashboard data for user {user_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "DATA_PROCESSING_ERROR", 
                    "message": "Unable to process dashboard data. Please try again later.",
                    "user_friendly": True
                }
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise
    except Exception as e:
        logger.error(f"Unexpected error in dashboard for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "user_friendly": True
            }
        )
