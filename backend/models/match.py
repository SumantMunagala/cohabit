import uuid

from pydantic import BaseModel

from backend.models.questionnaire import QuestionnaireInput


class MatchRequest(BaseModel):
    questionnaire_a: QuestionnaireInput
    free_text_a: str
    questionnaire_b: QuestionnaireInput
    free_text_b: str


class MatchResponse(BaseModel):
    job_id: uuid.UUID
