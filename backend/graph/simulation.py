from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.agent_a import agent_a_node
from backend.agents.agent_b import agent_b_node
from backend.agents.observer import observer_node
from backend.agents.verdict import verdict_node
from backend.graph.edges import increment_scenario_node, should_continue
from backend.graph.state import SimulationState

MAX_TURNS = 4

SCENARIO_PROMPTS = [
    "Just so you know, I usually have a few friends over pretty late on weekends and we hang out until 1 or 2am, sometimes people crash over unannounced. That's just kind of how it's always been for me.",
    "So, how do you want to handle splitting up cleaning? I'll be honest, I'm not great about doing dishes right away.",
    "Rent's due the 1st, right? I might occasionally be a few days late depending on when I get paid, that work?",
    "I love cooking big meals and using a lot of the kitchen space and dishes. Hope that's not going to be an issue.",
    "My partner ends up staying over most nights during the week. That's fine, right?",
    "I like it pretty warm in here, I'll probably have the heat up a lot in the winter. Also want to put up a bunch of art/posters in the common areas.",
]


def _extract_text(message) -> str:
    if isinstance(message.content, str):
        return message.content
    return next(
        (block["text"] for block in message.content if isinstance(block, dict) and block.get("type") == "text"),
        "",
    )


def _relay_a_to_b(state: SimulationState) -> dict:
    text = _extract_text(state["messages_a"][-1])
    name = state["persona_a"]["name"]
    return {"messages_b": [HumanMessage(content=text, name=name)], "turn_count": state["turn_count"] + 1}


def _relay_b_to_a(state: SimulationState) -> dict:
    text = _extract_text(state["messages_b"][-1])
    name = state["persona_b"]["name"]
    return {"messages_a": [HumanMessage(content=text, name=name)], "turn_count": state["turn_count"] + 1}


def _should_continue_turn(state: SimulationState) -> str:
    return "stop" if state["turn_count"] >= MAX_TURNS else "continue"


def _start_next_scenario_node(state: SimulationState) -> dict:
    prompt = SCENARIO_PROMPTS[state["current_scenario"]]
    return {"messages_a": [HumanMessage(content=prompt)], "turn_count": 0}


builder = StateGraph(SimulationState)
builder.add_node("agent_a", agent_a_node)
builder.add_node("relay_a_to_b", _relay_a_to_b)
builder.add_node("agent_b", agent_b_node)
builder.add_node("relay_b_to_a", _relay_b_to_a)
builder.add_node("observer", observer_node)
builder.add_node("increment_scenario", increment_scenario_node)
builder.add_node("start_next_scenario", _start_next_scenario_node)
builder.add_node("verdict", verdict_node)

builder.set_entry_point("agent_a")
builder.add_edge("agent_a", "relay_a_to_b")
builder.add_conditional_edges("relay_a_to_b", _should_continue_turn, {"continue": "agent_b", "stop": "observer"})
builder.add_edge("agent_b", "relay_b_to_a")
builder.add_conditional_edges("relay_b_to_a", _should_continue_turn, {"continue": "agent_a", "stop": "observer"})
builder.add_edge("observer", "increment_scenario")
builder.add_conditional_edges(
    "increment_scenario", should_continue, {"agent_a_node": "start_next_scenario", "verdict_node": "verdict"}
)
builder.add_edge("start_next_scenario", "agent_a")
builder.add_edge("verdict", END)

graph = builder.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    from backend.models.persona import PersonaObject

    persona_a = PersonaObject(
        name="Jordan", sleep_schedule="11pm-7am", cleanliness_level=8,
        conflict_style="avoids confrontation on small things, but direct and firm about sleep",
        communication_style="casual day-to-day, blunt when a boundary is crossed",
        dealbreakers=["loud noise after 10pm", "unannounced overnight guests"],
        behavioral_traits=["keeps a strict sleep schedule", "tidy without being obsessive", "escalates fast on repeat offenses"],
    )
    persona_b = PersonaObject(
        name="Riley", sleep_schedule="1am-9am, flexible", cleanliness_level=4,
        conflict_style="conflict-avoidant, lets things slide, vents indirectly when frustrated",
        communication_style="very social, dislikes rigid rules",
        dealbreakers=["being micromanaged about chores", "roommates who track every little thing"],
        behavioral_traits=["relaxed about mess", "loves having people over", "assumes things sort themselves out"],
    )

    START_SCENARIO = 3  # runs scenarios 3, 4, 5 then verdict -- keeps the demo to 3 scenarios without touching edges.py's TOTAL_SCENARIOS=6
    initial_state = {
        "persona_a": persona_a.model_dump(),
        "persona_b": persona_b.model_dump(),
        "messages_a": [HumanMessage(content=SCENARIO_PROMPTS[START_SCENARIO])],
        "messages_b": [],
        "current_scenario": START_SCENARIO,
        "observer_notes": [],
        "verdict": None,
        "turn_count": 0,
    }

    config = {"configurable": {"thread_id": "demo-full-graph-1"}}
    seen_notes = 0
    final_state = None

    for state in graph.stream(initial_state, config, stream_mode="values"):
        final_state = state
        if len(state["observer_notes"]) > seen_notes:
            seen_notes = len(state["observer_notes"])
            latest_note = state["observer_notes"][-1]
            print(f"\n=== Scenario {latest_note['scenario_index']} complete ===")
            print(f"Observer notes so far: {seen_notes}")
            print(f"Friction points: {latest_note['friction_points']}")
            print(f"Dealbreaker violations: {latest_note['dealbreaker_violations']}")

    print(f"\n=== Final: {seen_notes} scenarios observed ===")
    print("\nVerdict:")
    import json
    print(json.dumps(final_state["verdict"], indent=2))
