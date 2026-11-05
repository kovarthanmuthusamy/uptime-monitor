"""Checker tests — all traffic goes through httpx.MockTransport (no network).

The async checker is driven with ``asyncio.run`` so the suite needs no
pytest-asyncio plugin.
"""

import asyncio

import httpx

from app.checker import check_url


def run_check(url: str, handler) -> dict:
    return asyncio.run(check_url(url, transport=httpx.MockTransport(handler)))


def test_200_is_up_with_latency():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    result = run_check("https://example.com", handler)
    assert result["is_up"] is True
    assert result["status_code"] == 200
    assert result["latency_ms"] is not None and result["latency_ms"] >= 0
    assert result["error"] is None


def test_500_is_down_with_status_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    result = run_check("https://example.com", handler)
    assert result["is_up"] is False
    assert result["status_code"] == 500
    assert result["error"] is None


def test_connection_error_is_down_with_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    result = run_check("http://127.0.0.1:9", handler)
    assert result["is_up"] is False
    assert result["status_code"] is None
    assert result["latency_ms"] is None
    assert result["error"]


def test_redirect_is_followed_and_up():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, text="landed")

    result = run_check("https://example.com/old", handler)
    assert result["is_up"] is True
    assert result["status_code"] == 200
