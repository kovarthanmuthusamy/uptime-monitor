#!/usr/bin/env python3
"""Seed the demo data: three monitors, each checked once immediately.

- GitHub        https://github.com          (expected UP)
- TU Dortmund   https://www.tu-dortmund.de  (expected UP)
- Dead example  http://127.0.0.1:9          (connection refused -> DOWN)

Usage:  python scripts/run_demo_seed.py
Uses the configured DATABASE_URL (SQLite file by default).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.checker import check_url
from app.db import SessionLocal, init_db
from app.models import Check, Monitor

SEED = [
    ("GitHub", "https://github.com", 60),
    ("TU Dortmund", "https://www.tu-dortmund.de", 60),
    ("Dead example", "http://127.0.0.1:9", 60),
]


async def main() -> None:
    init_db()
    with SessionLocal() as db:
        monitors = []
        for name, url, interval in SEED:
            monitor = db.query(Monitor).filter(Monitor.url == url).first()
            if monitor is None:
                monitor = Monitor(name=name, url=url, interval_seconds=interval)
                db.add(monitor)
                db.commit()
                db.refresh(monitor)
                print(f"created monitor #{monitor.id}: {name} ({url})")
            monitors.append(monitor)

        results = await asyncio.gather(*(check_url(m.url) for m in monitors))
        for monitor, result in zip(monitors, results, strict=True):
            db.add(Check(monitor_id=monitor.id, **result))
            state = "UP" if result["is_up"] else "DOWN"
            print(f"checked {monitor.name}: {state} "
                  f"(status={result['status_code']}, latency={result['latency_ms']} ms, "
                  f"error={result['error']})")
        db.commit()
    print("seed complete — start the API and open http://localhost:8000")


if __name__ == "__main__":
    asyncio.run(main())
