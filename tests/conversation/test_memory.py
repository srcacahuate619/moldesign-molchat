"""Memory store: ownership on every row, loud persistence failures."""

import sqlite3

import pytest

from molchat_agent.conversation.memory import (
    Conversation,
    ConversationNotFound,
    MemoryStore,
    PersistenciaFallida,
)

ALICE = "alice-test"
MALLORY = "mallory-test"


@pytest.fixture
def store(tmp_path):
    return MemoryStore(tmp_path / "memory.db")


def test_crud_roundtrip(store):
    conv_id = store.create_conversation(ALICE)
    store.add_message(conv_id, ALICE, "user", "propiedades de la aspirina")
    conv = store.get_conversation(conv_id, ALICE)
    assert conv is not None and len(conv.messages) == 1
    assert store.list_conversations(ALICE)[0].id == conv_id
    assert store.delete_conversation(conv_id, ALICE) is True
    assert store.get_conversation(conv_id, ALICE) is None


def test_foreign_conversation_is_invisible(store):
    conv_id = store.create_conversation(ALICE)
    assert store.get_conversation(conv_id, MALLORY) is None
    assert store.list_conversations(MALLORY) == []
    assert store.delete_conversation(conv_id, MALLORY) is False
    assert store.get_conversation(conv_id, ALICE) is not None
    with pytest.raises(ConversationNotFound):
        store.add_message(conv_id, MALLORY, "user", "hola")
    with pytest.raises(ConversationNotFound):
        store.record_molecule(conv_id, MALLORY, "x", "CCO", {})
    with pytest.raises(ConversationNotFound):
        store.session_molecules(conv_id, MALLORY)


def test_molecules_roundtrip_deduplicated(store):
    conv_id = store.create_conversation(ALICE)
    store.record_molecule(conv_id, ALICE, "aspirina", "CCO", {"mw": 180.2})
    store.record_molecule(conv_id, ALICE, "aspirina", "CCO", {"mw": 180.2})
    molecules = store.session_molecules(conv_id, ALICE)
    assert [m["name"] for m in molecules] == ["aspirina"]
    assert molecules[0]["props"] == {"mw": 180.2}


def test_molecule_context_roundtrip(store):
    conv_id = store.create_conversation(ALICE)
    store.set_molecule_context(conv_id, ALICE, {"smiles": "CCO", "name": "etanol"})
    conv = store.get_conversation(conv_id, ALICE)
    assert conv is not None and conv.molecule_context == {"smiles": "CCO", "name": "etanol"}


def test_search_is_owner_scoped(store):
    alice_conv = store.create_conversation(ALICE)
    store.add_message(alice_conv, ALICE, "user", "un secreto sobre la aspirina")
    store.create_conversation(MALLORY)
    assert store.search_messages("secreto aspirina", MALLORY) == []
    hits = store.search_messages("secreto aspirina", ALICE)
    assert len(hits) == 1 and hits[0]["conv_id"] == alice_conv
    assert store.search_messages("a", ALICE) == []  # terms too short


def test_database_failure_is_loud(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.db")

    def _explode(*args, **kwargs):
        raise sqlite3.OperationalError("disco lleno")

    monkeypatch.setattr(sqlite3, "connect", _explode)
    with pytest.raises(PersistenciaFallida):
        store.create_conversation(ALICE)
    with pytest.raises(PersistenciaFallida):
        store.list_conversations(ALICE)


def test_delete_removes_molecules(store):
    conv_id = store.create_conversation(ALICE)
    store.record_molecule(conv_id, ALICE, "aspirina", "CCO", {})
    assert store.delete_conversation(conv_id, ALICE) is True
    with pytest.raises(ConversationNotFound):
        store.session_molecules(conv_id, ALICE)


def test_recent_context_compresses_long_histories(store):
    conv = Conversation(id="c", user_id=ALICE)
    for i in range(30):
        conv.add_message("user", f"propiedades de la aspirina variante {i}")
        conv.add_message("assistant", "Propiedades de aspirina: MW: 180.2 Da.")
    recent, summary = store.recent_context(conv)
    assert len(recent) == 12
    assert "Charla anterior" in summary
    assert "aspirina" in summary and "mw=180.2" in summary


def test_recent_context_keeps_short_histories(store):
    conv = Conversation(id="c", user_id=ALICE,
                        messages=[{"role": "user", "content": "hola MolChat, buen dia"}])
    recent, summary = store.recent_context(conv)
    assert recent == conv.messages and summary == ""
