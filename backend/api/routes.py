import asyncio
import logging
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from langchain_core.messages import HumanMessage
from sqlalchemy import func, select, update

from backend.agents.persona_construction import construct_persona
from backend.db.models import Simulation, Transcript, Verdict
from backend.db.session import async_session_factory
from backend.graph.simulation import SCENARIO_PROMPTS, graph
from backend.models.match import MatchRequest, MatchResponse
from backend.models.verdict import VerdictObject

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_simulation_async(job_id: uuid.UUID, request: MatchRequest) -> None:
    async with async_session_factory() as session:
        session.add(Simulation(id=job_id, status="running"))
        await session.commit()

    try:
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

        seen_notes = 0
        final_state = initial_state
        async for state in graph.astream(initial_state, config, stream_mode="values"):
            final_state = state
            if len(state["observer_notes"]) > seen_notes:
                seen_notes = len(state["observer_notes"])
                note = state["observer_notes"][-1]
                async with async_session_factory() as session:
                    session.add(
                        Transcript(simulation_id=job_id, scenario_index=note["scenario_index"], content=note)
                    )
                    await session.commit()

        async with async_session_factory() as session:
            session.add(Verdict(simulation_id=job_id, **final_state["verdict"]))
            await session.execute(
                update(Simulation).where(Simulation.id == job_id).values(status="completed", completed_at=func.now())
            )
            await session.commit()

        logger.info("Simulation %s completed", job_id)

    except Exception:
        logger.exception("Simulation %s failed", job_id)
        async with async_session_factory() as session:
            await session.execute(
                update(Simulation).where(Simulation.id == job_id).values(status="failed", completed_at=func.now())
            )
            await session.commit()


def run_simulation(job_id: uuid.UUID, request: MatchRequest) -> None:
    logger.info("Simulation %s started", job_id)
    asyncio.run(_run_simulation_async(job_id, request))


@router.post("/match", response_model=MatchResponse)
def create_match(request: MatchRequest, background_tasks: BackgroundTasks) -> MatchResponse:
    job_id = uuid.uuid4()
    background_tasks.add_task(run_simulation, job_id, request)
    return MatchResponse(job_id=job_id)


@router.get("/match/{job_id}")
async def get_match(job_id: uuid.UUID) -> dict | VerdictObject:
    async with async_session_factory() as session:
        simulation = await session.get(Simulation, job_id)
        if simulation is None:
            raise HTTPException(status_code=404, detail="Simulation not found")

        if simulation.status != "completed":
            return {"status": simulation.status, "job_id": job_id}

        result = await session.execute(select(Verdict).where(Verdict.simulation_id == job_id))
        verdict = result.scalar_one_or_none()
        if verdict is None:
            raise HTTPException(status_code=404, detail="Verdict not found")

        return VerdictObject.model_validate(verdict, from_attributes=True)


@router.websocket("/match/{job_id}/stream")
async def stream_match(websocket: WebSocket, job_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        simulation = await session.get(Simulation, job_id)
    if simulation is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    await websocket.accept()

    last_sent = -1
    try:
        while True:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Transcript)
                    .where(Transcript.simulation_id == job_id, Transcript.scenario_index > last_sent)
                    .order_by(Transcript.scenario_index)
                )
                for transcript in result.scalars():
                    await websocket.send_json(
                        {
                            "type": "scenario_complete",
                            "scenario": transcript.scenario_index,
                            "observer_notes": transcript.content,
                        }
                    )
                    last_sent = transcript.scenario_index

                simulation = await session.get(Simulation, job_id)

            if simulation.status == "completed":
                async with async_session_factory() as session:
                    result = await session.execute(select(Verdict).where(Verdict.simulation_id == job_id))
                    verdict = result.scalar_one_or_none()
                await websocket.send_json(
                    {
                        "type": "complete",
                        "verdict": VerdictObject.model_validate(verdict, from_attributes=True).model_dump(),
                    }
                )
                await websocket.close()
                return

            if simulation.status == "failed":
                await websocket.send_json({"type": "failed", "job_id": str(job_id)})
                await websocket.close()
                return

            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        logger.info("Client disconnected from stream for %s", job_id)
