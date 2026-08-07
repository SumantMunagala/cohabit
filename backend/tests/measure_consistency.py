"""Measure agent self-consistency with persona identity HELD FIXED across both
runs: construct each pair's PersonaObjects once, then invoke the simulation
graph directly twice (different thread_id per run), varying only the
conversation and verdict. This isolates conversation+verdict variance from
persona-construction variance, matching this project's original "same two
personas, two runs" metric definition (CLAUDE.md's Quality metrics section).

An earlier version of this script resubmitted through POST /match for run 2,
which re-derives personas from scratch each time. Comparing actual observer
notes for the worst-swinging pairs showed persona_construction() inventing a
different name *and* meaningfully different dealbreaker substance on every
call given the same questionnaire/free_text -- e.g. one run's persona had a
dishes dealbreaker that simply never existed in the other run. That's a
bigger variance source than verdict-judge miscalibration, so it's controlled
for here by constructing personas once and reusing them for both runs.

Uses claude-haiku-4-5-20251001 at 3 scenarios. persona_construction/verdict
run at temperature=0.2 (backend/agents/llm.py's get_llm(temperature=...),
mirrored in generate_test_pairs.py's _patch_models()) to reduce run-to-run
drift; agent_a/agent_b/observer stay at default temperature so roleplay
dialogue keeps natural variation.

No Postgres needed -- this drives the graph directly, not POST /match.

Run from repo root (venv active): python -m backend.tests.measure_consistency
"""

import asyncio
import json
import logging
from pathlib import Path

# Importing this triggers its module-level _patch_models() side effect --
# swaps persona_construction/agent_a/agent_b/observer/verdict to Haiku (with
# the persona/verdict temperature split) and sets edges.TOTAL_SCENARIOS = 3.
from backend.tests import generate_test_pairs  # noqa: F401

from langchain_core.messages import HumanMessage

from backend.agents.persona_construction import construct_persona
from backend.graph.simulation import SCENARIO_PROMPTS, graph
from backend.models.questionnaire import QuestionnaireInput

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NUM_PAIRS = 20
MAX_RETRIES_PER_RUN = 2
TEST_PAIRS_PATH = Path(__file__).parent / "results" / "test_pairs.json"
CONSISTENCY_RUNS_PATH = Path(__file__).parent / "results" / "consistency_runs.json"

DIMENSIONS = {
    "lifestyle_score": "lifestyle",
    "communication_score": "communication",
    "conflict_score": "conflict",
    "dealbreaker_score": "dealbreaker",
}


def dominant_outcome(verdict: dict) -> str:
    mean = sum(verdict[k] for k in DIMENSIONS) / 4
    if mean <= 4:
        return "low"
    if mean >= 8:
        return "high"
    return "medium"


def problematic_dimensions(verdict: dict) -> frozenset:
    min_score = min(verdict[k] for k in DIMENSIONS)
    return frozenset(name for key, name in DIMENSIONS.items() if verdict[key] == min_score)


async def run_scenario_once(persona_a: dict, persona_b: dict, thread_id: str) -> dict:
    initial_state = {
        "persona_a": persona_a,
        "persona_b": persona_b,
        "messages_a": [HumanMessage(content=SCENARIO_PROMPTS[0])],
        "messages_b": [],
        "current_scenario": 0,
        "observer_notes": [],
        "verdict": None,
        "turn_count": 0,
    }
    config = {"configurable": {"thread_id": thread_id}}
    final_state = initial_state
    async for state in graph.astream(initial_state, config, stream_mode="values"):
        final_state = state
    return final_state["verdict"]


async def run_scenario_with_retry(persona_a: dict, persona_b: dict, thread_id: str) -> dict:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES_PER_RUN + 2):
        try:
            return await run_scenario_once(persona_a, persona_b, thread_id)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("Run %s attempt %d failed: %s", thread_id, attempt, exc)
    raise last_exc


async def run_pair_fixed_personas(pair: dict) -> dict | None:
    idx = pair["pair_index"]
    persona_a = construct_persona(
        QuestionnaireInput(**pair["questionnaire_a"]), pair["free_text_a"]
    ).model_dump()
    persona_b = construct_persona(
        QuestionnaireInput(**pair["questionnaire_b"]), pair["free_text_b"]
    ).model_dump()

    try:
        verdict_1 = await run_scenario_with_retry(persona_a, persona_b, f"consistency-{idx}-run1")
        verdict_2 = await run_scenario_with_retry(persona_a, persona_b, f"consistency-{idx}-run2")
    except Exception:
        logger.error("Pair %d permanently failed", idx)
        return None

    return {
        "pair_index": idx,
        "category": pair["category"],
        "persona_a": persona_a,
        "persona_b": persona_b,
        "verdict_1": verdict_1,
        "verdict_2": verdict_2,
    }


def _print_side_by_side(result: dict) -> None:
    v1, v2 = result["verdict_1"], result["verdict_2"]
    print(f"\nPair {result['pair_index']} ({result['category']}):")
    for key in DIMENSIONS:
        print(f"  {key}: run1={v1[key]}  run2={v2[key]}")
    print(f"  dominant_outcome: run1={dominant_outcome(v1)}  run2={dominant_outcome(v2)}")
    print(
        f"  problematic_dimensions: run1={sorted(problematic_dimensions(v1))}  "
        f"run2={sorted(problematic_dimensions(v2))}"
    )


def score_consistency(results: list[dict]) -> None:
    consistent = 0
    inconsistent = []
    for r in results:
        v1, v2 = r["verdict_1"], r["verdict_2"]
        is_consistent = (
            dominant_outcome(v1) == dominant_outcome(v2)
            and problematic_dimensions(v1) == problematic_dimensions(v2)
        )
        if is_consistent:
            consistent += 1
        else:
            inconsistent.append(r)

    total = len(results)
    score = (consistent / total * 100) if total else 0.0
    print(f"\nSelf-consistency score: {score:.1f}% ({consistent}/{total} pairs)")

    if inconsistent:
        print(f"\n{len(inconsistent)} inconsistent pair(s), side by side for review:")
        for r in inconsistent:
            _print_side_by_side(r)
    else:
        print("\nNo inconsistent pairs.")


async def main() -> None:
    all_pairs = json.loads(TEST_PAIRS_PATH.read_text())
    pairs = sorted(all_pairs, key=lambda p: p["pair_index"])[:NUM_PAIRS]

    results: list[dict] = []
    for i, pair in enumerate(pairs):
        result = await run_pair_fixed_personas(pair)
        if result is not None:
            results.append(result)
            CONSISTENCY_RUNS_PATH.write_text(json.dumps(results, indent=2))
        print(f"Pair {pair['pair_index']} complete ({i + 1}/{len(pairs)})")

    skipped = len(pairs) - len(results)
    if skipped:
        print(f"\n{skipped} pair(s) skipped due to permanent failure")

    score_consistency(results)


if __name__ == "__main__":
    asyncio.run(main())
