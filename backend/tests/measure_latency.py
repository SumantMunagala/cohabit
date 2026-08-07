"""Measure p50/p95/max simulation latency (created_at -> completed_at) across
the 50 claude-haiku-4-5-20251001/3-scenario runs from backend/tests/results/test_pairs.json.

The simulations table also holds rows from other configurations (earlier
Phase 4 6-scenario Sonnet verification runs, and the original
measure_consistency.py's pre-redesign runs) with no column distinguishing
model or scenario count -- so this filters to exactly the 50 job_ids in
test_pairs.json rather than querying all completed rows, to avoid blending
incompatible datasets into one meaningless number.

Run from repo root (venv active, Postgres up): python -m backend.tests.measure_latency
"""

import asyncio
import json
import uuid
from pathlib import Path

import numpy as np
from sqlalchemy import select

from backend.db.models import Simulation
from backend.db.session import async_session_factory

TEST_PAIRS_PATH = Path(__file__).parent / "results" / "test_pairs.json"
OUTLIER_MULTIPLIER = 3


async def main() -> None:
    job_ids = [uuid.UUID(p["job_id"]) for p in json.loads(TEST_PAIRS_PATH.read_text())]

    async with async_session_factory() as session:
        result = await session.execute(
            select(Simulation).where(Simulation.id.in_(job_ids), Simulation.status == "completed")
        )
        rows = result.scalars().all()

    durations = [(row.completed_at - row.created_at).total_seconds() for row in rows]

    p50 = np.percentile(durations, 50)
    p95 = np.percentile(durations, 95)
    p_max = max(durations)

    print(f"Run count: {len(durations)}")
    print(f"p50: {p50:.1f}s")
    print(f"p95: {p95:.1f}s")
    print(f"max: {p_max:.1f}s")

    threshold = OUTLIER_MULTIPLIER * p95
    outliers = [row for row, duration in zip(rows, durations) if duration > threshold]
    if outliers:
        print(f"\n{len(outliers)} outlier(s) above {OUTLIER_MULTIPLIER}x p95 ({threshold:.1f}s):")
        for row in outliers:
            duration = (row.completed_at - row.created_at).total_seconds()
            print(f"  job_id={row.id}  duration={duration:.1f}s")
    else:
        print(f"\nNo outliers above {OUTLIER_MULTIPLIER}x p95 ({threshold:.1f}s).")

    print(
        "\nNote: these figures reflect claude-haiku-4-5-20251001 at 3 scenarios, "
        "not a full 6-scenario production run."
    )


if __name__ == "__main__":
    asyncio.run(main())
