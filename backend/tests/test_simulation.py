from backend.graph.simulation import graph, SCENARIO_PROMPTS
from backend.models.persona import PersonaObject
from langchain_core.messages import HumanMessage
import json


def test_simulation_catches_noise_dealbreaker():
    persona_a = PersonaObject(
        name="Sam", sleep_schedule="9pm-5am, very consistent", cleanliness_level=7,
        conflict_style="direct and early -- states limits upfront rather than waiting for conflict",
        communication_style="straightforward, prefers issues settled explicitly rather than left ambiguous",
        dealbreakers=["late night noise", "frequent overnight guests or parties"],
        behavioral_traits=["goes to bed at 9pm without exception", "low tolerance for guests or socializing at home", "quiet, low-key lifestyle"],
    )
    persona_b = PersonaObject(
        name="Casey", sleep_schedule="2am-10am, night owl", cleanliness_level=5,
        conflict_style="avoids confrontation, assumes people will speak up if something bothers them",
        communication_style="high energy, social, casual about house rules",
        dealbreakers=["being restricted or told when I can have friends over", "roommates who police my social life"],
        behavioral_traits=["hosts parties or has friends over on weeknights", "very high social energy", "up late most nights, active host"],
    )

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

    config = {"configurable": {"thread_id": "test-noise-incompatibility-1"}}
    seen_notes = 0
    final_state = None

    for state in graph.stream(initial_state, config, stream_mode="values"):
        final_state = state
        if len(state["observer_notes"]) > seen_notes:
            seen_notes = len(state["observer_notes"])
            print(f"--- Scenario {state['observer_notes'][-1]['scenario_index']} complete ({seen_notes}/6) ---")

    verdict = final_state["verdict"]
    print("\nFull verdict:")
    print(json.dumps(verdict, indent=2))

    all_dealbreaker_violations = [
        v for note in final_state["observer_notes"] for v in note["dealbreaker_violations"]
    ]

    assert verdict["dealbreaker_score"] < 5, f"expected dealbreaker_score < 5, got {verdict['dealbreaker_score']}"
    assert len(all_dealbreaker_violations) > 0, "expected at least one dealbreaker violation across all scenarios"

    combined_text = (verdict["dealbreaker_explanation"] + " " + verdict["overall_summary"]).lower()
    assert "noise" in combined_text or "sleep" in combined_text, (
        "expected the verdict to reference noise/sleep as the core issue"
    )

    print("\nPASS: dealbreaker_score < 5, dealbreaker violations present, noise/sleep referenced as core issue")


test_simulation_catches_noise_dealbreaker()
