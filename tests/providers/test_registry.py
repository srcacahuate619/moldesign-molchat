"""Registry: routing, profiles, and active provider."""

import pytest

from molchat_agent.config import DEFAULT_PROFILE, HACKATHON_PROFILE, load_config
from molchat_agent.providers import (
    ConsentStore,
    FakeProvider,
    ProviderDisabled,
    ProviderRegistry,
    UnknownProviderError,
    build_registry,
)
from molchat_agent.providers.base import (
    HealthCheckResult,
    HealthStatus,
    ProviderConfig,
)


class _StubRemote:
    """Minimal remote provider double (no network)."""

    id = "stub-remote"
    locality = "remote"

    def __init__(self) -> None:
        self.config = ProviderConfig(base_url="https://cloud.example/v1")
        self.plans = 0

    async def health(self):
        return HealthCheckResult(status=HealthStatus.OK)

    async def plan(self, goal, catalog=None):
        self.plans += 1
        return await FakeProvider().plan(goal, catalog)

    async def chat(self, turn):
        raise NotImplementedError
        yield


class _StubMeta(_StubRemote):
    id = "meta"
    locality = "remote"


def _registry_with_stubs(profile, consents=None):
    registry = ProviderRegistry(profile=profile, consents=consents)
    registry.register(FakeProvider())
    registry.register(_StubRemote())
    registry.register(_StubMeta())
    return registry


def test_unknown_provider_raises():
    with pytest.raises(UnknownProviderError):
        ProviderRegistry().get("nope")


def test_hackathon_allows_local_and_meta_only():
    registry = _registry_with_stubs(HACKATHON_PROFILE)
    assert registry.get("fake") is not None
    assert registry.get("meta") is not None
    with pytest.raises(ProviderDisabled):
        registry.get("stub-remote")


def test_default_profile_allows_everything_registered():
    registry = _registry_with_stubs(DEFAULT_PROFILE)
    assert registry.get("stub-remote") is not None


def test_active_defaults_to_meta_then_fake():
    assert _registry_with_stubs(HACKATHON_PROFILE).active_id == "meta"
    registry = ProviderRegistry()
    registry.register(FakeProvider())
    assert registry.active_id == "fake"


def test_set_active_validates_known_and_enabled():
    registry = _registry_with_stubs(HACKATHON_PROFILE)
    registry.set_active("fake")
    assert registry.active_id == "fake"
    with pytest.raises(ProviderDisabled):
        registry.set_active("stub-remote")
    with pytest.raises(UnknownProviderError):
        registry.set_active("nope")


@pytest.mark.asyncio
async def test_plan_routes_to_active_or_named_provider(tmp_path):
    registry = _registry_with_stubs(
        DEFAULT_PROFILE, ConsentStore(tmp_path / "c.json"))
    registry.grant("stub-remote")
    plan = await registry.plan("¿Qué receptores tengo?", provider_id="stub-remote")
    assert plan.steps[0].capability == "list_targets"
    assert registry.get("stub-remote").plans == 1


def test_build_registry_from_config():
    registry = build_registry(load_config({"MOLCHAT_PROVIDER": "fake"}))
    assert registry.profile == HACKATHON_PROFILE
    assert registry.active_id == "fake"
    assert registry.ids() == ["fake", "llama-server", "meta", "ollama", "openai-compatible"]
