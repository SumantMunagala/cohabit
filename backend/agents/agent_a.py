from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage

from backend.graph.state import SimulationState

load_dotenv()

_model = ChatAnthropic(model="claude-sonnet-5")


def _build_system_prompt(persona: dict) -> str:
    return (
        f"You are {persona['name']}, in an in-person conversation with a potential "
        "roommate about how you'd share a living space. Stay in character.\n\n"
        f"Your conflict style: {persona['conflict_style']}\n"
        f"Your behavioral traits: {', '.join(persona['behavioral_traits'])}\n"
        f"Your dealbreakers: {', '.join(persona['dealbreakers'])}\n\n"
        "Respond the way this person actually would — do not break character or "
        "acknowledge you are an AI.\n\n"
        "Do not soften or abandon a stated dealbreaker just because the other "
        "person is being agreeable, apologetic, or because the conversation has "
        "gone on pleasantly. If something genuinely crosses one of your "
        "dealbreakers, hold your position even if it creates friction — do not "
        "cave just to keep things smooth or likable."
    )


def agent_a_node(state: SimulationState) -> dict:
    system_prompt = _build_system_prompt(state["persona_a"])
    messages = [SystemMessage(content=system_prompt), *state["messages_a"]]
    response = _model.invoke(
        messages, config={"run_name": f"agent_a_scenario_{state['current_scenario']}"}
    )
    response = response.model_copy(update={"name": state["persona_a"]["name"]})
    return {"messages_a": [response]}
