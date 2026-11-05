"""FastAPI application: REST API, Prometheus metrics and the dashboard.

Endpoints
---------
- ``GET    /``                                dashboard (single HTML page)
- ``GET    /health``                          liveness + monitor count
- ``POST   /api/monitors``                    register a monitor (201)
- ``GET    /api/monitors``                    list with status summaries
- ``GET    /api/monitors/{id}``               one monitor
- ``DELETE /api/monitors/{id}``               remove monitor and its checks (204)
- ``GET    /api/monitors/{id}/checks``        check history, newest first
- ``POST   /api/monitors/{id}/check``         run a check right now
- ``GET    /api/stats``                       fleet-wide aggregates
- ``GET    /metrics``                         Prometheus exposition format
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.checker import check_url
from app.db import get_db, init_db
from app.models import Check, Monitor

CHECK_TIMEOUT = float(os.getenv("CHECK_TIMEOUT", "10"))
STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Schemas and serialisation
# ---------------------------------------------------------------------------


class MonitorIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(max_length=2048)
    interval_seconds: int = Field(default=60, ge=10, le=3600)

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value


def check_to_dict(check: Check) -> dict:
    return {
        "id": check.id,
        "monitor_id": check.monitor_id,
        "checked_at": check.checked_at.isoformat() if check.checked_at else None,
        "is_up": check.is_up,
        "status_code": check.status_code,
        "latency_ms": check.latency_ms,
        "error": check.error,
    }


def monitor_to_dict(db: Session, monitor: Monitor) -> dict:
    """Monitor plus the summary fields the dashboard lives on."""
    checks_count = (
        db.query(func.count(Check.id)).filter(Check.monitor_id == monitor.id).scalar() or 0
    )
    up_count = (
        db.query(func.count(Check.id))
        .filter(Check.monitor_id == monitor.id, Check.is_up.is_(True))
        .scalar()
        or 0
    )
    last_check = (
        db.query(Check)
        .filter(Check.monitor_id == monitor.id)
        .order_by(Check.checked_at.desc(), Check.id.desc())
        .first()
    )
    recent = (
        db.query(Check)
        .filter(Check.monitor_id == monitor.id)
        .order_by(Check.checked_at.desc(), Check.id.desc())
        .limit(20)
        .all()
    )
    return {
        "id": monitor.id,
        "name": monitor.name,
        "url": monitor.url,
        "interval_seconds": monitor.interval_seconds,
        "created_at": monitor.created_at.isoformat() if monitor.created_at else None,
        "checks_count": checks_count,
        "uptime_pct": round(100.0 * up_count / checks_count, 1) if checks_count else None,
        "last_check": check_to_dict(last_check) if last_check else None,
        # Oldest -> newest, for the dashboard sparkline.
        "recent_checks": [
            {"is_up": c.is_up, "latency_ms": c.latency_ms} for c in reversed(recent)
        ],
    }


def get_monitor_or_404(db: Session, monitor_id: int) -> Monitor:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="monitor not found")
    return monitor


def fleet_status(db: Session) -> tuple[int, int]:
    """(monitors_up, monitors_down) based on each monitor's latest check."""
    up = down = 0
    for monitor in db.query(Monitor).all():
        last = (
            db.query(Check)
            .filter(Check.monitor_id == monitor.id)
            .order_by(Check.checked_at.desc(), Check.id.desc())
            .first()
        )
        if last is not None:
            if last.is_up:
                up += 1
            else:
                down += 1
    return up, down


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="uptime-monitor", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    return {"status": "ok", "monitors": db.query(func.count(Monitor.id)).scalar() or 0}


@app.post("/api/monitors", status_code=201)
def create_monitor(payload: MonitorIn, db: Session = Depends(get_db)) -> dict:
    monitor = Monitor(
        name=payload.name, url=payload.url, interval_seconds=payload.interval_seconds
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor_to_dict(db, monitor)


@app.get("/api/monitors")
def list_monitors(db: Session = Depends(get_db)) -> list[dict]:
    return [monitor_to_dict(db, m) for m in db.query(Monitor).order_by(Monitor.id).all()]


@app.get("/api/monitors/{monitor_id}")
def get_monitor(monitor_id: int, db: Session = Depends(get_db)) -> dict:
    return monitor_to_dict(db, get_monitor_or_404(db, monitor_id))


@app.delete("/api/monitors/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)) -> Response:
    monitor = get_monitor_or_404(db, monitor_id)
    db.delete(monitor)  # checks are removed by the ORM cascade
    db.commit()
    return Response(status_code=204)


@app.get("/api/monitors/{monitor_id}/checks")
def list_checks(
    monitor_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    get_monitor_or_404(db, monitor_id)
    checks = (
        db.query(Check)
        .filter(Check.monitor_id == monitor_id)
        .order_by(Check.checked_at.desc(), Check.id.desc())
        .limit(limit)
        .all()
    )
    return [check_to_dict(c) for c in checks]


@app.post("/api/monitors/{monitor_id}/check")
async def check_now(monitor_id: int, db: Session = Depends(get_db)) -> dict:
    monitor = get_monitor_or_404(db, monitor_id)
    result = await check_url(monitor.url, timeout=CHECK_TIMEOUT)
    check = Check(monitor_id=monitor.id, **result)
    db.add(check)
    db.commit()
    db.refresh(check)
    return check_to_dict(check)


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    up, down = fleet_status(db)
    avg_latency = db.query(func.avg(Check.latency_ms)).scalar()
    return {
        "monitors_total": db.query(func.count(Monitor.id)).scalar() or 0,
        "monitors_up": up,
        "monitors_down": down,
        "checks_total": db.query(func.count(Check.id)).scalar() or 0,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency is not None else None,
    }


@app.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> Response:
    registry = CollectorRegistry()
    checks_counter = Counter(
        "uptime_checks_total", "Total checks by result", ["result"], registry=registry
    )
    up_count = (
        db.query(func.count(Check.id)).filter(Check.is_up.is_(True)).scalar() or 0
    )
    down_count = (
        db.query(func.count(Check.id)).filter(Check.is_up.is_(False)).scalar() or 0
    )
    checks_counter.labels(result="up").inc(up_count)
    checks_counter.labels(result="down").inc(down_count)
    up, _ = fleet_status(db)
    Gauge(
        "uptime_monitors_up", "Monitors whose latest check is up", registry=registry
    ).set(up)
    return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))
