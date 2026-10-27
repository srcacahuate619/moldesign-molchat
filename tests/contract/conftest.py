"""Shared live-contract fixtures: reachability probe + per-test bridge.

One bridge per test, closed with its event loop: a shared module-scoped
bridge pools httpx connections on the first test's loop; pytest-asyncio
closes that loop per test and later tests die with ``RuntimeError: Event
loop is closed`` — a harness failure, not a contract verdict (found in the
Fase 1 live run, 2026-10-26).
"""

import httpx
import pytest
import pytest_asyncio

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.config import load_config


def reachability():
    """Probe once: HTTP status, or None when there is no backend.

    Probes an authenticated endpoint: /targets/ answers without a session,
    which would let the suite run halfway unauthenticated and fail on
    per-account endpoints with confusing 401s.
    """
    config = load_config()
    headers = {"Accept": "application/json"}
    if config.moldesign_token:
        headers["Authorization"] = f"Bearer {config.moldesign_token}"
    try:
        response = httpx.get(f"{config.moldesign_base_url.rstrip('/')}/history/evaluations",
                             headers=headers, timeout=5.0, follow_redirects=False)
    except (httpx.RequestError, ValueError):
        return None
    return response.status_code


@pytest_asyncio.fixture
async def bridge():
    status = reachability()
    if status is None:
        pytest.skip("MolDesign inalcanzable; arráncalo para la suite de contrato.")
    if status in (401, 403):
        pytest.skip("Token ausente o rechazado; usa MOLDESIGN_TOKEN de pruebas.")
    async with MolDesignBridge.from_env() as client_bridge:
        yield client_bridge
