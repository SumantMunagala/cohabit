import uuid

from pydantic import BaseModel

from backend.models.questionnaire import QuestionnaireInput


class MatchRequest(BaseModel):
    questionnaire: QuestionnaireInput
    free_text: str


class MatchCandidate(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID


class MatchResponse(BaseModel):
    matches: list[MatchCandidate]
