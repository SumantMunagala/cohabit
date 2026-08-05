# Engineering Workflow — RoomieMatch AI

A reference for how to work on this project the way a SWE would at a startup or big tech company. Follow these practices consistently — the git history, branch structure, and working habits are visible to anyone who reviews the repo, including hiring managers.

---

## Git setup

Initialize properly before writing any code:

```bash
git init
git branch -M main
gh repo create roomie-match-ai --private
git add .
git commit -m "chore: initial project scaffold"
git push -u origin main
```

Configure your identity if not already set:

```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

---

## Branch strategy

Never work directly on main. Every task gets its own branch. Main should always be in a working state.

```bash
# start a new task
git checkout -b feat/pydantic-models

# finish the task, merge back
git checkout main
git merge feat/pydantic-models
git branch -d feat/pydantic-models
git push origin main
```

Branch naming convention:
- `feat/` — new functionality (feat/persona-construction-node)
- `fix/` — bug fixes (fix/observer-schema-validation)
- `chore/` — setup, config, dependencies (chore/docker-compose-setup)
- `refactor/` — restructuring existing code without changing behavior

One branch per task. Never let a branch accumulate multiple tasks — it makes the history unreadable and merges messy.

---

## Commit message format

Every commit follows this structure:

```
<type>(<scope>): <what it does>
```

Types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`

Examples:
```
feat(models): add PersonaObject Pydantic model with field validation
feat(graph): implement Agent A node with persona-grounded system prompt
feat(graph): wire full simulation graph with MemorySaver checkpointer
feat(api): add POST /match endpoint with background task
fix(observer): correct ObserverNotes schema to require friction_points field
chore(db): add Alembic migration for simulations table
refactor(api): move simulation task to dedicated service module
test(graph): add self-consistency verification script for persona pairs
docs(claude): update progress tracking after Phase 1 completion
```

Rules:
- Present tense ("add" not "added")
- Lowercase after the colon
- Specific enough that you know what changed without opening the diff
- One logical change per commit — not "did a bunch of stuff"

A readable commit history is something interviewers and hiring managers notice when they look at your repo. It signals that you work methodically.

---

## Environment and dependency management

**Python:**

Use a virtual environment from day one, never install globally:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Update requirements.txt every time you install something new:
```bash
pip freeze > requirements.txt
git add requirements.txt
git commit -m "chore(deps): add langraph and langchain dependencies"
```

**TypeScript:**

Commit `package-lock.json` — this locks exact dependency versions so the project builds identically everywhere.

**Environment variables:**

Never commit `.env`. Only commit `.env.example` with key names and no values:

```
# .env.example
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=
LANGCHAIN_PROJECT=
DATABASE_URL=
```

Add `.env` to `.gitignore` before your first commit — not after.

---

## Claude Code session setup

**Opening every session:**

Start by anchoring Claude Code to where you are. Don't assume it remembers the previous session:

```
We're working on RoomieMatch AI. 

Current state: [what was last completed]
Today's task: [the specific task]

Context: [what already exists that's relevant]
Goal: [the single thing this session produces]
Constraints: [how it should be built]
Done when: [how we verify it works]
```

Claude Code reads CLAUDE.md automatically but this opener removes any ambiguity about what you're building today.

**During the session:**

One task per session. If a task finishes early and the next one is small, you can do two — but complete and commit the first before starting the second. Never have two tasks in progress at once.

**Closing every session:**

Three things must be done before closing:
1. Done-when condition verified — the code actually runs and does what it should
2. CLAUDE.md progress tracking updated — current task, next task, decisions log
3. Clean commit pushed to remote

If any of these aren't done, the session isn't over.

---

## How to prompt Claude Code

**For a new file:**
```
Create backend/models/persona.py

This file defines the PersonaObject Pydantic model with these fields:
- name: str
- sleep_schedule: str  
- cleanliness_level: int (must be 1-10, add a validator)
- conflict_style: str
- dealbreakers: list[str]
- behavioral_traits: list[str]

Don't add anything beyond what's listed here.
```

**For modifying an existing file:**
```
In backend/graph/state.py, add two fields to SimulationState:
- current_scenario: int (default 0)
- verdict: dict (default None)

Don't change anything else in the file.
```

**For understanding a concept before implementing:**
```
Explain how LangGraph checkpointers work. No code yet — 
just the concept, how state is persisted between runs, 
and what thread_id does. I want to understand it before 
we implement it.
```

**For a code review:**
```
Review this function for correctness and edge cases.
Don't rewrite it — flag specific issues and explain 
why each one is a problem.

[paste code]
```

