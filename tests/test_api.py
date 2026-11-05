"""API tests against a temp SQLite DB (configured in the root conftest.py).

The check-now endpoint is tested with ``app.main.check_url`` monkeypatched
to a canned result, so the suite is deterministic and offline.
"""

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["monitors"], int)


def test_list_monitors_starts_empty(client):
    # Runs before any creation test in this module.
    assert client.get("/api/monitors").json() == []


def test_create_monitor_201(client):
    response = client.post(
        "/api/monitors",
        json={"name": "Example", "url": "https://example.com", "interval_seconds": 60},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Example"
    assert body["url"] == "https://example.com"
    assert body["checks_count"] == 0
    assert body["uptime_pct"] is None
    assert body["last_check"] is None


def test_create_monitor_bad_url_scheme_422(client):
    response = client.post(
        "/api/monitors", json={"name": "Bad", "url": "ftp://example.com"}
    )
    assert response.status_code == 422


def test_create_monitor_interval_too_small_422(client):
    response = client.post(
        "/api/monitors",
        json={"name": "Fast", "url": "https://example.com", "interval_seconds": 5},
    )
    assert response.status_code == 422


def test_check_now_and_stats(client, monkeypatch):
    async def fake_check(url: str, timeout: float = 10.0, transport=None) -> dict:
        return {"is_up": True, "status_code": 200, "latency_ms": 42.0, "error": None}

    monkeypatch.setattr(main_module, "check_url", fake_check)

    monitor = client.get("/api/monitors").json()[0]
    response = client.post(f"/api/monitors/{monitor['id']}/check")
    assert response.status_code == 200
    check = response.json()
    assert check["is_up"] is True
    assert check["status_code"] == 200

    history = client.get(f"/api/monitors/{monitor['id']}/checks").json()
    assert len(history) == 1
    assert history[0]["id"] == check["id"]

    stats = client.get("/api/stats").json()
    assert stats["monitors_total"] == 1
    assert stats["monitors_up"] == 1
    assert stats["monitors_down"] == 0
    assert stats["checks_total"] == 1
    assert stats["avg_latency_ms"] == 42.0

    one = client.get(f"/api/monitors/{monitor['id']}").json()
    assert one["uptime_pct"] == 100.0
    assert one["last_check"]["is_up"] is True


def test_metrics_contains_uptime_series(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "uptime_checks_total" in response.text
    assert "uptime_monitors_up" in response.text


def test_dashboard_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "uptime-monitor" in response.text


def test_delete_monitor_then_404(client):
    monitors = client.get("/api/monitors").json()
    monitor_id = monitors[0]["id"]
    assert client.delete(f"/api/monitors/{monitor_id}").status_code == 204
    assert client.get(f"/api/monitors/{monitor_id}").status_code == 404
    assert client.get("/api/monitors").json() == []
