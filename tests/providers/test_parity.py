"""Exit-gate proof (mock level): one goal, valid plans, three providers.

Fake needs no transport; llama-server and Meta run against mocked HTTP.
Live confirmation against a running llama-server and the Meta API is a
manual pre-release step (see docs/CONTRATO_MOLDESIGN.md).
"""

import json

import httpx
import pytest

from molchat_agent.capabilities import CAPABILITIES
from molchat_agent.providers import FakeProvider, LlamaServerProvider, MetaProvider

GOAL = "¿Qué receptores tengo?"
PLAN = {"steps": [{"capability": "list_targets", "arguments": {},
                    "rationale": "Primero consultar catálogo"}]}


def _completions_mock():
    def handle(request):
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json={"choices": [
            {"message": {"content": json.dumps(PLAN)}}]})

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
async def test_same_goal_yields_valid_plans_from_fake_local_and_meta():
    plans = [await FakeProvider().plan(GOAL)]
    async with httpx.AsyncClient(transport=_completions_mock()) as client:
        plans.append(await LlamaServerProvider(model="qwen-test", client=client).plan(GOAL))
    async with httpx.AsyncClient(transport=_completions_mock()) as client:
        plans.append(await MetaProvider(api_key="test-key", client=client).plan(GOAL))
    assert [p.goal for p in plans] == [GOAL] * 3
    for plan in plans:
        for step in plan.steps:
            assert CAPABILITIES[step.capability].risk == "read"
    assert plans[0].planner == "fake:deterministic"
    assert plans[1].planner == "llama-server:qwen-test"
    assert plans[2].planner == "meta:muse-spark-1.3"
