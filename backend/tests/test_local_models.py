"""Compare local Ollama models (mistral, llama3.1) against the simulation pipeline.

Runs the same two hardcoded, conflicting personas through the full 5-LLM-call-site
pipeline (persona construction x2, agent A, agent B, observer, verdict) once per
local model, swapped in via monkeypatching -- no production files are modified.
Scenarios are capped at 3 (instead of 6) to keep this fast. Structured-output calls
are wrapped with retry + failure logging since local models occasionally return
output that fails schema validation.
"""

import logging
import time

from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama

from backend.agents import agent_a, agent_b, observer, persona_construction, verdict
from backend.graph import edges
from backend.graph.simulation import SCENARIO_PROMPTS, graph
from backend.models.observer import ObserverNotes
from backend.models.persona import PersonaObject
from backend.models.questionnaire import QuestionnaireInput
from backend.models.verdict import VerdictObject

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
MAX_ATTEMPTS = 3  # 1 initial + 2 retries
MODELS = [("mistral", "mistral"), ("llama3.1", "llama3.1"), ("qwen2.5", "qwen2.5")]

PERSONA_A_INPUT = QuestionnaireInput(
    sleep_schedule="9pm-5am, very consistent",
    cleanliness_level=7,
    guests="rarely, prefers a quiet home",
    noise_tolerance=2,
    wfh=True,
    pets=False,
    budget="mid-range, prefers predictable costs",
)
PERSONA_A_FREE_TEXT = (
    "I go to bed at 9pm without exception, every night. I live a quiet, low-key "
    "lifestyle and don't do well with loud noise or a lot of socializing at home "
    "late at night. I'd rather things be settled explicitly upfront than deal "
    "with surprises."
)

PERSONA_B_INPUT = QuestionnaireInput(
    sleep_schedule="2am-10am, night owl",
    cleanliness_level=5,
    guests="frequently, loves hosting",
    noise_tolerance=8,
    wfh=False,
    pets=True,
    budget="flexible, doesn't track spending closely",
)
PERSONA_B_FREE_TEXT = (
    "I'm a very social, high energy person. I love having friends over on "
    "weeknights, sometimes people stay late or crash over. I'm pretty casual "
    "about house rules and assume people will just speak up if something's "
    "bothering them rather than me having to guess."
)


