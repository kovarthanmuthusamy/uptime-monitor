"""The probe: one HTTP GET that decides whether a site is up.

A site counts as *up* when it answers with a status in [200, 400) after
following redirects. Anything else — an error status or a network-level
failure — is *down*, with the reason kept in the result.
"""

from __future__ import annotations

import time

import httpx

USER_AGENT = "uptime-monitor/0.1 (+https://github.com/kovarthanmuthusamy/uptime-monitor)"


async def check_url(
    url: str,
    timeout: float = 10.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Check ``url`` once and return a result dict.

    Keys: ``is_up`` (bool), ``status_code`` (int | None),
    ``latency_ms`` (float | None), ``error`` (str | None).
    The optional ``transport`` exists so tests can inject an
    ``httpx.MockTransport`` instead of touching the network.
    """
    started = time.perf_counter()
    try:
        # trust_env=False: an uptime probe must hit the target directly,
        # never via HTTP(S)_PROXY from the environment — and a malformed
        # proxy variable must not be able to break the checker.
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
            trust_env=False,
        ) as client:
            response = await client.get(url)
        latency_ms = (time.perf_counter() - started) * 1000
        return {
            "is_up": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "latency_ms": round(latency_ms, 1),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - any probe failure means "down"
        # Network errors, TLS failures, malformed URLs, timeouts: from the
        # monitor's point of view the site simply did not answer properly.
        return {
            "is_up": False,
            "status_code": None,
            "latency_ms": None,
            "error": (str(exc) or exc.__class__.__name__)[:300],
        }
