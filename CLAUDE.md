# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Git is initialized with a remote (`origin`) and history. The project is still pre-logic in most places, though: the backend package skeleton exists (`backend/agents/`, `backend/graph/`, `backend/models/`, `backend/db/`, `backend/api/`, `backend/tests/`), and most files in it are still empty stubs — the implemented code so far is the health-check endpoint, a `POST /match` endpoint (accepts a `MatchRequest`, returns a `job_id` immediately) in `backend/api/main.py`/`backend/api/routes.py`, the `MatchRequest`/`MatchResponse` models in `backend/models/match.py`, that endpoint kicking off the full LangGraph simulation as a FastAPI `BackgroundTasks` job (`run_simulation()` in `backend/api/routes.py`, logging start/completion via stdlib `logging`), and — as of Phase 4 Task 3 — a real Postgres schema: `backend/db/models.py` (`Simulation`/`Verdict`/`Transcript` SQLAlchemy 2.0 async ORM tables), `backend/db/session.py` (async engine + `async_sessionmaker` factory), and an `alembic/` migration setup (async template) whose first migration is applied and verified live against the docker-compose Postgres. **Nothing in the app writes to these tables yet** — `run_simulation()`'s `graph.invoke()` result is still discarded; only the schema exists (persisting results is a later Phase 4 task). The frontend is an unmodified `create-next-app` scaffold (Next.js 16, React 19, Tailwind 4); `app/page.tsx` is still the default landing page. A Python venv and `requirements.txt` already exist at the repo root. No test suite exists yet despite being referenced below. Do not assume a file has real logic just because it exists — check its contents first. The architecture, stack, and structure described in this file are the intended design to build toward.

**Local environment quirk (this machine only, not project-level):** two native Windows PostgreSQL services (v17 on port 5432, v13 on port 5433) pre-exist outside this project and silently intercept connections meant for the docker-compose Postgres container if it publishes on either of those ports. `docker-compose.yml` therefore publishes on **port 5434** instead of the default 5432 — `DATABASE_URL` in `.env` must match. If `alembic`/the app ever gets a mysterious `InvalidPasswordError` or connects to the wrong database, check `Get-NetTCPConnection -LocalPort <port>` for a port collision before assuming the credentials are wrong.

## Project overview
AI-powered roommate compatibility system. Users complete a questionnaire and free-text description. The system constructs a behavioral persona per user, simulates two personas across multi-turn conflict scenarios using LangGraph agents, and produces a structured compatibility verdict scored across 4 dimensions via an LLM-as-judge observer pattern.

## Stack
- **Languages:** Python, TypeScript
- **Frameworks/libraries:** LangGraph, LangChain, FastAPI, Pydantic, SQLAlchemy, Next.js, React
- **Data/infra:** PostgreSQL, Claude/GPT-4o API
- **Dev tools:** LangSmith, Docker

## Architecture
```
Questionnaire + free-text
        ↓
Persona construction (LLM → PersonaObject)
        ↓
Simulation engine (LangGraph)
    Agent A ↔ Agent B (6 conflict scenarios, cross-scenario memory via checkpointer)
        ↓
Observer agent (silent, structured notes per scenario)
        ↓
Verdict layer (4-dimension score + plain-English summary)
```

Two separate LangGraph agents play Agent A and Agent B (not one agent role-playing both) — a single agent converges toward agreement, so separate agents with separate system prompts are used to produce authentic disagreement. Cross-scenario memory is carried via a LangGraph checkpointer keyed on `thread_id`. **As actually built (corrected from an earlier version of this doc):** the observer runs once per scenario (`observer_node`, Task 7), tagging each note with `scenario_index` and appending to a list — it does not see other scenarios. Cross-scenario synthesis happens one layer later, in the verdict node (Task 9), which reads the full accumulated `observer_notes` list across all scenarios. The original design's reasoning ("cross-scenario patterns are meaningful signal a per-scenario score would miss") still holds — it's just implemented at the verdict stage, not the observer stage.