**For debugging (always explain before fixing):**
```
I'm getting this error:
[paste full error]

Relevant code:
[paste code]

I expected [X] but got [Y].
I already tried [Z].

Don't fix it yet — explain what you think is causing it.
```

The debugging prompt is critical. "Explain before fixing" means you understand the root cause, not just the patch. If you can't explain why something broke, you'll hit the same issue again.

---

## Code review before running anything

After Claude Code generates code, read through it before running a single line. Ask yourself:

- Do I understand what every line does?
- Are there edge cases this doesn't handle?
- Does this match the patterns used elsewhere in the project?
- Could I explain this in an interview right now?

For anything that fails those checks, ask Claude Code to explain that specific part before moving on. This is not optional — it's the habit that separates engineers who own their codebase from engineers who maintain code they don't understand.

---

## Testing discipline

Every task that produces a function or node gets a quick verification script before moving on. Not a full test suite — just enough to confirm the done-when condition is actually met.

Structure every verification the same way:

```python
# backend/tests/test_persona_construction.py

from backend.agents.persona_construction import construct_persona
from backend.models.persona import QuestionnaireInput

def test_persona_construction():
    test_input = QuestionnaireInput(
        sleep_schedule="11pm-7am",
        cleanliness_level=7,
        guests="occasionally, weekends only",
        noise_tolerance=4,
        wfh=True,
        pets=False
    )
    
    persona = construct_persona(
        test_input, 
        "I'm laid back but firm on sleep schedule"
    )
    
    assert persona.name is not None
    assert 1 <= persona.cleanliness_level <= 10
    assert len(persona.dealbreakers) > 0
    assert len(persona.behavioral_traits) > 0
    print("PASS:", persona.model_dump())

test_persona_construction()
```

Run it. If it passes, the task is done. If it fails, debug before moving on. Keep all test scripts in `backend/tests/` — by Phase 6 they become the foundation for your metrics measurement.

---

## Debugging workflow

When something breaks, follow this sequence every time:

1. **Read the full error message** — don't just look at the last line. The stack trace usually tells you exactly where and why.
2. **Identify the specific line causing it** — open the file, find the line.
3. **Form a hypothesis** — "I think this is failing because X."
4. **Check your hypothesis** — add a print statement, inspect the variable, verify your assumption.
5. **If stuck after 15-20 minutes** — ask Claude Code: "I think the issue is X because Y — is that right?" Agree on root cause first, then ask for the fix.

Never copy-paste an error into Claude Code and ask it to fix it without doing steps 1-4 yourself. That skips the diagnostic work where most of the learning happens.

---

## File hygiene

- One responsibility per file — a file that does two unrelated things should be two files
- Keep files short — if a file is over 200 lines, consider splitting it
- Delete dead code immediately — don't comment it out and leave it
- No hardcoded values — use environment variables or constants files

---

## Project-specific practices

**After completing any Phase 1 node:** run it directly as a standalone function with a hardcoded input before wiring it into the graph. Verify it works in isolation first.

**After wiring nodes into the graph:** print the full state after every node run during development. Remove the prints before committing.

**During Phase 3 prompt iteration:** keep a running note outside of code of what you changed in each prompt version and what the trace showed afterward. This becomes your interview answer for "how did you iterate on prompt quality."

**LangSmith after every simulation run during Phase 2 and 3:** open the dashboard before looking at terminal output. Read the trace tree first. This builds the habit of using observability tools rather than just reading print statements.

---

## End of phase checklist

Before starting the next phase, verify all of these:

- [ ] All tasks in the phase committed with clean commit messages
- [ ] All branches merged and deleted
- [ ] CLAUDE.md progress tracking updated
- [ ] Decisions log updated with anything non-obvious that came up
- [ ] Issues log updated with any bugs encountered and how they were resolved
- [ ] Four-question interview test passed out loud for the phase as a whole

The four-question test: what does this component do, why is it built this way, what would break if you removed it, what would you do differently at scale. If you can't answer all four fluently, go back and read more before starting the next phase.

---

## What this workflow signals to interviewers

When a hiring manager or interviewer looks at your repo they can see:

- **Branch history** — shows you work in isolated, focused increments
- **Commit messages** — shows you document your work and think in logical units of change
- **File structure** — shows you think about separation of concerns
- **Test files** — shows you verify your work rather than hoping it works
- **CLAUDE.md and WORKFLOW.md** — shows you treat a solo project with the same discipline as a team project

When talking about how you built it in an interview, being able to say "I branched per task, wrote conventional commits, kept a decisions log, and ran self-consistency evals to measure prompt quality" is a qualitatively different answer than "I just built it." It demonstrates engineering process, not just engineering output.