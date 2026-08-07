"""Generate 50 diverse persona pairs and run each through a 3-scenario simulation
using claude-haiku-4-5-20251001, via the real POST /match / GET /match/{job_id} API
(in-process ASGI -- no separate uvicorn process needed), and report total token cost.

Prerequisites:
  - docker-compose Postgres up and migrated: `docker-compose up -d && alembic upgrade head`
  - .env populated with ANTHROPIC_API_KEY, LANGCHAIN_API_KEY,
    LANGCHAIN_TRACING_V2=true, LANGCHAIN_PROJECT

Run from repo root (venv active): python -m backend.tests.generate_test_pairs
"""

import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ["LLM_MODE"] = "api"

from langchain_anthropic import ChatAnthropic

from backend.agents import agent_a, agent_b, observer, persona_construction, verdict
from backend.graph import edges
from backend.models.observer import ObserverNotes
from backend.models.persona import PersonaObject
from backend.models.verdict import VerdictObject

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"
NUM_PAIRS = 50
SCENARIOS_PER_RUN = 3
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 600
MAX_RETRIES_PER_PAIR = 2
INPUT_PRICE_PER_MILLION = 1.0
OUTPUT_PRICE_PER_MILLION = 5.0
RESULTS_PATH = Path(__file__).parent / "results" / "test_pairs.json"

# Matches llm.py's get_llm(temperature=0.2) for persona_construction/verdict --
# those two stages get a low temperature to reduce run-to-run drift in persona
# substance and judge calibration; agent_a/agent_b/observer stay at the
# default temperature so roleplay dialogue keeps natural variation.
PERSONA_VERDICT_TEMPERATURE = 0.2


def _patch_models() -> None:
    """Swap every agent's model to Haiku and cap scenarios at 3, mirroring the
    monkeypatch technique test_local_models.py already uses for Ollama models."""
    haiku = ChatAnthropic(model=HAIKU_MODEL)
    haiku_low_temp = ChatAnthropic(model=HAIKU_MODEL, temperature=PERSONA_VERDICT_TEMPERATURE)
    persona_construction._model = haiku_low_temp
    persona_construction._structured_model = haiku_low_temp.with_structured_output(PersonaObject, method="json_schema")
    agent_a._model = haiku
    agent_b._model = haiku
    observer._model = haiku
    observer._structured_model = haiku.with_structured_output(ObserverNotes, method="json_schema")
    verdict._model = haiku_low_temp
    verdict._structured_model = haiku_low_temp.with_structured_output(VerdictObject, method="json_schema")
    edges.TOTAL_SCENARIOS = SCENARIOS_PER_RUN


_patch_models()

import httpx  # noqa: E402
from langsmith import Client as LangSmithClient  # noqa: E402

from backend.api.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Persona pair generation
# ---------------------------------------------------------------------------

SLEEP_SCHEDULES = {
    "early_bird": "6am-10pm, up with the sun",
    "night_owl": "1am-9am, night owl",
    "flexible": "no fixed schedule, adapts to whatever's going on",
}
GUEST_LEVELS = ["rarely", "occasionally", "often"]
BUDGET_LEVELS = ["low", "medium", "high"]

