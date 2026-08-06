# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Git is initialized with a remote (`origin`) and history. The project is still pre-logic, though: the backend package skeleton exists (`backend/agents/`, `backend/graph/`, `backend/models/`, `backend/db/`, `backend/api/`, `backend/tests/`), but almost every file in it is an empty stub — the only implemented code is a single health-check endpoint in `backend/api/main.py`. The frontend is an unmodified `create-next-app` scaffold (Next.js 16, React 19, Tailwind 4); `app/page.tsx` is still the default landing page. A Python venv and `requirements.txt` already exist at the repo root. No Alembic config/migrations and no test suite exist yet despite both being referenced below. Do not assume a file has real logic just because it exists — check its contents first. The architecture, stack, and structure described in this file are the intended design to build toward.

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
Never commit `.env` — only `.env.example` with key names and no values. Add `.env` to `.gitignore` before the first commit.

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
```
Currently `backend/api/main.py` only exposes `GET /` (health check) — no other routes are wired up. There's no Alembic config or migrations directory yet (`alembic init` hasn't been run), so skip `alembic upgrade head` until that's set up. There's also no test suite yet — `backend/tests/` only has a `.gitkeep`, and `pytest` isn't in `requirements.txt`.

## Development guidelines
- Explain reasoning before implementing — architectural decisions should be made before writing code
- Build incrementally — smallest working unit first, verify it runs, then expand
- One task per session — finish and commit before moving to the next thing
- Never move forward until the current piece actually runs correctly

## Metrics tracking

Key metrics to record during development and testing. Update this section as numbers come in — these feed directly into resume bullets and interview talking points.

### Simulation scale
- Total simulated user pairs run end-to-end: `2` (Jordan/Riley — Tasks 6, 7, 10; Sam/Casey — Task 11)
- Total simulation runs (including repeats for consistency testing): `5` (2 single-scenario runs in Task 6, 1 in Task 7, 1 three-scenario run in Task 10, 1 full six-scenario run in Task 11)
- Total LangSmith traced LLM calls across all runs: `~67` (reconstructed from this session's actual tool calls — see breakdown below; the LangSmith dashboard's own project-level stats are the authoritative source per the measurement note below, this session's build-up is provided as a cross-check)
  - Task 3 (persona construction, incl. the `method="json_schema"` bug fix): 3
  - Task 4 (Agent A): 2
  - Task 5 (Agent B): 1
  - Task 6 (single-scenario demo, run twice): 8
  - Task 7 (observer, chained off a fresh graph run): 5
  - Task 9 (verdict, fixture-based, no live graph run): 1
  - Task 10 (3-scenario full graph): 16
  - Task 11 (6-scenario full graph): 31

### Performance
- p95 verdict delivery time end-to-end (job start → verdict stored): `___s` — not yet instrumented; would need `job_start_time`/`verdict_stored_time` logging as described below, which doesn't exist yet (no persistence layer built — that's Phase 4)
- Average simulation duration across all runs: `___s` — not precisely timed; Task 10/11's runs were observed to take multiple minutes each but weren't stopwatched. LangSmith's per-trace latency (e.g. the 191.54s P50/P99 seen for one turn in Task 11's trace) is per-LLM-call, not per full simulation — the dashboard's thread-level view would have the real end-to-end duration if needed
- Max concurrent simulations handled without degradation: `___` — not tested; every run so far has been sequential, one at a time

### Quality
- Agent self-consistency score (same two personas, same scenario, two runs — verdict similarity): `___%`
- Dealbreaker detection precision before prompt iteration: `___%`
- Dealbreaker detection precision after prompt iteration: `___%`
- Number of prompt iterations to reach final observer prompt: `___`

### How to measure each one
**Self-consistency score** — pick 20 persona pairs, run each through the same scenario twice, compare the verdicts side by side. Score as matching if the dominant compatibility outcome and flagged dealbreakers align. `(matching runs / total runs) * 100`

**Dealbreaker detection precision** — manually label 30 simulation transcripts as "dealbreaker present" or "not present." Run the observer output against your labels. `(true positives / (true positives + false positives)) * 100`

**p95 latency** — log `job_start_time` and `verdict_stored_time` for every simulation. Sort all durations, take the 95th percentile value.

**LangSmith call count** — visible in the LangSmith dashboard under project stats after all test runs complete.

## Progress tracking

Update this section at the end of every task and phase. This is the first thing a new Claude Code session reads to understand where the project stands — keep it current.

### Current status
- **Current phase:** Phase 3 — Prompt iteration
- **Current task:** none started yet
- **Last completed task:** Phase 2 Task 2 — Name your runs (added `config={"run_name": ...}` to the `.invoke()` call inside `agent_a_node`, `agent_b_node`, `observer_node`, `verdict_node`; verified live in the LangSmith trace tree — e.g. `agent_a` the graph node contains a nested `agent_a_scenario_3` LLM-call span, confirming both the graph-node name and the `run_name` show up as distinct, correctly nested labels)
- **Next task:** first task of Phase 3 — Prompt iteration (not yet scoped)

### Phase completion
- [x] Phase 1 — Core simulation in isolation
- [x] Phase 2 — Observability
- [ ] Phase 3 — Prompt iteration
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
| Task 10's outer scenario loop (agent_a → agent_b → observer → verdict) runs as **one continuous graph execution with internal loop-back edges**, under a single `thread_id` — not as separate `.invoke()` calls per scenario sharing a `thread_id` | The task spec's own wording had two constraints in tension ("conditional edge → agent_a again" implies one graph run; "each scenario invocation uses the same thread_id" implies separate calls). The literal, detailed graph-topology wording was treated as the stronger signal | If the intent was actually separate per-scenario invocations relying on the checkpointer to bridge state between them, this is a real design fork requiring a rework of Task 10, not a tweak — flagged to the user, unconfirmed as of this writing |
| Added `_start_next_scenario_node` and a `SCENARIO_PROMPTS` list (6 conflict topics) in `simulation.py`, not in the original Task 10 spec | Looping back to `agent_a` with no glue node would leave `turn_count` at its prior value (breaking the inner 4-turn loop after scenario 1) and never introduce a new conflict topic | None — necessary for the outer loop to function at all once more than one scenario runs |
| Renamed `_should_continue` (Task 6, the inner 4-turn-loop check) to `_should_continue_turn` | Task 10 also imports Task 8's `should_continue` (the outer scenario-loop check) into the same file — two identically-named, differently-scoped functions in one module was a real readability hazard | None — internal rename only, not part of any task's "done when" |
| Demo in `simulation.py`'s `__main__` seeds `current_scenario=3` instead of `0` to get a 3-scenario run | Running the full 6 scenarios for this task's own verification would mean ~40+ live LLM calls, duplicating Task 11's explicit job. Reusing `edges.py`'s unmodified `TOTAL_SCENARIOS=6` by starting partway through avoids touching that already-verified file | None — `current_scenario` is just a progress counter, starting it at 3 is functionally identical to starting at 0 with a lower ceiling |
| Progress printed via `graph.stream(..., stream_mode="values")` in the driver code instead of a print-only node baked into the graph | `Workflow.md`'s own guidance treats debug prints as development-time, not committed graph structure | None found |
| Set `name` on messages in `agent_a_node`/`agent_b_node` (own `AIMessage` reply) and the relay nodes (relayed `HumanMessage`) in `simulation.py` | Post-Task-11, LangSmith traces only showed generic `human`/`ai` role labels instead of persona names, making traces harder to read. Confirmed via docs that LangChain messages support a `name` field for exactly this, with a provider-dependent-behavior caveat | Verified live against Anthropic specifically (not assumed from docs) — the field is accepted without error and round-trips correctly through a full relay → next-agent call; `observer_node`/`verdict_node` messages are unaffected since those aren't persona-voiced turns |
| Added `config={"run_name": ...}` to the `.invoke()` call inside each node (`agent_a_scenario_{n}`, `agent_b_scenario_{n}`, `observer_scenario_{n}`, `verdict_synthesis`) — separate and distinct from the message-level `name` field added earlier | "Name your runs" (Phase 2 Task 2) turned out to mean naming the individual LLM-call span, not the message speaker label already handled. The two are genuinely different LangSmith concepts: `run_name` labels a trace span/row; message `name` labels a speaker within message content | Verified live in the trace tree: the graph node name (e.g. `agent_a`, from `add_node`) and the nested `run_name` (`agent_a_scenario_3`) both appear, correctly nested rather than one overwriting the other |

### Issues log
Record bugs or problems encountered and how they were resolved. Useful for interviews — being able to talk about what broke and how you fixed it is as valuable as the working system.

| Issue | Root cause | Resolution |
|-------|------------|------------|
| `construct_persona()` raised `pydantic_core.ValidationError` on `dealbreakers`/`behavioral_traits` (`Input should be a valid list`, got a string) | Claude's tool-calling structured-output path doesn't always respect `list[str]` typing in the tool schema — it collapsed multiple items into one combined string. Adding `Field(description=...)` to those fields did not fix it. | Switched `with_structured_output` to `method="json_schema"`, Anthropic's stricter schema-enforced output mode; fixed on first retry |
