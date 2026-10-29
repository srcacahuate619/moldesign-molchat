import json

import httpx
import pytest

from molchat_agent.meta import MetaPlanner


@pytest.mark.asyncio
async def test_meta_chat_supports_structured_tools():
    def handle(request):
        data = json.loads(request.content)
        assert request.url.host == "api.meta.ai"
        assert request.headers["authorization"] == "Bearer test-key"
        assert data["tools"][0]["function"]["name"] == "demo"
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await MetaPlanner(api_key="test-key", client=client).chat_with_tools(
            [{"role": "user", "content": "hola"}], [{"type": "function", "function": {"name": "demo"}}])
    assert result["content"] == "ok"


@pytest.mark.asyncio
async def test_meta_uses_structured_output_but_excludes_sensitive_tools():
    observed = {}

    def handle(request):
        observed.update(json.loads(request.content))
        assert request.url.host == "api.meta.ai"
        assert request.headers["authorization"] == "Bearer test-key"
        plan = {"steps": [{"capability": "list_targets", "arguments": {},
                           "rationale": "Primero consultar catálogo"}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan)}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        async with MetaPlanner(api_key="test-key", client=client) as planner:
            plan = await planner.plan("¿Qué receptores tengo?")
    assert plan.steps[0].capability == "list_targets"
    assert observed["response_format"]["type"] == "json_schema"
    assert "approve_docking_proposal" not in json.dumps(observed)


@pytest.mark.asyncio
async def test_unrecognized_model_tool_can_never_run():
    def handle(_):
        result = {"steps": [{"capability": "run_shell", "arguments": {"command": "echo hack"},
                             "rationale": ""}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        async with MetaPlanner(api_key="test", client=client) as planner:
            with pytest.raises(RuntimeError, match="plan válido"):
                await planner.plan("Haz algo prohibido")

