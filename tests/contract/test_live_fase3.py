"""Live contract: Fase 3 capabilities (engines, results, batch, reports).

Same rules as the Fase 1 suite (see ``test_live_moldesign.py``): skips
without backend/token; failures are real once reachable. Error paths use
bogus ids (no state changes). Positive paths need ``MOLCHAT_CONTRACT_MOLECULE_ID``
(a UUID with an evaluation result in the test account) and skip without it.
"""

import os

import pytest

from molchat_agent.bridge import BridgeError

pytestmark = pytest.mark.contract

BOGUS_UUID = "12345678-1234-1234-1234-123456789012"
_MOLECULE_ID = os.environ.get("MOLCHAT_CONTRACT_MOLECULE_ID", "")

needs_molecule = pytest.mark.skipif(
    not _MOLECULE_ID, reason="MOLCHAT_CONTRACT_MOLECULE_ID sin fijar")


@pytest.mark.asyncio
async def test_engines_returns_inventory(bridge):
    assert isinstance(await bridge.call("list_engines", {}), dict)


@pytest.mark.asyncio
async def test_history_stats_returns_counters(bridge):
    result = await bridge.call("get_history_stats", {})
    assert isinstance(result, dict)
    assert "total_evaluations" in result


@pytest.mark.asyncio
async def test_rescoring_endpoints_answer(bridge):
    for name in ("rescoring_health", "rescoring_info", "rescoring_ram"):
        assert isinstance(await bridge.call(name, {}), dict)


@pytest.mark.asyncio
async def test_result_of_unknown_molecule_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("get_evaluation_result", {"molecule_id": BOGUS_UUID})


@pytest.mark.asyncio
async def test_interactions_of_unknown_molecule_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("get_interactions", {"molecule_id": BOGUS_UUID})


@pytest.mark.asyncio
async def test_gnn_of_unknown_molecule_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("get_gnn_attention", {"molecule_id": BOGUS_UUID})


@pytest.mark.asyncio
async def test_sar_of_unknown_molecule_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("get_sar", {"molecule_id": BOGUS_UUID})


@pytest.mark.asyncio
async def test_ai_report_of_unknown_molecule_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("get_ai_report", {"molecule_id": BOGUS_UUID})


@pytest.mark.asyncio
async def test_ai_report_stream_of_unknown_molecule_fails(bridge):
    try:
        result = await bridge.call("stream_ai_report", {"molecule_id": BOGUS_UUID})
    except BridgeError:
        return
    assert result == {"events": []}  # empty stream is also a clean miss


@pytest.mark.asyncio
async def test_dossier_of_unknown_molecule_fails(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("get_case_dossier", {"molecule_id": BOGUS_UUID,
                                               "format": "preview"})


@pytest.mark.asyncio
async def test_batch_endpoints_reject_unknown_ids(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("batch_status", {"batch_id": "lote-inexistente-1"})
    with pytest.raises(BridgeError):
        await bridge.call("cancel_batch", {"batch_id": "lote-inexistente-1"})
    with pytest.raises(BridgeError):
        await bridge.call("export_batch", {"batch_id": "lote-inexistente-1",
                                           "format": "csv"})


@pytest.mark.asyncio
async def test_cancel_of_unknown_task_fails(bridge):
    try:
        result = await bridge.call("cancel_evaluation", {"task_id": "tarea-inexistente-1"})
    except BridgeError:
        return  # unknown task rejected: compliant
    assert result.get("cancelled") is False  # or a clean negative


@pytest.mark.asyncio
async def test_save_of_unknown_molecule_fails_without_writes(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("save_molecule", {"molecule_id": BOGUS_UUID})


@pytest.mark.asyncio
async def test_stream_of_unknown_task_is_clean(bridge):
    try:
        result = await bridge.call("stream_evaluation", {"task_id": "tarea-inexistente-1"})
    except BridgeError:
        return
    assert isinstance(result.get("events"), list)


@needs_molecule
@pytest.mark.asyncio
async def test_result_positive_returns_typed_record(bridge):
    result = await bridge.call("get_evaluation_result", {"molecule_id": _MOLECULE_ID})
    assert isinstance(result, dict)
    assert result.get("molecule_id") == _MOLECULE_ID


@needs_molecule
@pytest.mark.asyncio
async def test_per_molecule_reads_answer_or_clean_404(bridge):
    """Interactions/GNN/SAR/AI-report depend on stored data: dict or clean 404."""
    for name, args in (
        ("get_interactions", {"molecule_id": _MOLECULE_ID}),
        ("get_gnn_attention", {"molecule_id": _MOLECULE_ID}),
        ("get_sar", {"molecule_id": _MOLECULE_ID}),
        ("get_ai_report", {"molecule_id": _MOLECULE_ID}),
    ):
        try:
            result = await bridge.call(name, args)
        except BridgeError:
            continue  # no stored data for this molecule: compliant
        assert isinstance(result, (dict, list)), name


@needs_molecule
@pytest.mark.asyncio
async def test_dossier_positive_returns_bytes_or_clean_404(bridge):
    try:
        result = await bridge.call("get_case_dossier", {"molecule_id": _MOLECULE_ID,
                                                        "format": "preview"})
    except BridgeError:
        return  # no result to document: compliant
    assert isinstance(result, bytes) and len(result) > 0
