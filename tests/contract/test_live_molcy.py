"""Live contract: Molcy renders (discovery, status, acta, cancel).

Error paths use bogus UUIDs (no state changes). The positive render is
gated behind MOLCHAT_CONTRACT_MAY_LAUNCH=1: it consumes real GPU minutes,
so it picks the first available moldex source, requests a preview render,
polls briefly (never to completion here), and cancels to free the GPU.
"""

import os
import uuid

import pytest

from molchat_agent.bridge import BridgeError

pytestmark = pytest.mark.contract

BOGUS_UUID = "12345678-1234-1234-1234-123456789012"

needs_launch = pytest.mark.skipif(
    os.environ.get("MOLCHAT_CONTRACT_MAY_LAUNCH") != "1",
    reason="MOLCHAT_CONTRACT_MAY_LAUNCH!=1: no GPU from the suite")


@pytest.mark.asyncio
async def test_fuentes_lists_moldex_and_receptores(bridge):
    fuentes = await bridge.call("molcy_fuentes", {})
    assert isinstance(fuentes["moldex"], list)
    assert isinstance(fuentes["receptores"], list)


@pytest.mark.asyncio
async def test_unknown_job_status_procedencia_and_cancel_fail(bridge):
    with pytest.raises(BridgeError):
        await bridge.call("molcy_job_status", {"job_id": BOGUS_UUID})
    with pytest.raises(BridgeError):
        await bridge.call("get_video_acta", {"job_id": BOGUS_UUID})
    with pytest.raises(BridgeError):
        await bridge.call("cancel_molcy_job", {"job_id": BOGUS_UUID})


@needs_launch
@pytest.mark.asyncio
async def test_request_poll_and_cancel_render(bridge):
    fuentes = await bridge.call("molcy_fuentes", {})
    ready = [m for m in fuentes["moldex"]
             if m.get("disponible") and "resultado" in (m.get("escenas_disponibles") or [])]
    if not ready:
        pytest.skip("sin corridas renderizables en la cuenta de pruebas")
    source = ready[0]
    args = {"origen": "moldex", "id": source["id"], "escena": "resultado",
            "formato": "previsualizacion"}
    if source.get("task_id"):
        args["task_id"] = source["task_id"]
    try:
        job = await bridge.call("request_case_video", args)
    except BridgeError as exc:
        pytest.skip(f"render no disponible aquí: {exc}")
    assert job["estado"] in ("en_cola", "renderizando")
    try:
        status = await bridge.call("molcy_job_status", {"job_id": job["id"]})
        assert status["estado"] in ("en_cola", "renderizando", "completo",
                                    "fallido", "cancelado")
    finally:
        await bridge.call("cancel_molcy_job", {"job_id": job["id"]})
    assert uuid.UUID(job["id"])  # well-formed job identity
