"""Background worker: probes every monitor that is due for a check.

Run it next to the API:

    python -m app.worker

Every ``WORKER_TICK_SECONDS`` (default 5) the worker looks for monitors
whose latest check is older than their configured interval — or that have
never been checked — and probes them concurrently (capped), storing one
:class:`~app.models.Check` per probe and logging one line per check.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime

from app.checker import check_url
from app.db import SessionLocal, init_db
from app.models import Check, Monitor

TICK_SECONDS = float(os.getenv("WORKER_TICK_SECONDS", "5"))
CHECK_TIMEOUT = float(os.getenv("CHECK_TIMEOUT", "10"))
MAX_CONCURRENCY = 10


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat stored values as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def due_monitors() -> list[tuple[int, str]]:
    """Return (id, url) of monitors due for a check right now."""
    now = datetime.now(UTC)
    due: list[tuple[int, str]] = []
    with SessionLocal() as db:
        for monitor in db.query(Monitor).all():
            last = (
                db.query(Check)
                .filter(Check.monitor_id == monitor.id)
                .order_by(Check.checked_at.desc(), Check.id.desc())
                .first()
            )
            if last is None or (now - _aware(last.checked_at)).total_seconds() >= (
                monitor.interval_seconds
            ):
                due.append((monitor.id, monitor.url))
    return due


async def _run_due(due: list[tuple[int, str]]) -> list[tuple[int, str, dict]]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def probe(monitor_id: int, url: str) -> tuple[int, str, dict]:
        async with semaphore:
            return monitor_id, url, await check_url(url, timeout=CHECK_TIMEOUT)

    return await asyncio.gather(*(probe(mid, url) for mid, url in due))


def run_tick() -> int:
    """Run one scheduling tick; returns how many checks were performed."""
    due = due_monitors()
    if not due:
        return 0
    results = asyncio.run(_run_due(due))
    with SessionLocal() as db:
        for monitor_id, url, result in results:
            db.add(Check(monitor_id=monitor_id, **result))
            status = "UP  " if result["is_up"] else "DOWN"
            detail = (
                f"{result['status_code']} in {result['latency_ms']} ms"
                if result["is_up"] or result["status_code"]
                else result["error"]
            )
            print(f"[{datetime.now(UTC).isoformat(timespec='seconds')}] "
                  f"{status} {url} -> {detail}", flush=True)
        db.commit()
    return len(results)


def main() -> None:
    init_db()
    print(f"uptime-monitor worker started (tick every {TICK_SECONDS:g}s)", flush=True)
    while True:
        try:
            run_tick()
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on transient errors
            print(f"worker tick failed: {exc}", flush=True)
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