## Project structure (planned)
```
roomie-match-ai/
├── backend/
│   ├── agents/          # persona_construction, agent_a, agent_b, observer, verdict
│   ├── graph/           # state.py, nodes.py, edges.py, simulation.py
│   ├── models/          # Pydantic models: persona, observer, verdict
│   ├── api/             # FastAPI app and routes
│   ├── db/              # SQLAlchemy models and session
│   └── tests/
├── frontend/
│   ├── app/             # Next.js pages: questionnaire, results
│   └── components/
├── docker-compose.yml
└── .env.example
```

## Key decisions
- **LangGraph over a loop** — StateGraph gives typed state management, checkpointing for cross-scenario memory, and conditional routing
- **Two separate agents** — single agent playing both roles converges; separate agents with separate system prompts produce authentic disagreement
- **Verdict node reads all scenarios together** (not the observer, which runs per-scenario — see Architecture note above) — cross-scenario patterns are meaningful signal a per-scenario score would miss
- **Pydantic at every boundary** — catches malformed LLM output immediately rather than letting bad data propagate
- **Async background tasks** — simulations run 30-90 seconds; synchronous endpoint would time out and block
- **PostgreSQL for transcripts** — enables self-consistency measurement and dealbreaker detection evals after the fact

## Environment variables
```
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=cohabit
DATABASE_URL=
```
Never commit `.env` — only `.env.example` with key names and no values. Add `.env` to `.gitignore` before the first commit. `DATABASE_URL` on this machine is `postgresql+asyncpg://postgres:postgres@localhost:5434/roomie_match` (port 5434, not the Postgres default 5432 — see the port-collision note above).

## Running locally
```bash
# backend (from repo root — requirements.txt and venv/ live at the root, not backend/)
venv\Scripts\activate        # Windows; source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn backend.api.main:app --reload

# frontend
cd frontend
npm install
npm run dev

# database
docker-compose up -d
alembic upgrade head
```
Currently `backend/api/main.py` exposes `GET /` (health check) and, via `backend/api/routes.py`'s `APIRouter`, `POST /match` (accepts a `MatchRequest`, returns a `MatchResponse` with a `job_id` immediately, then runs the full 6-scenario simulation graph as a background task — logs `Simulation <job_id> started`/`completed` to the console, no result persisted anywhere yet). `alembic upgrade head` now runs cleanly and creates `simulations`/`verdicts`/`transcripts` in Postgres (Phase 4 Task 3) — but nothing in the app writes to them yet. There's also no test suite yet — `backend/tests/` only has a `.gitkeep`, and `pytest` isn't in `requirements.txt`.

## Development guidelines
- Explain reasoning before implementing — architectural decisions should be made before writing code
- Build incrementally — smallest working unit first, verify it runs, then expand
- One task per session — finish and commit before moving to the next thing
- Never move forward until the current piece actually runs correctly

## Metrics tracking

Key metrics to record during development and testing. Update this section as numbers come in — these feed directly into resume bullets and interview talking points.

