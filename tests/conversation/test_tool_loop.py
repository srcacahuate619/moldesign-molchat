import json

import httpx
import pytest

from molchat_agent.conversation.tool_loop import Tool, _arguments, run_tool_loop
from molchat_agent.providers.base import ProviderError
from molchat_agent.providers.openai_compatible import OpenAICompatibleProvider


SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"name": {"type": "string", "maxLength": 120}},
          "required": ["name"]}

CID_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "case_name": {"type": "string", "maxLength": 100},
    "cid": {"type": "integer", "minimum": 1, "maximum": 999999999999}}, "required": ["case_name", "cid"]}


@pytest.mark.parametrize("cid", [9887712, "9887712"])
def test_cid_accepts_integer_and_decimal_string(cid):
    assert _arguments(json.dumps({"case_name": "prueba2", "cid": cid}), CID_SCHEMA) == {"case_name": "prueba2", "cid": 9887712}


@pytest.mark.parametrize("cid", [True, 0, -1, 2.5, "1.5", "abc", "9" * 13])
def test_invalid_cid_is_rejected(cid):
    with pytest.raises(ValueError, match="cid"):
        _arguments(json.dumps({"case_name": "prueba2", "cid": cid}), CID_SCHEMA)


@pytest.mark.asyncio
async def test_schema_error_gives_model_actionable_feedback_before_safe_retry():
    executed = []
    class Provider:
        async def chat_with_tools(self, messages, tools):
            count = sum(entry.get("role") == "tool" for entry in messages)
            if count == 0:
                return call("verify_editor_structure", '{"case_name":"prueba2","cid":9887712,"smiles":"CCO"}', "bad")
            if count == 1:
                message = json.loads(messages[-1]["content"])["error"]
                assert "no se ejecutó" in message and "case_name, cid" in message
                return call("verify_editor_structure", '{"case_name":"prueba2","cid":9887712}', "good")
            return {"role": "assistant", "content": "Verificación terminada."}
    async def execute(args):
        executed.append(args)
        return {"status": "match"}
    await run_tool_loop(Provider(), [{"role": "user", "content": "verifica"}], [Tool("verify_editor_structure", "Verifica", CID_SCHEMA, execute)])
    assert executed == [{"case_name": "prueba2", "cid": 9887712}]


def call(name="pubchem_lookup", args='{"name":"ibuprofeno"}', call_id="call_1"):
    return {"role": "assistant", "content": None, "tool_calls": [{
        "id": call_id, "type": "function", "function": {"name": name, "arguments": args}}]}


@pytest.mark.asyncio
async def test_tool_schema_result_and_original_question_are_sent_in_one_loop():
    payloads = []
    async def handle(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        if len(payloads) == 1:
            reply = call()
        else:
            assert payload["messages"][1]["content"] == "Busca ibuprofeno"
            assert payload["messages"][2]["tool_calls"][0]["id"] == "call_1"
            assert payload["messages"][3]["role"] == "tool"
            assert payload["messages"][3]["tool_call_id"] == "call_1"
            assert json.loads(payload["messages"][3]["content"])["name"] == "ibuprofeno"
            reply = {"role": "assistant", "content": "Encontré una referencia."}
        return httpx.Response(200, json={"choices": [{"message": reply}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleProvider(base_url="http://127.0.0.1:8000/v1", model="test", client=client)
        async def lookup(args):
            return {"name": args["name"], "cid": 3672}
        result = await run_tool_loop(provider, [{"role": "system", "content": "Ayuda"},
                                                {"role": "user", "content": "Busca ibuprofeno"}],
                                     [Tool("pubchem_lookup", "Busca", SCHEMA, lookup)])
    assert result.text == "Encontré una referencia."
    assert payloads[0]["tools"][0]["function"]["parameters"] == SCHEMA
    assert payloads[0]["tool_choice"] == "auto"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_call", [call(name="unknown"), call(args='{"name":"x","extra":"y"}'), call(args="no-json")])
async def test_invalid_calls_do_not_execute(bad_call):
    invoked = []
    class Provider:
        async def chat_with_tools(self, messages, tools):
            if len(messages) == 1:
                return bad_call
            assert "no se ejecutó" in json.loads(messages[-1]["content"])["error"]
            return {"role": "assistant", "content": "Necesito más datos."}
    async def execute(args):
        invoked.append(args)
        return {}
    await run_tool_loop(Provider(), [{"role": "user", "content": "hola"}],
                        [Tool("pubchem_lookup", "Busca", SCHEMA, execute)])
    assert not invoked


@pytest.mark.asyncio
async def test_execution_failure_never_claims_no_action_or_retries():
    calls = []
    class Provider:
        async def chat_with_tools(self, messages, tools):
            if len(messages) == 1:
                return call()
            assert "No se pudo confirmar" in json.loads(messages[-1]["content"])["error"]
            return {"role": "assistant", "content": "No pude confirmar."}
    async def execute(args):
        calls.append(args)
        raise ValueError("unexpected failure after operation")
    await run_tool_loop(Provider(), [{"role": "user", "content": "hola"}],
                        [Tool("pubchem_lookup", "Busca", SCHEMA, execute)])
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_repeated_call_id_and_step_limit():
    class Provider:
        async def chat_with_tools(self, messages, tools):
            return call()
    async def execute(args):
        return {"ok": True}
    tool = Tool("pubchem_lookup", "Busca", SCHEMA, execute)
    with pytest.raises(ProviderError):
        await run_tool_loop(Provider(), [{"role": "user", "content": "hola"}], [tool])
    result = await run_tool_loop(Provider(), [{"role": "user", "content": "hola"}], [tool], max_steps=1)
    assert result.exhausted


@pytest.mark.asyncio
async def test_six_step_budget_allows_four_tool_calls_and_model_summary():
    calls = []
    class Provider:
        async def chat_with_tools(self, messages, _tools):
            done = sum(1 for message in messages if message.get("role") == "tool")
            if done == 4:
                return {"role": "assistant", "content": "Acciones confirmadas."}
            return call(call_id=f"step-{done}")
    async def execute(args):
        calls.append(args)
        return {"status": "ok"}
    result = await run_tool_loop(Provider(), [{"role": "user", "content": "consulta"}],
                                 [Tool("pubchem_lookup", "Busca", SCHEMA, execute)], max_steps=6)
    assert result.text == "Acciones confirmadas." and not result.exhausted and len(calls) == 4


