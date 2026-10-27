"""Live contract: CR-07 proposal creation + CR-06 reconcile/replay.

Needs the platform branch with CR-06/CR-07 (feat/molchat-plataforma-cr).
Same rules as the other live suites: skips without backend/token; failures
are real once reachable. The positive sequence creates REAL proposals
(pending, server-side TTL expiry) and seals idempotency keys in the test
account — that is the surface under test, not litter to avoid.

Launching a real evaluation is gated behind MOLCHAT_CONTRACT_MAY_LAUNCH=1:
compute starts only with explicit operator consent.
"""

import os
import uuid

import pytest

from molchat_agent.bridge import BridgeError

pytestmark = pytest.mark.contract

SMILES = "CCO"
TARGET = "7E2Y"  # platform default target (pre-curated)

needs_launch = pytest.mark.skipif(
    os.environ.get("MOLCHAT_CONTRACT_MAY_LAUNCH") != "1",
    reason="MOLCHAT_CONTRACT_MAY_LAUNCH!=1: no compute from the suite")


def _key():
    return f"molchat-contract-{uuid.uuid4().hex}"


@pytest.mark.asyncio
async def test_create_returns_reviewable_proposal(bridge):
    proposal = await bridge.call("create_docking_proposal", {
        "smiles": SMILES, "target_pdb_id": TARGET})
    assert proposal["proposal_id"]
    assert proposal["proposal_hash"].startswith("sha256:")
    assert len(proposal["proposal_hash"]) == 71
    assert proposal["estado"] == "pendiente"
    assert isinstance(proposal["parametros_efectivos"], dict)
    assert isinstance(proposal["preflight"], dict)


@pytest.mark.asyncio
async def test_create_rejects_invalid_smiles(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("create_docking_proposal", {
            "smiles": "NO-ES-SMILES!!!", "target_pdb_id": TARGET})


@pytest.mark.asyncio
async def test_same_key_replays_same_proposal(bridge):
    key = _key()
    args = {"smiles": SMILES, "target_pdb_id": TARGET}
    first = await bridge.call("create_docking_proposal", args, idempotency_key=key)
    second = await bridge.call("create_docking_proposal", args, idempotency_key=key)
    assert second["proposal_id"] == first["proposal_id"]
    assert second["proposal_hash"] == first["proposal_hash"]


@pytest.mark.asyncio
async def test_reconcile_reports_completed_operation(bridge):
    key = _key()
    created = await bridge.call("create_docking_proposal", {
        "smiles": SMILES, "target_pdb_id": TARGET}, idempotency_key=key)
    vista = await bridge.call("reconcile_operation", {"idempotency_key": key})
    assert vista["operation"] == "crear_propuesta"
    assert vista["status"] == "COMPLETADA"
    assert vista["proposal_id"] == created["proposal_id"]
    assert vista["response"]["proposal_id"] == created["proposal_id"]


@pytest.mark.asyncio
async def test_reconcile_of_unknown_key_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("reconcile_operation", {"idempotency_key": _key()})


@needs_launch
@pytest.mark.asyncio
async def test_approve_with_key_replays_task_id(bridge):
    created = await bridge.call("create_docking_proposal", {
        "smiles": SMILES, "target_pdb_id": TARGET})
    key = _key()
    args = {"proposal_id": created["proposal_id"],
            "proposal_hash": created["proposal_hash"]}
    first = await bridge.call("approve_docking_proposal", args, idempotency_key=key)
    assert first["task_id"]
    second = await bridge.call("approve_docking_proposal", args, idempotency_key=key)
    assert second["task_id"] == first["task_id"]  # replayed, no second run
