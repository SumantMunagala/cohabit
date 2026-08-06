from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.agent_a import agent_a_node
from backend.agents.agent_b import agent_b_node
from backend.graph.state import SimulationState

MAX_TURNS = 4


def _extract_text(message) -> str:
    if isinstance(message.content, str):
        return message.content
    return next(
        (block["text"] for block in message.content if isinstance(block, dict) and block.get("type") == "text"),
        "",
    )


def _relay_a_to_b(state: SimulationState) -> dict:
    text = _extract_text(state["messages_a"][-1])
    return {"messages_b": [HumanMessage(content=text)], "turn_count": state["turn_count"] + 1}


def _relay_b_to_a(state: SimulationState) -> dict:
    text = _extract_text(state["messages_b"][-1])
    return {"messages_a": [HumanMessage(content=text)], "turn_count": state["turn_count"] + 1}


def _should_continue(state: SimulationState) -> str:
    return "stop" if state["turn_count"] >= MAX_TURNS else "continue"


builder = StateGraph(SimulationState)
builder.add_node("agent_a", agent_a_node)
builder.add_node("relay_a_to_b", _relay_a_to_b)
builder.add_node("agent_b", agent_b_node)
builder.add_node("relay_b_to_a", _relay_b_to_a)

builder.set_entry_point("agent_a")
builder.add_edge("agent_a", "relay_a_to_b")
builder.add_conditional_edges("relay_a_to_b", _should_continue, {"continue": "agent_b", "stop": END})
builder.add_edge("agent_b", "relay_b_to_a")
builder.add_conditional_edges("relay_b_to_a", _should_continue, {"continue": "agent_a", "stop": END})

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

    initial_state = {
        "persona_a": persona_a.model_dump(),
        "persona_b": persona_b.model_dump(),
        "messages_a": [HumanMessage(content="Just so you know, I usually have a few friends over pretty late on weekends and we hang out until 1 or 2am, sometimes people crash over unannounced. That's just kind of how it's always been for me.")],
        "messages_b": [],
        "current_scenario": 0,
        "observer_notes": [],
        "verdict": None,
        "turn_count": 0,
    }

    result = graph.invoke(initial_state, {"configurable": {"thread_id": "demo-1"}})

    a_replies = [m for m in result["messages_a"] if isinstance(m, AIMessage)]
    b_replies = [m for m in result["messages_b"] if isinstance(m, AIMessage)]

    print(f"Scenario prompt: {result['messages_a'][0].content}\n")
    for a_msg, b_msg in zip(a_replies, b_replies):
        print(f"{persona_a.name}: {_extract_text(a_msg)}\n")
        print(f"{persona_b.name}: {_extract_text(b_msg)}\n")
