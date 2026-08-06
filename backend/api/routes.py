import logging
import uuid

from fastapi import APIRouter, BackgroundTasks
from langchain_core.messages import HumanMessage

from backend.agents.persona_construction import construct_persona
from backend.graph.simulation import SCENARIO_PROMPTS, graph
from backend.models.match import MatchRequest, MatchResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def run_simulation(job_id: uuid.UUID, request: MatchRequest) -> None:
    logger.info("Simulation %s started", job_id)

    persona_a = construct_persona(request.questionnaire_a, request.free_text_a)
    persona_b = construct_persona(request.questionnaire_b, request.free_text_b)

    initial_state = {
        "persona_a": persona_a.model_dump(),
        "persona_b": persona_b.model_dump(),
        "messages_a": [HumanMessage(content=SCENARIO_PROMPTS[0])],
        "messages_b": [],
        "current_scenario": 0,
        "observer_notes": [],
        "verdict": None,
        "turn_count": 0,
    }
    config = {"configurable": {"thread_id": str(job_id)}}

    graph.invoke(initial_state, config)

    logger.info("Simulation %s completed", job_id)


@router.post("/match", response_model=MatchResponse)
def create_match(request: MatchRequest, background_tasks: BackgroundTasks) -> MatchResponse:
    job_id = uuid.uuid4()
    background_tasks.add_task(run_simulation, job_id, request)
    return MatchResponse(job_id=job_id)