COMPATIBLE_FREE_TEXT_A = [
    "I keep a steady, predictable routine and like our place to feel calm and put together. "
    "I'm relaxed about small stuff, but I do notice when shared spaces get messy and I'd "
    "rather we just talk about it early.",
    "Home is where I recharge, so I like it quiet and orderly. I'm not rigid about it, but "
    "I do keep to a rhythm and expect the people I live with to respect that most nights.",
    "I'm pretty low-maintenance and get along with almost anyone, as long as we're roughly "
    "on the same page about noise and cleanliness. I'd rather compromise early than let "
    "something fester.",
    "I like having a few close friends over occasionally, nothing wild. Mostly I just want "
    "a place that feels consistent and where nobody is surprised by how the other person lives.",
]
COMPATIBLE_FREE_TEXT_B = [
    "I'm easygoing and adaptable -- I don't need things to be perfect, but I do appreciate "
    "when a place has some order to it. I try to speak up early if something's bothering me "
    "instead of letting it build.",
    "I like a calm, dependable home base. I'm social outside the apartment more than in it, "
    "so I don't bring a ton of chaos home with me.",
    "I get along well with roommates because I try to notice what matters to them and adjust. "
    "I'm not precious about my own habits as long as we're generally aligned.",
    "I value routine and a tidy shared space, though I'm flexible on the details. I'd rather "
    "have an honest conversation upfront than assume things will just work out.",
]
INCOMPATIBLE_FREE_TEXT_STRICT = [
    "I need the apartment spotless and quiet after 9pm -- that's non-negotiable for me. I've "
    "had roommates who didn't take that seriously before and it never worked out long-term.",
    "I'm a light sleeper and very particular about cleanliness -- dishes in the sink overnight "
    "or noise late at night genuinely ruins my week. I'd rather be upfront about that than "
    "pretend it doesn't matter.",
    "I work from home and need real quiet during the day. Guests dropping by unannounced or "
    "a messy kitchen are hard dealbreakers for me, not just preferences.",
    "I keep a strict, early routine and expect the space to reflect that. I don't do well "
    "with unpredictability -- I'd rather live alone than constantly negotiate basic respect "
    "for quiet hours.",
]
INCOMPATIBLE_FREE_TEXT_LOOSE = [
    "I'm very social and the apartment is basically my hangout spot -- people are over most "
    "nights and I don't stress much about mess, it always sorts itself out eventually.",
    "I'm a night owl and pretty loud when I'm having fun with friends at home. I don't really "
    "track cleaning schedules -- I'll get to it when I get to it.",
    "Honestly I like a lived-in space and I don't mind clutter. I have people over a lot and "
    "I assume folks will just tell me directly if something's bugging them.",
    "I run on a late schedule and like spontaneity -- last-minute guests, music, whatever. "
    "I don't do well with a lot of rules around the house.",
]
AMBIGUOUS_FREE_TEXT_A = [
    "I say I'm laid back but I actually get quietly annoyed about noise more than I let on. "
    "I'd rather avoid bringing it up in the moment and just hope it resolves itself.",
    "I'm pretty flexible day to day, though there are a couple of specific things -- like "
    "guests without a heads-up -- that genuinely bother me even if I don't always say so.",
    "I go back and forth between wanting a very social home and needing real quiet to focus. "
    "Depends on the week, honestly.",
    "Mostly easygoing, but I have strong opinions about a couple of specific habits that I "
    "probably haven't been direct enough about with past roommates.",
]
AMBIGUOUS_FREE_TEXT_B = [
    "I think of myself as considerate, but I've been told I don't always notice when I'm "
    "being the noisy one. I do care, I just don't always catch it in the moment.",
    "I'm fine with most things as long as nobody springs a big change on me. I don't love "
    "conflict, so I tend to let small stuff slide until it isn't small anymore.",
    "I like structure most of the time, but I also want to feel like the apartment is still "
    "fun to live in. I haven't fully figured out how to balance the two.",
    "I'd call myself adaptable, though a couple of things -- mess in shared areas mostly -- "
    "get under my skin more than I usually let on upfront.",
]


def _questionnaire(sleep_key: str, clean: int, guests: str, noise: int, wfh: bool, pets: bool, budget: str) -> dict:
    return {
        "sleep_schedule": SLEEP_SCHEDULES[sleep_key],
        "cleanliness_level": clean,
        "guests": guests,
        "noise_tolerance": noise,
        "wfh": wfh,
        "pets": pets,
        "budget": budget,
    }


def _pair_body(q_a: dict, text_a: str, q_b: dict, text_b: str) -> dict:
    return {"questionnaire_a": q_a, "free_text_a": text_a, "questionnaire_b": q_b, "free_text_b": text_b}


def _clamp(value: int) -> int:
    return min(10, max(1, value))


def _compatible_pair(rng: random.Random) -> dict:
    sleep_key = rng.choice(list(SLEEP_SCHEDULES))
    clean = rng.randint(5, 9)
    noise = rng.randint(2, 6)
    guests = rng.choice(GUEST_LEVELS)
    budget = rng.choice(BUDGET_LEVELS)

    q_a = _questionnaire(sleep_key, clean, guests, noise, rng.choice([True, False]), rng.choice([True, False]), budget)
    q_b = _questionnaire(
        sleep_key,
        _clamp(clean + rng.choice([-1, 0, 1])),
        guests,
        _clamp(noise + rng.choice([-1, 0, 1])),
        rng.choice([True, False]),
        rng.choice([True, False]),
        budget,
    )
    return _pair_body(q_a, rng.choice(COMPATIBLE_FREE_TEXT_A), q_b, rng.choice(COMPATIBLE_FREE_TEXT_B))


def _incompatible_pair(rng: random.Random) -> dict:
    clean_a, clean_b = rng.randint(8, 10), rng.randint(1, 3)
    noise_a, noise_b = rng.randint(1, 3), rng.randint(8, 10)
    budget_a, budget_b = rng.choice(BUDGET_LEVELS), rng.choice(BUDGET_LEVELS)

    q_a = _questionnaire("early_bird", clean_a, "rarely", noise_a, True, False, budget_a)
    q_b = _questionnaire("night_owl", clean_b, "often", noise_b, False, True, budget_b)
    return _pair_body(q_a, rng.choice(INCOMPATIBLE_FREE_TEXT_STRICT), q_b, rng.choice(INCOMPATIBLE_FREE_TEXT_LOOSE))


