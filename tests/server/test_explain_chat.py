"""explain_evaluation through the hosted chat: the skill reads, the guard checks, the lock has the last word."""
import copy
import json
from pathlib import Path

import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.config import MolChatConfig
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.providers import build_registry
from molchat_agent.server.app import create_app
from molchat_agent.server.auth import mint, standalone_secret
from molchat_agent.server.state import ServerState

from tests.conversation.test_explain_evaluation import NOT_CALIBRATED, VERIFIED


def events(response):
    return [json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith("data:")]


def state_for(tmp_path):
    registry = build_registry(MolChatConfig())
    registry.set_active("fake")
    secret = standalone_secret()
    state = ServerState(secret=secret, registry=registry, memory=MemoryStore(tmp_path / "memory.db"),
                        backend=QualityBackend(Path(__file__).parent.parent / "quality/fixtures/properties.json"),
                        hosted=True)
    token = mint(secret, "owner", {"chat"}, 3600)
    return state, registry, {"Authorization": f"Bearer {token}"}


async def ask(tmp_path, monkeypatch, job, final_text, task_id="t-1", status=200):
    """One turn: the model calls explain_evaluation for ``task_id`` and then writes ``final_text``."""
    state, registry, headers = state_for(tmp_path)
    seen_by_model = []
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            assert "explain_evaluation" in {item["function"]["name"] for item in tools}
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "explain", "type": "function",
                "function": {"name": "explain_evaluation", "arguments": json.dumps({"task_id": task_id})}}]}
        seen_by_model.append(json.loads(messages[-1]["content"]))
        return {"role": "assistant", "content": final_text}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async def registry_for_turn(_token):
        return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    requests = []
    async def host(request):
        requests.append((request.method, request.url.path, request.headers.get("authorization")))
        return httpx.Response(status, json=job) if status == 200 else httpx.Response(status)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(host)) as host_client:
        state.bridge = MolDesignBridge(client=host_client)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                     base_url="http://testserver") as client:
            response = await client.post("/v1/chat", headers=headers, json={"text": "explícame el resultado de la tarea"})
            result = next(e["result"] for e in events(response) if e["type"] == "result")
    return result, requests, seen_by_model, headers


@pytest.mark.asyncio
async def test_a_calibrated_result_is_explained_with_its_conditions_and_only_reads(tmp_path, monkeypatch):
    answer = ("Vina 1.2.7 dio −9,48 kcal/mol (exhaustividad 8, 9 poses, semilla 42). El receptor está calibrado: "
              "ρ = 0,39, IC 95 % 0,22–0,54, n = 89. Esto ordena la serie; no es un Ki.")
    result, requests, seen, headers = await ask(tmp_path, monkeypatch, VERIFIED, answer, task_id="t-8t69")
    assert requests == [("GET", "/evaluation/status/t-8t69", headers["Authorization"])]
    assert seen[0]["calibration"]["backing"]["spearman_rho"] == 0.39
    for kept in ("−9,48", "0,39", "0,22–0,54", "n = 89", "semilla 42", "IC 95 %"):
        assert kept in result["text"]
    assert "dato no verificado" not in result["text"]
    assert result["text"].endswith("Calibración declarada por MolDesign: Calibrado para este receptor (Spearman ρ medido).")
    row = next(item for item in result["evidence"] if item["tool"] == "explain_evaluation")
    assert row["values"]["calibración"] == "calibrado" and row["values"]["exhaustividad"] == "8"


@pytest.mark.asyncio
async def test_a_number_the_facts_do_not_hold_is_hidden_even_when_it_is_close(tmp_path, monkeypatch):
    answer = "El receptor está calibrado: ρ = 0,3 y la afinidad fue −9,3 kcal/mol, con n = 89."
    result, _, _, _ = await ask(tmp_path, monkeypatch, VERIFIED, answer, task_id="t-8t69")
    assert "ρ = [dato no verificado]" in result["text"] and "[dato no verificado] kcal/mol" in result["text"]
    assert "0,3" not in result["text"].split("Calibración declarada")[0] and "n = 89" in result["text"]
    assert result["text"].startswith("Nota de verificación:")


@pytest.mark.asyncio
async def test_a_model_that_overclaims_calibration_is_followed_by_the_locks_own_warning(tmp_path, monkeypatch):
    answer = "El receptor está calibrado y la afinidad de −7,2 kcal/mol confirma un buen candidato."
    result, _, seen, _ = await ask(tmp_path, monkeypatch, NOT_CALIBRATED, answer, task_id="t-demo")
    assert seen[0]["calibration"]["backing"] is None and seen[0]["calibration"]["level"] == "curado_estructural"
    tail = result["text"].split("\n\n")[-1]
    assert tail.startswith("Calibración declarada por MolDesign: Curado estructuralmente; sin calibrar")
    assert "hipótesis a comprobar" in tail


@pytest.mark.asyncio
async def test_a_foreign_task_is_not_explained_and_adds_nothing(tmp_path, monkeypatch):
    result, requests, seen, _ = await ask(tmp_path, monkeypatch, {}, "No encontré esa tarea en tu cuenta.", status=404)
    assert seen[0]["status"] == "not_found" and len(requests) == 1
    assert "Calibración" not in result["text"]
    assert not any(item["tool"] == "explain_evaluation" for item in result["evidence"])


@pytest.mark.asyncio
async def test_a_run_still_in_progress_has_nothing_to_explain(tmp_path, monkeypatch):
    job = copy.deepcopy(VERIFIED)
    job.update({"status": "STARTED", "progress": 40, "result": None})
    result, _, seen, _ = await ask(tmp_path, monkeypatch, job, "Aún no terminó; no hay resultado que explicar.", task_id="t-8t69")
    assert seen[0]["status"] == "not_ready" and "affinity" not in seen[0]
    assert "Calibración" not in result["text"]
