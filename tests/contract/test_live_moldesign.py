"""Live contract suite: 10 requests against a real MolDesign.

Manual/pre-release only (PLAN tarea 1.1; strategy in §19)::

    python -m pytest tests/contract/ -m contract -o addopts=""

Requires MolDesign running and ``MOLDESIGN_TOKEN`` from a test account
(see docs/CONTRATO_MOLDESIGN.md). Skips — never fails — when the backend
is unreachable or the token is missing/rejected: those are environment
states, not contract verdicts. Once reachable, failures are real.
The ``bridge`` fixture lives in ``conftest.py`` (shared with Fase 3 tests).
"""

import pytest

from molchat_agent.bridge import BridgeError

pytestmark = pytest.mark.contract

TARGET = "1HSG"  # public PDB entry (HIV-1 protease)
ETHANOL = "CCO"
ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"


@pytest.mark.asyncio
async def test_1_list_targets(bridge):
    result = await bridge.call("list_targets", {})
    assert isinstance(result, (list, dict))


@pytest.mark.asyncio
async def test_2_preflight_ethanol(bridge):
    result = await bridge.call("check_preflight",
                               {"smiles": ETHANOL, "target_pdb_id": TARGET})
    assert isinstance(result, dict)
    assert isinstance(result.get("technical_blockers"), list)


@pytest.mark.asyncio
async def test_3_preflight_aspirin(bridge):
    result = await bridge.call("check_preflight",
                               {"smiles": ASPIRIN, "target_pdb_id": TARGET})
    assert isinstance(result.get("technical_blockers"), list)


@pytest.mark.asyncio
async def test_4_preflight_invalid_smiles_is_never_a_silent_pass(bridge):
    try:
        result = await bridge.call("check_preflight",
                                   {"smiles": "!!!no-es-smiles", "target_pdb_id": TARGET})
    except BridgeError:
        return  # server-side rejection: compliant
    assert isinstance(result, dict) and result.get("technical_blockers"), \
        "invalid SMILES returned without blockers"


@pytest.mark.asyncio
async def test_5_list_evaluations(bridge):
    result = await bridge.call("list_evaluations", {})
    assert isinstance(result, (list, dict))


@pytest.mark.asyncio
async def test_6_list_evaluations_pagination(bridge):
    result = await bridge.call("list_evaluations", {"page": 2, "page_size": 5})
    assert isinstance(result, (list, dict))


@pytest.mark.asyncio
async def test_7_list_evaluations_target_filter(bridge):
    result = await bridge.call("list_evaluations", {"target_pdb_id": TARGET})
    assert isinstance(result, (list, dict))


@pytest.mark.asyncio
async def test_8_status_of_unknown_task_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("evaluation_status", {"task_id": "tarea-inexistente-1"})


@pytest.mark.asyncio
async def test_9_unknown_proposal_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("get_docking_proposal", {"proposal_id": "propuesta-inexistente-1"})


@pytest.mark.asyncio
async def test_10_approve_of_unknown_proposal_fails_server_side(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("approve_docking_proposal", {
            "proposal_id": "propuesta-inexistente-1",
            "proposal_hash": "sha256:" + "0" * 64,
        })