### Simulation scale
- Total simulated user pairs run end-to-end: `3` (Jordan/Riley — Tasks 6, 7, 10, and reused throughout Phase 2/3 verification; Sam/Casey — Task 11; an auto-named pair generated live from `POST /match` request payloads — Phase 4 Task 2 verification, the first pair whose personas were never hardcoded in a script). Note: 3 additional personas (Mara, Jamie, Dana) were generated during the Phase 3 persona-construction audit but never run through the simulation graph — they test `construct_persona()` in isolation, not end-to-end pairs.
- Total simulation runs (including repeats for consistency testing): `10` (2 single-scenario runs in Task 6, 1 in Task 7, 1 three-scenario run in Task 10, 1 full six-scenario run in Task 11, 1 three-scenario rerun for the LangSmith-setup check, 1 three-scenario rerun for the run_name check, 2 single-scenario runs for the Phase 3 agent-consistency controlled test, 1 full six-scenario run in Phase 4 Task 2 — the first run triggered over HTTP via `POST /match` rather than a direct script invocation)
- Total LangSmith traced LLM calls across all runs: `~152` (reconstructed from this session's actual tool calls — see breakdown below; the LangSmith dashboard's own project-level stats are the authoritative source per the measurement note below, this session's build-up is provided as a cross-check)
  - Task 3 (persona construction, incl. the `method="json_schema"` bug fix): 3
  - Task 4 (Agent A): 2
  - Task 5 (Agent B): 1
  - Task 6 (single-scenario demo, run twice): 8
  - Task 7 (observer, chained off a fresh graph run): 5
  - Task 9 (verdict, fixture-based, no live graph run): 1
  - Task 10 (3-scenario full graph): 16
  - Task 11 (6-scenario full graph): 31
  - Post-Task-11 `name=` field verification: 2
  - LangSmith-setup verification (3-scenario rerun): 16
  - `run_name` verification (3-scenario rerun): 16
  - Phase 3 persona-construction audit (3 cases, before the prompt fix): 3
  - Phase 3 persona-construction audit (same 3 cases, after the prompt fix): 3
  - Phase 3 agent-consistency controlled test (2 single-scenario runs): 12
  - Phase 4 Task 2 (background-task wiring verification, 1 full 6-scenario run via `POST /match`, counted directly from server-log `httpx` request lines): 33

### Performance
- p95 verdict delivery time end-to-end (job start → verdict stored): `___s` — still not instrumented against real persistence (no DB write yet — that's a later Phase 4 task), but Phase 4 Task 2 gives the first real wall-clock data point via log timestamps: one full 6-scenario `POST /match` run took `206s` (started 20:36:32, completed 20:39:58) job-start to background-task-completion. Single data point, not a distribution — not enough for a real p95 yet
- Average simulation duration across all runs: `~206s` (single measured data point, Phase 4 Task 2's HTTP-triggered 6-scenario run — the first run with precise start/end timestamps via `logging`, rather than eyeballed). Task 10/11's runs were observed to take multiple minutes each but weren't stopwatched precisely. LangSmith's per-trace latency (e.g. the 191.54s P50/P99 seen for one turn in Task 11's trace) is per-LLM-call, not per full simulation
- Max concurrent simulations handled without degradation: `___` — not tested; every run so far has been sequential, one at a time

### Quality
- Agent self-consistency score (same two personas, same scenario, two runs — verdict similarity): `___%`
- Dealbreaker detection precision before prompt iteration: `___%`
- Dealbreaker detection precision after prompt iteration: `___%`
- Number of prompt iterations to reach final observer prompt: `0` (audited in Phase 3 against 3 concrete criteria — specific quotes vs. vague commentary — and found already solid from the first version; no changes made)
- Number of prompt iterations for persona construction: `1` (Phase 3 audit found inference quality degraded to near-restatement on flat/single-note inputs; added an explicit good-vs-bad example plus contradiction-detection guidance; re-verified improvement on the same 3 test cases)
- Number of prompt iterations for agent system prompts: `1` (Phase 3 added an anti-sycophancy-drift instruction so agents don't cave on dealbreakers just to stay agreeable; verified with a controlled same-pair/same-scenario/twice comparison)

### How to measure each one
**Self-consistency score** — pick 20 persona pairs, run each through the same scenario twice, compare the verdicts side by side. Score as matching if the dominant compatibility outcome and flagged dealbreakers align. `(matching runs / total runs) * 100`

**Dealbreaker detection precision** — manually label 30 simulation transcripts as "dealbreaker present" or "not present." Run the observer output against your labels. `(true positives / (true positives + false positives)) * 100`

**p95 latency** — log `job_start_time` and `verdict_stored_time` for every simulation. Sort all durations, take the 95th percentile value.

**LangSmith call count** — visible in the LangSmith dashboard under project stats after all test runs complete.

## Progress tracking

Update this section at the end of every task and phase. This is the first thing a new Claude Code session reads to understand where the project stands — keep it current.

### Current status
- **Current phase:** Phase 4 — Backend API
- **Current task:** none started yet
- **Last completed task:** Phase 4, Task 3 — PostgreSQL setup. Added `backend/db/models.py` (SQLAlchemy 2.0 async `DeclarativeBase` models: `Simulation`, `Verdict`, `Transcript`, with `UUID(as_uuid=True)` PKs, `DateTime(timezone=True)` timestamps, `Text` for LLM-generated prose fields, `JSONB` for `transcripts.content`, `ondelete="CASCADE"` FKs to `simulations.id`) and `backend/db/session.py` (async engine + `async_sessionmaker` factory, reads `DATABASE_URL` via `os.environ[...]` so misconfiguration fails loudly). Ran `alembic init -t async alembic` (Alembic's purpose-built async-DBAPI template — no hand-written async plumbing needed), pointed `alembic/env.py` at `Base.metadata` and `DATABASE_URL`, autogenerated and applied the first migration. Verified live: all three tables plus `alembic_version` exist in Postgres, `verdicts`' schema matches exactly (checked via `psql \d verdicts`), and `backend/db/session.py`'s own engine can query `information_schema.tables` end-to-end. **No application code writes to these tables yet** (that's Task 4). Also hit and resolved a real infra blocker: two pre-existing native Windows PostgreSQL services (v17 on 5432, v13 on 5433) were silently intercepting all connections meant for the docker-compose container, producing misleading `InvalidPasswordError`s that had nothing to do with credentials — resolved by moving the container to port 5434 (user's choice over stopping either native service) and fixing a stale password left over from the container's Postgres volume having been initialized once before under different credentials.
- **Next task:** Phase 4, Task 4 — Persist simulation results (not yet scoped)

### Phase completion
- [x] Phase 1 — Core simulation in isolation
- [x] Phase 2 — Observability
- [x] Phase 3 — Prompt iteration
- [ ] Phase 4 — Backend API
- [ ] Phase 5 — Frontend
- [ ] Phase 6 — Testing and metrics

### Phase 1 tasks
- [x] Task 1 — Pydantic models
- [x] Task 2 — LangGraph state
- [x] Task 3 — Persona construction function
- [x] Task 4 — Agent A node
- [x] Task 5 — Agent B node
- [x] Task 6 — Single scenario conversation
- [x] Task 7 — Observer node
- [x] Task 8 — Scenario routing
- [x] Task 9 — Verdict node
- [x] Task 10 — Full graph assembly with checkpointer
- [x] Task 11 — End-to-end test with two distinct personas

### Phase 2 tasks
- [x] Task 1 — Langsmith setup
- [x] Task 2 — Name your runs

### Phase 4 tasks
- [x] Task 1 — FastAPI app skeleton
- [x] Task 2 — Background task
- [x] Task 3 — PostgreSQL setup
- [] Task 4 — Persist simulation results
- [] Task 5 — Results endpoint
- [] Task 6 — Websocket streaming


### Decisions log
Record any architectural decisions made during the build that weren't in the original design. Format: decision made, why, any tradeoffs accepted.

| Decision | Reason | Tradeoff |
|----------|--------|----------|
| `with_structured_output(..., method="json_schema")` instead of the default `method="function_calling"` for Claude structured output | Default tool-calling method let Claude return `dealbreakers`/`behavioral_traits` as a single string instead of a list, failing Pydantic validation, even after adding `Field(description=...)` hints | `json_schema` mode is Anthropic-specific structured-output enforcement; if another provider is ever swapped in, this method choice needs revisiting |
| `PersonaObject.name` is invented by the LLM rather than passed in | `construct_persona()`'s signature only takes `questionnaire` + `free_text`, no name field, but `PersonaObject.name` is required | Persona names aren't user-supplied — fine for simulation purposes, would need revisiting if personas are ever shown to end users under a real identity |
| Keep Claude's extended thinking enabled on agent nodes (`agent_a.py` and `agent_b.py`), instead of disabling it | Extended thinking's visible reasoning is wanted later for a frontend dashboard view and for inspecting reasoning quality in LangSmith traces | `AIMessage.content` from `ChatAnthropic` is a list of content blocks (`{"type": "thinking", ...}` + `{"type": "text", ...}`), not a plain string. A text-extraction helper (`_extract_text()`) was needed sooner than predicted — added in `backend/graph/simulation.py` at Task 6, not Task 5/7 as originally guessed, since the relay nodes between the two agents needed plain text before either Agent B or the observer did |
| Added two "relay" nodes (`_relay_a_to_b`, `_relay_b_to_a`) in `backend/graph/simulation.py` between `agent_a_node`/`agent_b_node` in the graph | `agent_a_node`/`agent_b_node` are constrained to only read/write their own `messages_a`/`messages_b` (a hard constraint from Tasks 4-5), so with no glue node between them, Agent B would never see what Agent A said and vice versa — two disconnected monologues instead of a conversation. Routing/conditional-edge functions can't mutate state, so this had to be a node, not edge logic | Two extra hops per turn in the graph; each relay also owns advancing `turn_count`, so turn-counting logic lives outside both agent nodes |
| Added `turn_count: int` to `SimulationState` (`backend/graph/state.py`) | Task 6 needed "stop after N turns" logic; the alternative (deriving turn count from `len(messages_a) + len(messages_b)`) was rejected as fragile — it would silently break if the seeding/relay logic changes and double-counts each turn (one `AIMessage` + one relayed `HumanMessage` per turn) | Reopened an already-completed file (`state.py`) for a field not in the original Task 2 design — same category of change as the `PersonaObject.name`/`Field(description=...)` situation in Task 3 |
| `observer_node()` manually appends to `observer_notes` (`existing + [new_note]`) instead of adding an `operator.add` reducer to `state.py` | `observer_notes` has exactly one writer, unlike `messages_a`/`messages_b` which needed `add_messages`'s ID-based merge logic; a plain reducer would be no more correct than the node managing the full list itself | `state.py` left untouched this task — but this means observer-related state now uses a different accumulation mechanism than the message fields, worth knowing before adding more list-accumulating state fields |
| Applied `with_structured_output(..., method="json_schema")` to `ObserverNotes` from the start, before hitting any failure | `ObserverNotes` has four `list[str]` fields — the exact shape that broke `PersonaObject` under the default `function_calling` method in Task 3 | None — this is the established fix from Task 3, applied proactively rather than rediscovered |
| `ObserverNotes.scenario_index` is force-set via `.model_copy(update={"scenario_index": ...})` after the LLM call, not trusted from the model's structured output | The model has no reliable way to know the true `current_scenario` value, and Task 3 already established the model can't be trusted to reproduce structured fields correctly | None — deterministic override, no downside found |
| Split scenario routing into two functions: `should_continue()` (pure, string-returning) and `increment_scenario_node()` (state-mutating) in `backend/graph/edges.py`, instead of one function doing both | Confirmed directly against LangGraph docs that conditional-edge routing functions cannot update state — only nodes (or `Command`-returning nodes) can. The task's own "done when" also required `should_continue()` to return a plain string, which a `Command`-based single-function design couldn't satisfy | Task 10 must remember to run `increment_scenario_node` immediately before the conditional edge that calls `should_continue`, or the scenario counter never advances and the graph loops forever |
| Corrected a stale claim in this doc's Architecture/Key decisions sections: "observer reads all 6 scenarios together" was never actually true once Task 7 was built to spec (observer runs once per scenario, tagged with `scenario_index`) | Task 9 (verdict node) is what actually reads the full `observer_notes` list across all scenarios — cross-scenario synthesis happens one layer later than the original design doc said | None functionally — the original reasoning (cross-scenario patterns matter) still holds, it's just implemented at the verdict stage; corrected the doc rather than leaving it describing an architecture that was never built |
| `verdict_node()`'s system prompt explicitly names and counteracts LLM score-clustering (instructs full 1-10 range use, reserves 8-10 for unambiguous evidence, maps each of the 4 dimensions to specific evidence categories) | Spec called out a real, well-documented LLM-as-judge failure mode — scores defaulting to a narrow "safe" band regardless of actual variance | Verified against 3 fixture scenarios (smooth / mixed / unresolved-dealbreaker) rather than a live 6-scenario run, to avoid pre-empting Task 11's end-to-end test with ~50+ premature LLM calls |
| Task 10's outer scenario loop (agent_a → agent_b → observer → verdict) runs as **one continuous graph execution with internal loop-back edges**, under a single `thread_id` — not as separate `.invoke()` calls per scenario sharing a `thread_id` | The task spec's own wording had two constraints in tension ("conditional edge → agent_a again" implies one graph run; "each scenario invocation uses the same thread_id" implies separate calls). The literal, detailed graph-topology wording was treated as the stronger signal | **Confirmed with the user** (post-Phase-3 audit) that this is the intended design — the checkpointer's role here is mostly future-proofing (resumability) rather than load-bearing for a single continuous run. No rework needed |
| Added `_start_next_scenario_node` and a `SCENARIO_PROMPTS` list (6 conflict topics) in `simulation.py`, not in the original Task 10 spec | Looping back to `agent_a` with no glue node would leave `turn_count` at its prior value (breaking the inner 4-turn loop after scenario 1) and never introduce a new conflict topic | None — necessary for the outer loop to function at all once more than one scenario runs |
| Renamed `_should_continue` (Task 6, the inner 4-turn-loop check) to `_should_continue_turn` | Task 10 also imports Task 8's `should_continue` (the outer scenario-loop check) into the same file — two identically-named, differently-scoped functions in one module was a real readability hazard | None — internal rename only, not part of any task's "done when" |
| Demo in `simulation.py`'s `__main__` seeds `current_scenario=3` instead of `0` to get a 3-scenario run | Running the full 6 scenarios for this task's own verification would mean ~40+ live LLM calls, duplicating Task 11's explicit job. Reusing `edges.py`'s unmodified `TOTAL_SCENARIOS=6` by starting partway through avoids touching that already-verified file | None — `current_scenario` is just a progress counter, starting it at 3 is functionally identical to starting at 0 with a lower ceiling |
| Progress printed via `graph.stream(..., stream_mode="values")` in the driver code instead of a print-only node baked into the graph | `Workflow.md`'s own guidance treats debug prints as development-time, not committed graph structure | None found |
| Set `name` on messages in `agent_a_node`/`agent_b_node` (own `AIMessage` reply) and the relay nodes (relayed `HumanMessage`) in `simulation.py` | Post-Task-11, LangSmith traces only showed generic `human`/`ai` role labels instead of persona names, making traces harder to read. Confirmed via docs that LangChain messages support a `name` field for exactly this, with a provider-dependent-behavior caveat | Verified live against Anthropic specifically (not assumed from docs) — the field is accepted without error and round-trips correctly through a full relay → next-agent call; `observer_node`/`verdict_node` messages are unaffected since those aren't persona-voiced turns |
| Added `config={"run_name": ...}` to the `.invoke()` call inside each node (`agent_a_scenario_{n}`, `agent_b_scenario_{n}`, `observer_scenario_{n}`, `verdict_synthesis`) — separate and distinct from the message-level `name` field added earlier | "Name your runs" (Phase 2 Task 2) turned out to mean naming the individual LLM-call span, not the message speaker label already handled. The two are genuinely different LangSmith concepts: `run_name` labels a trace span/row; message `name` labels a speaker within message content | Verified live in the trace tree: the graph node name (e.g. `agent_a`, from `add_node`) and the nested `run_name` (`agent_a_scenario_3`) both appear, correctly nested rather than one overwriting the other |
| Strengthened `persona_construction.py`'s `SYSTEM_PROMPT` with an explicit good-vs-bad example pair, guiding questions for behavior-in-conflict, and an instruction to treat free-text contradictions as inference signal | An evidence-based audit (3 diverse `construct_persona()` calls — a flat/single-note input, a socially-open input, a self-contradicting input) found inference quality was inconsistent: strong when the input naturally contained tension, but degraded to near-restatement on flatter inputs (e.g. `"comfortable with high noise levels"` ≈ a direct paraphrase of `noise_tolerance=9`) | Re-ran the same 3 cases after the change: the previously-weak flat-input case improved the most (e.g. `"comfortable with high noise levels"` → `"may genuinely fail to notice when a roommate is bothered, requiring the roommate to speak up first"`), and also fixed an unrelated accuracy issue where `cleanliness_level=3` had been softened to `"moderate"` |
| Added an anti-sycophancy-drift instruction to `agent_a.py`/`agent_b.py`'s `_build_system_prompt()`: do not soften or abandon a stated dealbreaker just because the other party is agreeable or the conversation has gone pleasantly | Targeted a known LLM failure mode (gradually caving to be agreeable over a long back-and-forth) that hadn't been explicitly guarded against, directly relevant to "stay in character under pressure" | Verified with a deliberate controlled test (not an incidental rerun): same pair (Jordan/Riley), same single scenario, seeded identically, run twice independently. All 4 verdict scores landed within 1 point across both runs, the dominant conclusion matched ("workable but fragile, hinges on follow-through" in both), and in both runs Jordan flexed on enforcement mechanics (dropping a hard cutoff for a vibe-based standard) while never abandoning the underlying dealbreaker itself — still 1 pair/1 scenario/2 runs, not the full 20-pair statistical validation `CLAUDE.md`'s Quality metrics describe |
| `run_simulation()` (the `POST /match` background task) lives directly in `backend/api/routes.py` rather than a new `backend/services/` module | The task is small and self-contained (build 2 personas, assemble initial state, invoke the existing compiled `graph`, log twice) — a new module would be premature structure for one function, and no service layer exists yet elsewhere in the codebase | None — may need revisiting once Phase 4 Task 4 (persist simulation results) adds more logic to the same task function |
| `thread_id` for the LangGraph checkpointer is set to `str(job_id)` per request, instead of a hardcoded string (as the `simulation.py` demo uses) | Each `POST /match` call needs isolated checkpointer state under the single shared in-memory `MemorySaver()` instance; reusing one hardcoded thread id across requests would let concurrent runs collide | None found — `job_id` is already a UUID generated per request, so reusing it as the thread key added no new field |
| Introduced stdlib `logging` for the first time in this repo (`logging.basicConfig(...)` in `backend/api/main.py`, `logging.getLogger(__name__)` in `routes.py`), instead of continuing the bare-`print()` convention `simulation.py`'s demo/tests use | Server background-task output needs to show up in `uvicorn`'s log stream with timestamps; `print()` has no level/timestamp/logger-name structure and doesn't compose with `uvicorn`'s own logging | `%(asctime)s` was added to the format string specifically so "log start time"/"log completion time" didn't need manual `datetime` calls in the log messages themselves |
| `Simulation`/`Verdict`/`Transcript` (`backend/db/models.py`) use `UUID(as_uuid=True)` with client-side `default=uuid.uuid4` for all PKs, `DateTime(timezone=True)` (not the implicit naive `datetime` type-map) for timestamps, `Text` (not `String`) for the 5 LLM-generated verdict prose fields, `JSONB` for `transcripts.content`, and `ondelete="CASCADE"` on both simulation FKs | UUID matches the existing `job_id = uuid.uuid4()` pattern and avoids depending on Postgres's `pgcrypto` extension; `DateTime(timezone=True)` avoids silently dropping the tz info that Postgres's `func.now()` (a `timestamptz`) actually returns; `Text` avoids truncation risk on unpredictable-length LLM output; `JSONB` is indexable/queryable, matching CLAUDE.md's stated eval use case; `CASCADE` prevents orphaned audit rows if a simulation is ever deleted | None of these are currently exercised by write paths (Task 4 will be the first real test); `CASCADE` is a DDL-level choice that can be changed via another migration if it ever proves wrong for the audit-trail use case |
| `backend/db/session.py` reads `DATABASE_URL` via `os.environ["DATABASE_URL"]`, not `os.getenv(...)` with a fallback | Fails loudly (`KeyError`) on misconfiguration rather than silently connecting to the wrong database — directly relevant after this task's own debugging saga where a wrong-seeming connection error actually had nothing to do with the DSN itself | None — matches the "fail fast" instinct the port-collision investigation reinforced |
| Used Alembic's `-t async` template (`alembic init -t async alembic`) rather than hand-writing async migration plumbing | Confirmed via Alembic's current docs (context7) that the async template already generates the correct `async_engine_from_config` + `connection.run_sync(...)` + `asyncio.run(...)` boilerplate for async DBAPIs — asyncpg is the only driver installed (no sync psycopg2/psycopg), so this path is mandatory, not optional | `alembic/env.py` still needed a `sys.path.insert(...)` safety net so `from backend.db.models import Base` resolves, since `backend/` has no top-level `__init__.py` (implicit namespace package) and Alembic's `env.py` runs as a standalone script |
| `docker-compose.yml` publishes Postgres on port **5434** instead of the default 5432 | Two pre-existing native Windows PostgreSQL installs on this dev machine (v17 on 5432, v13 on 5433 — confirmed via each install's `postgresql.conf`) silently intercepted all host connections meant for the docker-compose container on either port, producing misleading `InvalidPasswordError`s. Confirmed the real cause by testing auth from *inside* Docker's own network (`docker run --network cohabit_default ... psql -h db`), which succeeded — proving the container/credentials were fine and the failure was purely a Windows host-networking port collision | User explicitly chose remapping the port over stopping either native service, to avoid any risk to whatever those native installs are used for outside this project. This is a per-machine workaround, not a project design choice — a different dev machine wouldn't need it |

### Issues log
Record bugs or problems encountered and how they were resolved. Useful for interviews — being able to talk about what broke and how you fixed it is as valuable as the working system.

| Issue | Root cause | Resolution |
|-------|------------|------------|
| `construct_persona()` raised `pydantic_core.ValidationError` on `dealbreakers`/`behavioral_traits` (`Input should be a valid list`, got a string) | Claude's tool-calling structured-output path doesn't always respect `list[str]` typing in the tool schema — it collapsed multiple items into one combined string. Adding `Field(description=...)` to those fields did not fix it. | Switched `with_structured_output` to `method="json_schema"`, Anthropic's stricter schema-enforced output mode; fixed on first retry |
| `alembic revision --autogenerate` and direct `asyncpg` connections both failed with `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "postgres"`, despite `.env`'s `DATABASE_URL` exactly matching `docker-compose.yml`'s declared `POSTGRES_PASSWORD` | Two separate root causes stacked: (1) the Postgres data volume had been initialized once before (`docker ps` showed the container up for 25+ min prior, logs showed "Skipping initialization" from 2026-08-02) under different credentials — Postgres only applies `POSTGRES_PASSWORD` on first-ever volume init, so the env var was silently ignored on restart; (2) after fixing that via `ALTER ROLE`, the error persisted because two native Windows PostgreSQL services (v17 on port 5432, v13 on port 5433) were intercepting the host's connections before they ever reached the container — confirmed by the complete absence of any corresponding `FATAL`/auth log line in `docker logs`, and confirmed conclusively by successfully authenticating from *inside* Docker's own network (bypassing Windows host networking) with the exact same credentials that failed over the host port | Fixed root cause (1) via `ALTER ROLE postgres WITH PASSWORD 'postgres'` (safe — confirmed the DB had zero tables/data at the time). Fixed root cause (2) by remapping `docker-compose.yml`'s published port to 5434 (first tried 5433, which turned out to itself collide with the second native install — checked port availability via `Get-NetTCPConnection` before landing on 5434) |
