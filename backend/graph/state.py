from typing import TypedDict
from typing_extensions import Annotated
from langgraph.graph.message import add_messages


class SimulationState(TypedDict):
    persona_a: dict
    persona_b: dict
    messages_a: Annotated[list, add_messages]
    messages_b: Annotated[list, add_messages]
    current_scenario: int
    observer_notes: list[dict]
    verdict: dict | None
    turn_count: int
