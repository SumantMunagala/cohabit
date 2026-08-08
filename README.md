# Cohabit

A roommate compatibility tool that skips the survey-matching approach and actually simulates conflict between two people before telling you if they'd get along. Each person's questionnaire and free-text answers get turned into a behavioral persona, and two separate LLM agents play those personas out through six roommate conflict scenarios — noise, guests, cleaning, money. A third agent watches and takes notes, and a judge model scores the outcome across four dimensions with an explanation.

Submit one profile and the app finds your five closest candidates from a pool by embedding similarity, runs all five conflict simulations at the same time, and gives you back a ranked list with real scores.

## How it works

```
Questionnaire + free-text
        │
        ▼
Persona construction (LLM → PersonaObject, Pydantic-validated)
        │
        ▼
Embed persona (Voyage AI, 512-dim) ──► pgvector cosine-similarity search
        │                                over the candidate pool
        ▼
Top 5 candidates
        │
        ▼
5 simulations in parallel (LangGraph, one per candidate)
    Agent A ⇄ Agent B — 6 conflict scenarios, cross-scenario memory
        │ (after each scenario)
    Observer agent — structured notes, tied to actual dialogue
        │ (after all 6 scenarios)
    Verdict — 4-dimension score + summary
        │
        ▼
Ranked results, streamed to the client over WebSocket as they finish
```

Persona A and B are played by two separate agent calls, not one model writing both sides. When a single model generates a whole conversation it tends to smooth both characters toward agreement, since that's what coherent dialogue looks like in its training data. Two independent calls, each only aware of its own persona, don't have that pull — they'll actually hold a dealbreaker instead of writing their way to a tidy resolution.

## Features

- Persona construction that infers behavior from a questionnaire and a short description, rather than just echoing the inputs back
- Personas are embedded and stored in Postgres via `pgvector`, so a new submission gets matched against the pool by cosine similarity before anything expensive runs
- Two independent LangGraph agents argue through six scenarios, with memory carried across all of them via a checkpointer
- A judge model scores four dimensions (lifestyle, communication, conflict resolution, dealbreakers), with a prompt specifically written to avoid every score clustering in the same safe middle band
- All five candidate simulations for a submission run concurrently instead of one after another — this took some digging into how FastAPI's background tasks actually execute, more on that below
- Each simulation streams progress over its own WebSocket as scenarios complete
- LLM provider is swappable through one factory function — Claude for real use, a local Ollama model for cheap bulk testing, no call sites need to change

## Tech stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph, LangChain |
| LLMs | Claude (Anthropic API) or Llama 3.1 (local via Ollama) |
| Embeddings | Voyage AI (`voyage-3-lite`, 512-dim) |
| Backend | FastAPI, Pydantic, SQLAlchemy (async) |
| Database | PostgreSQL + `pgvector` |
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Observability | LangSmith |
| Infra | Docker Compose, Alembic |

## Project structure

```
cohabit/
├── backend/
│   ├── agents/       # persona_construction, agent_a, agent_b, observer, verdict,
│   │                   embeddings, candidate_selection, llm (provider factory)
│   ├── graph/         # LangGraph state, nodes, edges, compiled simulation graph
│   ├── models/        # Pydantic models: questionnaire, persona, observer, verdict, match
│   ├── api/           # FastAPI app + routes (/match endpoints)
│   ├── db/            # SQLAlchemy models (simulations, verdicts, transcripts, users, matches) + session
│   └── tests/         # end-to-end test, local-model comparison, seeding, consistency/latency scripts
├── frontend/
│   └── app/           # Next.js app router — questionnaire form + live ranked results page
├── alembic/           # database migrations
└── docker-compose.yml # PostgreSQL + pgvector
```

## API

| Endpoint | Description |
|---|---|
| `POST /match` | Takes `{questionnaire, free_text}`. Builds and embeds the persona, picks 5 candidates, kicks off 5 simulations in the background, and returns `{matches: [{job_id, candidate_id}, ...]}` right away. |
| `GET /match/{job_id}` | Poll one simulation's status, or get the full verdict once it's done. |
| `GET /match/{job_id}/stream` | WebSocket, one message per completed scenario, then the final verdict. |

## Getting started

### Prerequisites
- Python 3.12+, Node 18+, Docker
- API keys: Anthropic (or a local Ollama install), Voyage AI

### 1. Database
```bash
docker-compose up -d
alembic upgrade head
```

### 2. Backend
```bash
python -m venv venv
venv\Scripts\activate        # Windows; source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env         # fill in DATABASE_URL, ANTHROPIC_API_KEY, VOYAGE_API_KEY, LLM_MODE
uvicorn backend.api.main:app --reload
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`, fill out the form, and the 5 match cards will fill in as their simulations finish.

### Seeding a candidate pool
A fresh database has nobody to match against. This populates it with synthetic users across a few personality archetypes:
```bash
python -m backend.tests.seed_users
```

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (async, `postgresql+asyncpg://...`) |
| `ANTHROPIC_API_KEY` | Claude API access |
| `VOYAGE_API_KEY` | Persona embeddings |
| `LLM_MODE` | `api` (Claude) or `local` (Ollama) |
| `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT` | LangSmith tracing (optional) |

## Some numbers

- Running 5 candidate simulations concurrently rather than one at a time turned out to need more than just calling FastAPI's `add_task()` five times — `BackgroundTasks` awaits its tasks sequentially under the hood, so five separate calls would still run one after another. Fixed by wrapping all five in a single `asyncio.gather()`. With that fix, five real simulations finished within about 100 seconds of each other, instead of the 15-20+ minutes sequential execution would have taken.
- Self-consistency (same two personas, same scenario, run twice) went from 50% to 80% agreement after tracing an inconsistency bug to the persona-generation step rather than the judge — persona construction was inventing different dealbreaker details on every call, not the verdict scoring being flaky.
- p95 simulation latency measured at 127.8s (Haiku, 3 scenarios, 50 runs, 0 outliers).
- A live ranked match came back as 65% / 65% / 50% / 40% / 35% — spread out, not clustered around one number.

## Testing

```bash
python -m backend.tests.test_simulation      # full 6-scenario end-to-end assertion test
python -m backend.tests.measure_consistency  # self-consistency across repeated runs
python -m backend.tests.measure_latency      # p50/p95/max simulation latency
python -m backend.tests.seed_users           # populate the candidate pool
```

No pytest — these are plain scripts with asserts, run directly, matching how the rest of the project is tested.
