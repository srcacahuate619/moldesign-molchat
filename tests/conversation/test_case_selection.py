import pytest

from molchat_agent.conversation.case_selection import CreateCase, parse_case_selection, select_case
from molchat_agent.providers.base import ChatEvent


def test_selection_requires_the_exact_user_supplied_name():
    assert parse_case_selection('{"tool":"create_case","name":"holamundo"}',
                                'crea un caso llamado "holamundo"') == CreateCase("holamundo")
    assert parse_case_selection('{"tool":"create_case","name":"otro"}',
                                'crea un caso llamado "holamundo"') is None
    assert parse_case_selection('{"tool":"create_case","name":"mundo"}',
                                'crea un caso llamado "holamundo"') is None


@pytest.mark.parametrize("response", [
    "no es json", "[]", '{"tool":"delete_case","name":"holamundo"}',
    '{"tool":"create_case","name":"holamundo","user_id":"otra-cuenta"}',
    '{"tool":"create_case","name":""}',
])
def test_untrusted_selection_is_rejected(response):
    assert parse_case_selection(response, 'crea el caso "holamundo"') is None


@pytest.mark.asyncio
async def test_model_proposes_but_does_not_create_a_case():
    class Provider:
        async def chat(self, turn):
            assert "create_case" in turn.messages[0]["content"]
            yield ChatEvent(type="token", text='{"tool":"create_case","name":"holamundo"}')
            yield ChatEvent(type="done", done=True)

    assert await select_case(Provider(), 'crea el caso "holamundo"') == CreateCase("holamundo")
