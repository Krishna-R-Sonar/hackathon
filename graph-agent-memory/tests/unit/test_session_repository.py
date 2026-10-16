"""Database-independent tests for session transcript and handoff repository queries."""

from types import SimpleNamespace

from graph_memory.models import ConversationMessageModel, SessionModel, SessionStatus
from graph_memory.repositories.nodes import NodeRepository


class FakeDatabase:
    def __init__(self, result_set):
        self.result_set = result_set
        self.calls = []

    def query(self, cypher, params=None, read_only=False):
        self.calls.append((cypher, params or {}, read_only))
        return SimpleNamespace(result_set=self.result_set)


def message_properties(message_id, created_at):
    return {
        "id": message_id,
        "workspace_id": "workspace-a",
        "session_id": "session-a",
        "role": "assistant",
        "content": message_id,
        "created_at": created_at,
    }


def test_conversation_history_clamps_limit_and_returns_chronological_order():
    later = SimpleNamespace(properties=message_properties("msg-b", "2026-10-02T00:00:00+00:00"))
    earlier = SimpleNamespace(properties=message_properties("msg-a", "2026-10-01T00:00:00+00:00"))
    db = FakeDatabase([[later], [earlier]])
    repository = NodeRepository(db)

    messages = repository.get_conversation_history("session-a", "workspace-a", limit=500)

    assert [message.id for message in messages] == ["msg-a", "msg-b"]
    cypher, params, read_only = db.calls[0]
    assert "LIMIT 100" in cypher
    assert "{id: $session_id, workspace_id: $workspace_id}" in cypher
    assert params == {"session_id": "session-a", "workspace_id": "workspace-a"}
    assert read_only


def test_conversation_append_is_scoped_to_the_session_workspace():
    message = ConversationMessageModel(
        id="msg-a",
        workspace_id="workspace-a",
        session_id="session-a",
        role="user",
        content="Continue the previous task.",
    )
    db = FakeDatabase([[SimpleNamespace(properties=message.model_dump())]])

    saved = NodeRepository(db).save_conversation_message(message)

    assert saved == message
    cypher, params, read_only = db.calls[0]
    assert "MATCH (s:Session {id: $session_id, workspace_id: $workspace_id})" in cypher
    assert "MERGE (s)-[:HAS_MESSAGE]->(msg)" in cypher
    assert params["workspace_id"] == "workspace-a"
    assert params["session_id"] == "session-a"
    assert not read_only


def test_session_updates_use_atomic_version_comparison():
    session = SessionModel(
        id="session-a",
        workspace_id="workspace-a",
        agent_id="agent-a",
        status=SessionStatus.CHECKPOINTED,
        version=3,
        summary="Saved progress",
    )
    updated_properties = {
        **session.model_dump(),
        "version": 4,
    }
    db = FakeDatabase([[SimpleNamespace(properties=updated_properties)]])

    updated = NodeRepository(db).update_session(session, expected_version=3)

    assert updated.version == 4
    cypher, params, read_only = db.calls[0]
    assert "WHERE coalesce(s.version, 1) = $expected_version" in cypher
    assert "s.version = coalesce(s.version, 1) + 1" in cypher
    assert params["expected_version"] == 3
    assert not read_only
