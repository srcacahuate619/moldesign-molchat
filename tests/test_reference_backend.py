"""The public example exercises the same kit over an actual local HTTP server."""

import asyncio
import importlib
import threading
from pathlib import Path

import pytest

from conformance import runner
from examples.reference_backend.server import ReferenceServer
from molchat_agent.tools import catalog as registered_catalog

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.asyncio
async def test_reference_passes_offline_and_live(monkeypatch):
    # Keep this optional pack from changing other tests' catalog.
    catalog_module = importlib.import_module("molchat_agent.tools.catalog")
    monkeypatch.setattr(catalog_module, "_REGISTRY", registered_catalog())
    reference = importlib.import_module("molchat_agent.tools.reference")
    importlib.reload(reference)
    server = ReferenceServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        verdicts = await runner.run(
            ROOT / "examples/reference_backend/cases", live=True,
            base_url=f"http://127.0.0.1:{server.server_port}",
            token="example-session", allow_remote=False, require_contract=False)
        assert not [v for v in verdicts if v.status == "fail"]
        assert all(any(v.check == check and v.status == "pass" for v in verdicts)
                   for check in ("1b", "3b", "5b"))
        assert server.count == 0
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        thread.join()


@pytest.mark.asyncio
async def test_live_read_failure_does_not_pass_as_no_mutation(monkeypatch):
    catalog_module = importlib.import_module("molchat_agent.tools.catalog")
    monkeypatch.setattr(catalog_module, "_REGISTRY", registered_catalog())
    reference = importlib.import_module("molchat_agent.tools.reference")
    importlib.reload(reference)
    class FailedBridge:
        async def call(self, capability, args, **kwargs):
            if capability == "reference_count":
                return {"count": 0}
            raise runner.BridgeError("backend failed")

    packs = [runner.Pack(name="example", capabilities=[
        {"name": "reference_status", "valid_args": {"record_id": "example-1"},
         "live_read": True}])]
    result = await runner.check_reads_no_mutation_live(
        packs, FailedBridge(), {"capability": "reference_count"})
    assert result[0].status == "fail"


@pytest.mark.asyncio
async def test_live_read_blocked_counts_as_read_not_as_failure(monkeypatch):
    """A blocked read (preflight blockers are data) keeps 3b on its purpose:
    no mutation. Measured live against MolDesign, check_preflight blocks on a
    fresh catalog and the runner must not call that a conformance failure."""
    catalog_module = importlib.import_module("molchat_agent.tools.catalog")
    monkeypatch.setattr(catalog_module, "_REGISTRY", registered_catalog())
    reference = importlib.import_module("molchat_agent.tools.reference")
    importlib.reload(reference)

    class BlockedReport:
        state = "blocked"

    class BlockedBridge:
        async def call(self, capability, args, **kwargs):
            if capability == "reference_count":
                return {"count": 7}
            raise AssertionError("no further reads expected")

    async def _blocked(self, plan):
        return BlockedReport()

    monkeypatch.setattr(runner, "AgentExecutor",
                        lambda bridge: type("E", (), {"execute": _blocked})())

    packs = [runner.Pack(name="example", capabilities=[
        {"name": "reference_status", "valid_args": {"record_id": "example-1"},
         "live_read": True}])]
    result = await runner.check_reads_no_mutation_live(
        packs, BlockedBridge(), {"capability": "reference_count"})
    assert result[0].status == "pass"
    assert "blocked" in result[0].detail
