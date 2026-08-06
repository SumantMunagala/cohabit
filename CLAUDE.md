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

Two separate LangGraph agents play Agent A and Agent B (not one agent role-playing both) — a single agent converges toward agreement, so separate agents with separate system prompts are used to produce authentic disagreement. Cross-scenario memory is carried via a LangGraph checkpointer keyed on `thread_id`, and the observer reads all 6 scenarios together (not per-scenario) since cross-scenario patterns are meaningful signal a per-scenario score would miss.

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
- **Observer reads all scenarios** — cross-scenario patterns are meaningful signal a per-scenario score would miss
- **Pydantic at every boundary** — catches malformed LLM output immediately rather than letting bad data propagate
- **Async background tasks** — simulations run 30-90 seconds; synchronous endpoint would time out and block
- **PostgreSQL for transcripts** — enables self-consistency measurement and dealbreaker detection evals after the fact

## Environment variables
```
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=roomie-match-ai
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
- Total simulated user pairs run end-to-end: `___`
- Total simulation runs (including repeats for consistency testing): `___`
- Total LangSmith traced LLM calls across all runs: `___`

### Performance
- p95 verdict delivery time end-to-end (job start → verdict stored): `___s`
- Average simulation duration across all runs: `___s`
- Max concurrent simulations handled without degradation: `___`

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
- **Current phase:** Phase 1 — Core simulation in isolation
- **Current task:** Task 8 — Scenario routing
- **Last completed task:** Task 7 — Observer node (`observer_node()` in `backend/agents/observer.py`, `with_structured_output(ObserverNotes, method="json_schema")`, manual append to `observer_notes` since that field has no reducer, `scenario_index` force-set from state rather than trusted from the model)
- **Next task:** Task 9 — Verdict node

### Phase completion
- [ ] Phase 1 — Core simulation in isolation
- [ ] Phase 2 — Observability
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
- [ ] Task 8 — Scenario routing
- [ ] Task 9 — Verdict node
- [ ] Task 10 — Full graph assembly with checkpointer
- [ ] Task 11 — End-to-end test with two distinct personas

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

### Issues log
Record bugs or problems encountered and how they were resolved. Useful for interviews — being able to talk about what broke and how you fixed it is as valuable as the working system.

| Issue | Root cause | Resolution |
|-------|------------|------------|
| `construct_persona()` raised `pydantic_core.ValidationError` on `dealbreakers`/`behavioral_traits` (`Input should be a valid list`, got a string) | Claude's tool-calling structured-output path doesn't always respect `list[str]` typing in the tool schema — it collapsed multiple items into one combined string. Adding `Field(description=...)` to those fields did not fix it. | Switched `with_structured_output` to `method="json_schema"`, Anthropic's stricter schema-enforced output mode; fixed on first retry |