class RetryingStructuredModel:
    """Wraps a structured-output Runnable with retry + failure logging."""

    def __init__(self, structured_model, label: str, stats: dict):
        self._structured_model = structured_model
        self._label = label
        self._stats = stats

    def invoke(self, *args, **kwargs):
        self._stats["calls"] += 1
        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self._structured_model.invoke(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                self._stats["failures"] += 1
                logger.warning(
                    "[%s] structured output attempt %d/%d failed: %s",
                    self._label, attempt, MAX_ATTEMPTS, exc,
                )
                if attempt < MAX_ATTEMPTS:
                    self._stats["retries"] += 1
        raise last_error


def _extract_text(message) -> str:
    if message is None:
        return ""
    if isinstance(message.content, str):
        return message.content
    return next(
        (block["text"] for block in message.content if isinstance(block, dict) and block.get("type") == "text"),
        "",
    )


_ORIGINALS = {
    persona_construction: {"_model": persona_construction._model, "_structured_model": persona_construction._structured_model},
    agent_a: {"_model": agent_a._model},
    agent_b: {"_model": agent_b._model},
    observer: {"_model": observer._model, "_structured_model": observer._structured_model},
    verdict: {"_model": verdict._model, "_structured_model": verdict._structured_model},
}
_ORIGINAL_TOTAL_SCENARIOS = edges.TOTAL_SCENARIOS


def _restore_originals():
    for module, attrs in _ORIGINALS.items():
        for attr, value in attrs.items():
            setattr(module, attr, value)
    edges.TOTAL_SCENARIOS = _ORIGINAL_TOTAL_SCENARIOS


def run_for_model(model_key: str, ollama_model_name: str) -> dict:
    stats = {"calls": 0, "failures": 0, "retries": 0}
    result = {"model": model_key, "error": None, "stats": stats}

    ollama_model = ChatOllama(model=ollama_model_name, base_url=OLLAMA_BASE_URL)

    edges.TOTAL_SCENARIOS = 3
    persona_construction._model = ollama_model
    persona_construction._structured_model = RetryingStructuredModel(
        ollama_model.with_structured_output(PersonaObject, method="json_schema"), f"{model_key}:persona", stats
    )
    agent_a._model = ollama_model
    agent_b._model = ollama_model
    observer._model = ollama_model
    observer._structured_model = RetryingStructuredModel(
        ollama_model.with_structured_output(ObserverNotes, method="json_schema"), f"{model_key}:observer", stats
    )
    verdict._model = ollama_model
    verdict._structured_model = RetryingStructuredModel(
        ollama_model.with_structured_output(VerdictObject, method="json_schema"), f"{model_key}:verdict", stats
    )

    start = time.monotonic()
    try:
        persona_a = persona_construction.construct_persona(PERSONA_A_INPUT, PERSONA_A_FREE_TEXT)
        persona_b = persona_construction.construct_persona(PERSONA_B_INPUT, PERSONA_B_FREE_TEXT)

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
        config = {"configurable": {"thread_id": f"local-eval-{model_key}"}}

        final_state = None
        for state in graph.stream(initial_state, config, stream_mode="values"):
            final_state = state

        sample_a = next((m for m in final_state["messages_a"] if isinstance(m, AIMessage)), None)
        sample_b = next((m for m in final_state["messages_b"] if isinstance(m, AIMessage)), None)
        scenario_1_notes = next((n for n in final_state["observer_notes"] if n["scenario_index"] == 0), None)

        result.update({
            "elapsed": time.monotonic() - start,
            "persona_a": persona_a,
            "persona_b": persona_b,
            "sample_a_name": persona_a.name,
            "sample_a_text": _extract_text(sample_a),
            "sample_b_name": persona_b.name,
            "sample_b_text": _extract_text(sample_b),
            "scenario_1_notes": scenario_1_notes,
            "verdict": final_state["verdict"],
        })
    except Exception as exc:
        result.update({"elapsed": time.monotonic() - start, "error": str(exc)})
        logger.error("[%s] run failed: %s", model_key, exc)
    finally:
        _restore_originals()

    return result


def print_report(results: list[dict]):
    for r in results:
        print("\n" + "=" * 70)
        print(f"MODEL: {r['model']}")
        print("=" * 70)
        print(f"Total time: {r['elapsed']:.1f}s")
        print(f"Structured-output calls: {r['stats']['calls']} | failures: {r['stats']['failures']} | retries: {r['stats']['retries']}")

        if r["error"]:
            print(f"\nRUN FAILED: {r['error']}")
            continue

        print(f"\n{r['sample_a_name']} behavioral_traits:")
        for t in r["persona_a"].behavioral_traits:
            print(f"  - {t}")
        print(f"\n{r['sample_b_name']} behavioral_traits:")
        for t in r["persona_b"].behavioral_traits:
            print(f"  - {t}")

        print("\nSample exchange (scenario 1):")
        print(f"  {r['sample_a_name']}: {r['sample_a_text']}")
        print(f"  {r['sample_b_name']}: {r['sample_b_text']}")

        print("\nScenario 1 observer friction_points:")
        notes = r["scenario_1_notes"]
        if notes:
            for f in notes["friction_points"]:
                print(f"  - {f}")
        else:
            print("  (none captured)")

        print("\nVerdict scores:")
        v = r["verdict"]
        for key in ["lifestyle_score", "communication_score", "conflict_score", "dealbreaker_score"]:
            print(f"  {key}: {v[key]}")

    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)
    header = f"{'model':<12}{'time(s)':<10}{'lifestyle':<11}{'comm':<8}{'conflict':<10}{'dealbreaker':<12}{'struct fails':<14}"
    print(header)
    for r in results:
        if r["error"]:
            print(f"{r['model']:<12}{'FAILED':<10}")
            continue
        v = r["verdict"]
        print(
            f"{r['model']:<12}{r['elapsed']:<10.1f}{v['lifestyle_score']:<11}{v['communication_score']:<8}"
            f"{v['conflict_score']:<10}{v['dealbreaker_score']:<12}{r['stats']['failures']:<14}"
        )


def main():
    results = [run_for_model(model_key, ollama_model_name) for model_key, ollama_model_name in MODELS]
    print_report(results)


if __name__ == "__main__":
    main()
