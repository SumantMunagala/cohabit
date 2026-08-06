from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from backend.graph.state import SimulationState
from backend.models.verdict import VerdictObject

load_dotenv()

_model = ChatAnthropic(model="claude-sonnet-5")
_structured_model = _model.with_structured_output(VerdictObject, method="json_schema")

SYSTEM_PROMPT = (
    "You are synthesizing a roommate-compatibility verdict from an observer's notes "
    "across every conflict scenario two people were simulated through. Score four "
    "independent dimensions, each 1-10:\n"
    "- lifestyle_score: compatibility of daily habits and routines (sleep, cleanliness, "
    "noise, schedules) — ground this in friction_points/tone_shifts about those topics.\n"
    "- communication_score: how disagreements were actually discussed — ground this in "
    "tone_shifts and concessions.\n"
    "- conflict_score: whether conflict, once raised, moved toward resolution or stayed "
    "stuck — ground this in friction_points and concessions together.\n"
    "- dealbreaker_score: driven directly by dealbreaker_violations. A real, unresolved "
    "dealbreaker violation should pull this score low even if the rest of the "
    "conversation was polite.\n\n"
    "LLM compatibility judges have a well-known failure mode: clustering every score "
    "into a safe 6-8 band regardless of actual differences. Do not do this. Use the "
    "full 1-10 range. Reserve 8-10 strictly for dimensions with strong, consistent, "
    "unambiguous evidence of compatibility. Score each dimension independently — do "
    "not anchor all four to one overall gut impression.\n\n"
    "Every explanation must cite specific friction points, dealbreaker violations, "
    "tone shifts, or concessions from the notes — not generic commentary."
)


def _build_notes_summary(observer_notes: list[dict]) -> str:
    blocks = []
    for note in observer_notes:
        blocks.append(
            f"Scenario {note['scenario_index']}:\n"
            f"  Friction points: {'; '.join(note['friction_points']) or 'none'}\n"
            f"  Dealbreaker violations: {'; '.join(note['dealbreaker_violations']) or 'none'}\n"
            f"  Tone shifts: {'; '.join(note['tone_shifts']) or 'none'}\n"
            f"  Concessions: {'; '.join(note['concessions']) or 'none'}"
        )
    return "\n\n".join(blocks)


def verdict_node(state: SimulationState) -> dict:
    notes_summary = _build_notes_summary(state["observer_notes"])
    verdict = _structured_model.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=notes_summary)],
        config={"run_name": "verdict_synthesis"},
    )
    return {"verdict": verdict.model_dump()}
