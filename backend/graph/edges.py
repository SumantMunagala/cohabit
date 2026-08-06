from backend.graph.state import SimulationState

TOTAL_SCENARIOS = 6


def should_continue(state: SimulationState) -> str:
    return "agent_a_node" if state["current_scenario"] < TOTAL_SCENARIOS else "verdict_node"


def increment_scenario_node(state: SimulationState) -> dict:
    return {"current_scenario": state["current_scenario"] + 1}
