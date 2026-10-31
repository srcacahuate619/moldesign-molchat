import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.conversation.harness_tools import evaluation_status_tool


def tool_for(handler, token="test-account-token"):
    client = httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handler))
    return evaluation_status_tool(MolDesignBridge(client=client, token=token)), client


@pytest.mark.asyncio
async def test_success_keeps_vina_energy_calibration_and_the_caveat():
    seen = []
    async def host(request):
        seen.append(request)
        return httpx.Response(200, json={"task_id": "t-1", "status": "SUCCESS", "progress": 100, "result": {
            "molecule_id": "m-1", "affinity_kcal": -7.2, "target_name": "VMAT2", "vina_version": "1.2.7",
            "target_calibracion": {"estado": "sin_calibrar"}, "scientific_warnings": [{"codigo": "X"}], "docking_poses": [{"x": 1}]}})
    tool, client = tool_for(host)
    async with client:
        result = await tool.execute({"task_id": "t-1"})
    assert seen[0].url.path == "/evaluation/status/t-1"
    assert seen[0].headers["authorization"] == "Bearer test-account-token"
    assert result["task_status"] == "SUCCESS" and result["result"]["affinity_kcal"] == -7.2
    assert result["result"]["target_calibracion"] == {"estado": "sin_calibrar"}
    assert result["result"]["scientific_warnings"] == 1 and "docking_poses" not in result["result"]
    assert "no una energía libre ni un Ki" in result["note"]


@pytest.mark.asyncio
async def test_running_task_has_no_result_or_note():
    async def host(_request):
        return httpx.Response(200, json={"task_id": "t-2", "status": "STARTED", "progress": 40, "result": None})
    tool, client = tool_for(host)
    async with client:
        result = await tool.execute({"task_id": "t-2"})
    assert result["task_status"] == "STARTED" and result["progress"] == 40
    assert "result" not in result and "note" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [403, 404])
async def test_foreign_or_unknown_task_is_not_found(code):
    async def host(_request):
        return httpx.Response(code)
    tool, client = tool_for(host)
    async with client:
        assert (await tool.execute({"task_id": "t-3"}))["status"] == "not_found"


@pytest.mark.asyncio
async def test_invalid_id_and_missing_session_never_reach_the_host():
    calls = []
    async def host(request):
        calls.append(request)
        return httpx.Response(200, json={})
    tool, client = tool_for(host)
    async with client:
        assert (await tool.execute({"task_id": "../etc"}))["status"] == "invalid"
    tool, client = tool_for(host, token=None)
    async with client:
        assert (await tool.execute({"task_id": "t-4"}))["status"] == "unavailable"
    assert not calls


@pytest.mark.asyncio
async def test_mismatched_or_failed_response_abstains():
    async def mismatch(_request):
        return httpx.Response(200, json={"task_id": "otra", "status": "SUCCESS"})
    async def down(_request):
        return httpx.Response(503)
    for handler in (mismatch, down):
        tool, client = tool_for(handler)
        async with client:
            assert (await tool.execute({"task_id": "t-5"}))["status"] == "unavailable"
