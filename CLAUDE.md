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
- **Current task:** Task 6 — Single scenario conversation
- **Last completed task:** Task 5 — Agent B node (`agent_b_node()` in `backend/agents/agent_b.py`, exact structural mirror of `agent_a_node()` reading `persona_b`/`messages_b`)
- **Next task:** Task 7 — Observer node

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
- [ ] Task 6 — Single scenario conversation
- [ ] Task 7 — Observer node
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
| Keep Claude's extended thinking enabled on agent nodes (`agent_a.py` and future `agent_b.py`), instead of disabling it | Extended thinking's visible reasoning is wanted later for a frontend dashboard view and for inspecting reasoning quality in LangSmith traces | `AIMessage.content` from `ChatAnthropic` is a list of content blocks (`{"type": "thinking", ...}` + `{"type": "text", ...}`), not a plain string. Any node/UI that needs plain reply text (Agent B reading Agent A's history, the observer reading transcripts, a future frontend transcript view) needs a small "extract the text block" helper rather than reading `.content` directly — not yet written, to be added when Task 5 (Agent B) or Task 7 (observer) first needs to consume message text |

### Issues log
Record bugs or problems encountered and how they were resolved. Useful for interviews — being able to talk about what broke and how you fixed it is as valuable as the working system.

| Issue | Root cause | Resolution |
|-------|------------|------------|
| `construct_persona()` raised `pydantic_core.ValidationError` on `dealbreakers`/`behavioral_traits` (`Input should be a valid list`, got a string) | Claude's tool-calling structured-output path doesn't always respect `list[str]` typing in the tool schema — it collapsed multiple items into one combined string. Adding `Field(description=...)` to those fields did not fix it. | Switched `with_structured_output` to `method="json_schema"`, Anthropic's stricter schema-enforced output mode; fixed on first retry |