def _ambiguous_pair(rng: random.Random) -> dict:
    sleep_key = rng.choice(list(SLEEP_SCHEDULES))  # aligned axis
    clean_a = rng.randint(1, 10)
    clean_b = rng.randint(1, 10)
    while abs(clean_a - clean_b) < 4:  # conflicting axis
        clean_b = rng.randint(1, 10)
    noise_a = rng.randint(3, 7)
    noise_b = _clamp(noise_a + rng.choice([-1, 0, 1]))
    budget = rng.choice(BUDGET_LEVELS)

    q_a = _questionnaire(sleep_key, clean_a, rng.choice(GUEST_LEVELS), noise_a, rng.choice([True, False]), rng.choice([True, False]), budget)
    q_b = _questionnaire(sleep_key, clean_b, rng.choice(GUEST_LEVELS), noise_b, rng.choice([True, False]), rng.choice([True, False]), budget)
    return _pair_body(q_a, rng.choice(AMBIGUOUS_FREE_TEXT_A), q_b, rng.choice(AMBIGUOUS_FREE_TEXT_B))


def generate_persona_pairs(n: int = NUM_PAIRS, seed: int = 42) -> list[tuple[str, dict]]:
    rng = random.Random(seed)
    n_compatible = round(n * 0.3)
    n_incompatible = round(n * 0.3)
    n_ambiguous = n - n_compatible - n_incompatible

    pairs = (
        [("compatible", _compatible_pair(rng)) for _ in range(n_compatible)]
        + [("incompatible", _incompatible_pair(rng)) for _ in range(n_incompatible)]
        + [("ambiguous", _ambiguous_pair(rng)) for _ in range(n_ambiguous)]
    )
    rng.shuffle(pairs)
    return pairs


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


async def run_pair(client: httpx.AsyncClient, pair_index: int, category: str, body: dict) -> dict:
    last_status: dict = {}
    job_id = None
    timestamp = None

    for attempt in range(1, MAX_RETRIES_PER_PAIR + 2):
        resp = await client.post("/match", json=body)
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        timestamp = datetime.now(timezone.utc).isoformat()

        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            poll_resp = await client.get(f"/match/{job_id}")
            poll_resp.raise_for_status()
            data = poll_resp.json()
            if "status" not in data:
                return {
                    "pair_index": pair_index,
                    "category": category,
                    "job_id": job_id,
                    "timestamp": timestamp,
                    **body,
                    "verdict": data,
                }
            if data["status"] == "failed":
                last_status = data
                break
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        else:
            last_status = {"status": "timeout"}

        remaining = MAX_RETRIES_PER_PAIR + 1 - attempt
        logger.warning(
            "Pair %d attempt %d did not complete (%s)%s",
            pair_index, attempt, last_status, f", retrying ({remaining} left)" if remaining else "",
        )

    logger.error("Pair %d permanently failed after %d attempts", pair_index, MAX_RETRIES_PER_PAIR + 1)
    return {
        "pair_index": pair_index,
        "category": category,
        "job_id": job_id,
        "timestamp": timestamp,
        **body,
        "error": last_status,
    }


def _print_cost_report(run_start_time: datetime) -> None:
    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() != "true":
        print("WARNING: LANGCHAIN_TRACING_V2 is not 'true' -- token/cost totals below will be 0.")

    runs = LangSmithClient().list_runs(
        project_name=os.environ["LANGCHAIN_PROJECT"],
        run_type="llm",
        start_time=run_start_time,
    )
    total_input = 0
    total_output = 0
    for run in runs:
        total_input += run.prompt_tokens or 0
        total_output += run.completion_tokens or 0

    cost = (total_input / 1_000_000) * INPUT_PRICE_PER_MILLION + (total_output / 1_000_000) * OUTPUT_PRICE_PER_MILLION
    print(f"\nTotal input tokens: {total_input}")
    print(f"Total output tokens: {total_output}")
    print(f"Estimated cost ({HAIKU_MODEL} pricing, $1/M in, $5/M out): ${cost:.4f}")


async def main() -> None:
    pairs = generate_persona_pairs()
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    run_start_time = datetime.now(timezone.utc)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        for i, (category, body) in enumerate(pairs):
            result = await run_pair(client, i, category, body)
            results.append(result)
            RESULTS_PATH.write_text(json.dumps(results, indent=2))

            completed = sum(1 for r in results if "verdict" in r)
            print(f"Completed {completed}/{len(pairs)}")

    failed = [r["pair_index"] for r in results if "error" in r]
    if failed:
        print(f"\n{len(failed)} pair(s) permanently failed: {failed}")

    print("\nWaiting for LangSmith traces to flush...")
    await asyncio.sleep(10)
    _print_cost_report(run_start_time)


if __name__ == "__main__":
    asyncio.run(main())
