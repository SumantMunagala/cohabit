import uuid

from fastapi import APIRouter

from backend.models.match import MatchRequest, MatchResponse

router = APIRouter()


@router.post("/match", response_model=MatchResponse)
def create_match(request: MatchRequest) -> MatchResponse:
    job_id = uuid.uuid4()
    return MatchResponse(job_id=job_id)
