import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.security import verify_token
from app.core.config import settings
import openai

logger = logging.getLogger(__name__)
router = APIRouter()

def _get_openai_key() -> str | None:
    """Re-read at call time so a missing key doesn't crash the whole app."""
    key = settings.OPENAI_API_KEY
    if not key or key.startswith("sk-your") or key.startswith("sk-test"):
        return None
    return key

class MentorRequest(BaseModel):
    topic: str

@router.post("/mentor")
def ai_mentor(payload: MentorRequest, user_id: str = Depends(verify_token)):
    if not payload.topic or not payload.topic.strip():
        raise HTTPException(status_code=400, detail="Topic must not be empty")

    # Graceful fallback — AI is optional, must never block the test flow
    api_key = _get_openai_key()
    if not api_key:
        logger.warning("OPENAI_API_KEY not configured — AI mentor unavailable")
        return {"response": None, "message": "AI mentor is not configured yet. Contact support."}

    try:
        openai.api_key = api_key
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "user",
                "content": f"Explain '{payload.topic}' clearly for a NEET student preparing for exams."
            }],
            max_tokens=800,
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        logger.error(f"OpenAI call failed for user {user_id}: {e}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")
