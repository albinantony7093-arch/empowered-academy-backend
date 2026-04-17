from pydantic import BaseModel, field_validator
from typing import Dict

class SubmitAnswersRequest(BaseModel):
    test_id: str
    answers: Dict[str, str]   # { "question_id": "selected_option" }

    @field_validator("answers")
    @classmethod
    def answers_not_empty(cls, v):
        if not v:
            raise ValueError("Answers dict must not be empty")
        return v

    @field_validator("test_id")
    @classmethod
    def test_id_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("test_id must not be empty")
        return v
