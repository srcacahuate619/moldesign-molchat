"""Consent gate: no remote byte without a grant for that destination."""

import json

import httpx
import pytest

from molchat_agent.config import DEFAULT_PROFILE, load_config
from molchat_agent.providers import (
    ConsentDenied,
    ConsentStore,
    FakeProvider,
    ProviderRegistry,
    build_registry,
    resolve_destination,
)
from molchat_agent.providers.base import (
    HealthCheckResult,
    HealthStatus,
    ProviderConfig,
)
from molchat_agent.providers.meta import MetaProvider


class _StubRemote:
    id = "stub-remote"
    locality = "remote"

    def __init__(self, base_url="https://cloud.example/v1"):
        self.config = ProviderConfig(base_url=base_url)
        self.calls = 0

    async def health(self):
        self.calls += 1
        return HealthCheckResult(status=HealthStatus.OK)

    async def plan(self, goal, catalog=None):
        self.calls += 1
        return await FakeProvider().plan(goal, catalog)

    async def chat(self, turn):
        raise NotImplementedError
        yield


def _registry(tmp_path, profile=DEFAULT_PROFILE, **kwargs):
    registry = ProviderRegistry(
        profile=profile, consents=ConsentStore(tmp_path / "consents.json"), **kwargs)
    registry.register(FakeProvider())
    registry.register(_StubRemote())
    return registry


def test_destination_is_computed_and_unknown_means_remote(tmp_path):
    registry = _registry(tmp_path)
    meta = MetaProvider(api_key="test-key")
    assert resolve_destination(meta).fingerprint == "meta@api.meta.ai"
    assert resolve_destination(FakeProvider()).is_remote is False
    remote = registry.destination("stub-remote")
    assert remote.fingerprint == "stub-remote@cloud.example"
    assert remote.is_remote is True


@pytest.mark.asyncio
async def test_remote_plan_without_consent_sends_nothing(tmp_path):
    registry = _registry(tmp_path)
    with pytest.raises(ConsentDenied, match="cloud.example"):
        await registry.plan("hola", provider_id="stub-remote")
    assert registry.get("stub-remote").calls == 0


@pytest.mark.asyncio
async def test_grant_then_plan_then_revoke(tmp_path):
    registry = _registry(tmp_path)
    record = registry.grant("stub-remote")
    assert record["host"] == "cloud.example"
    assert "granted_at" in record
    plan = await registry.plan("¿Qué receptores tengo?", provider_id="stub-remote")
    assert plan.steps[0].capability == "list_targets"
    assert registry.get("stub-remote").calls == 1
    assert registry.revoke("stub-remote") == ["stub-remote@cloud.example"]
    with pytest.raises(ConsentDenied):
        await registry.plan("hola", provider_id="stub-remote")


def test_grant_local_is_rejected_and_revoke_unknown_is_empty(tmp_path):
    registry = _registry(tmp_path)
    with pytest.raises(ValueError, match="nada que autorizar"):
        registry.grant("fake")
    assert registry.revoke("stub-remote") == []


@pytest.mark.asyncio
async def test_offline_overrides_grants(tmp_path):
    registry = _registry(tmp_path, offline=True)
    registry.grant("stub-remote")
    with pytest.raises(ConsentDenied, match="offline"):
        await registry.plan("hola", provider_id="stub-remote")
    assert registry.get("stub-remote").calls == 0


@pytest.mark.asyncio
async def test_status_never_probes_unconsented_remote(tmp_path):
    registry = _registry(tmp_path)
    rows = {r.provider_id: r for r in await registry.status()}
    assert rows["stub-remote"].health.status == HealthStatus.NO_CONSENT
    assert rows["stub-remote"].consented is False
    assert registry.get("stub-remote").calls == 0
    assert rows["fake"].consented is True
    assert rows["fake"].health.status == HealthStatus.OK


def test_corrupt_consents_file_fails_loud(tmp_path):
    path = tmp_path / "consents.json"
    path.write_text("{no es json", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupto"):
        ConsentStore(path).records()


@pytest.mark.asyncio
async def test_meta_end_to_end_grant_flow_with_mock_transport(tmp_path):
    def handle(request):
        plan = {"steps": [{"capability": "list_targets", "arguments": {},
                            "rationale": "demo"}]}
        return httpx.Response(200, json={"choices": [
            {"message": {"content": json.dumps(plan)}}]})

    config = load_config({"MODEL_API_KEY": "test-key",
                          "MOLCHAT_CONSENTS_FILE": str(tmp_path / "c.json")})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        registry = build_registry(config, clients={"meta": client})
        with pytest.raises(ConsentDenied, match="meta@api.meta.ai"):
            await registry.plan("¿Qué receptores tengo?", provider_id="meta")
        registry.grant("meta")
        plan = await registry.plan("¿Qué receptores tengo?", provider_id="meta")
        assert plan.planner == "meta:muse-spark-1.3"
