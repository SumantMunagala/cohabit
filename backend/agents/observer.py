from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from backend.graph.state import SimulationState
from backend.models.observer import ObserverNotes

load_dotenv()

_model = ChatAnthropic(model="claude-sonnet-5")
_structured_model = _model.with_structured_output(ObserverNotes, method="json_schema")

SYSTEM_PROMPT = (
    "You are a neutral observer analyzing a conversation between two prospective "
    "roommates. You have no persona and are not a participant — your only job is "
    "to evaluate the transcript.\n\n"
    "For every field, you must cite specific evidence: a direct quote or a clear, "
    "concrete paraphrase from the transcript. Do not write vague commentary like "
    "'there was some tension' or 'they mostly agreed' — say what was actually said "
    "and by whom.\n\n"
    "Pay particular attention to each person's stated dealbreakers (given below) "
    "and flag any point in the conversation where one was directly implicated, "
    "even if the two people ultimately resolved it amicably — a dealbreaker being "
    "raised and discussed still counts as a violation worth noting."
)


def _extract_text(message) -> str:
    if isinstance(message.content, str):
        return message.content
    return next(
        (block["text"] for block in message.content if isinstance(block, dict) and block.get("type") == "text"),
        "",
    )


def _build_transcript(state: SimulationState) -> str:
    name_a = state["persona_a"]["name"]
    name_b = state["persona_b"]["name"]
    a_replies = [m for m in state["messages_a"] if isinstance(m, AIMessage)]
    b_replies = [m for m in state["messages_b"] if isinstance(m, AIMessage)]

    lines = []
    if state["messages_a"] and isinstance(state["messages_a"][0], HumanMessage):
        lines.append(f"[Scenario prompt]: {_extract_text(state['messages_a'][0])}")
    for a_msg, b_msg in zip(a_replies, b_replies):
        lines.append(f"{name_a}: {_extract_text(a_msg)}")
        lines.append(f"{name_b}: {_extract_text(b_msg)}")
    return "\n\n".join(lines)


def observer_node(state: SimulationState) -> dict:
    transcript = _build_transcript(state)
    persona_context = (
        f"{state['persona_a']['name']}'s dealbreakers: {', '.join(state['persona_a']['dealbreakers'])}\n"
        f"{state['persona_b']['name']}'s dealbreakers: {', '.join(state['persona_b']['dealbreakers'])}"
    )
    human_message = f"{persona_context}\n\nTranscript:\n{transcript}"

    notes = _structured_model.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human_message)]
    )
    notes = notes.model_copy(update={"scenario_index": state["current_scenario"]})

    return {"observer_notes": state["observer_notes"] + [notes.model_dump()]}
