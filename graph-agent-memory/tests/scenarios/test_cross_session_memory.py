"""Acceptance workflow for persistent context and cross-agent handoffs."""

import json
import uuid

import pytest

from graph_memory.db import get_db
from graph_memory.mcp_server import create_mcp_server


@pytest.fixture(scope="module")
def db_client():
    client = get_db()
    health = client.check_health()
    if health.get("status") != "healthy":
        pytest.skip(f"FalkorDB is not running: {health}")
    client.init_schema()
    return client


@pytest.fixture
def scenario_workspace(db_client):
    workspace_id = f"test_cross_session_{uuid.uuid4().hex[:8]}"
    db_client.query(
        "MERGE (w:Workspace {id: $workspace_id})",
        {"workspace_id": workspace_id},
    )
    yield workspace_id
    db_client.query(
        "MATCH (n) WHERE n.workspace_id = $workspace_id DETACH DELETE n",
        {"workspace_id": workspace_id},
    )
    db_client.query(
        "MATCH (w:Workspace {id: $workspace_id}) DETACH DELETE w",
        {"workspace_id": workspace_id},
    )


def extract_result(tool_result):
    if tool_result.structured_content and "result" in tool_result.structured_content:
        return tool_result.structured_content["result"]
    if tool_result.content and hasattr(tool_result.content[0], "text"):
        return json.loads(tool_result.content[0].text)
    return tool_result.structured_content or {}


@pytest.mark.asyncio
async def test_new_agent_resumes_from_persisted_graph(db_client, scenario_workspace):
    session_a_server = create_mcp_server()
    started = await session_a_server.call_tool(
        "session_start",
        {"agent_id": "agent-a", "workspace_id": scenario_workspace},
    )
    session_a = extract_result(started)
    session_id = session_a["id"]

    saved = await session_a_server.call_tool(
        "memory_save",
        {
            "workspace_id": scenario_workspace,
            "session_id": session_id,
            "memory_type": "procedural",
            "content": "Retry transient requests with exponential backoff and jitter.",
            "source_ref": "src/retry.py",
        },
    )
    assert not saved.is_error

    appended = await session_a_server.call_tool(
        "conversation_append",
        {
            "session_id": session_id,
            "workspace_id": scenario_workspace,
            "role": "assistant",
            "content": "I confirmed the retry policy in the implementation.",
        },
    )
    assert not appended.is_error

    checkpointed = await session_a_server.call_tool(
        "session_checkpoint",
        {
            "session_id": session_id,
            "workspace_id": scenario_workspace,
            "task_progress": "Retry policy reviewed.",
            "changed_files": ["src/retry.py"],
            "verified_findings": ["Transient failures use backoff."],
            "test_outcomes": "12 passed",
            "next_steps": "Apply the policy to the queue worker.",
        },
    )
    assert not checkpointed.is_error

    # A new MCP server instance simulates a later agent process/session.
    session_b_server = create_mcp_server()
    started_b = await session_b_server.call_tool(
        "session_start",
        {"agent_id": "agent-b", "workspace_id": scenario_workspace},
    )
    session_b = extract_result(started_b)

    context_result = await session_b_server.call_tool(
        "agent_context",
        {
            "workspace_id": scenario_workspace,
            "exclude_session_id": session_b["id"],
            "query": "retry transient request policy",
        },
    )
    assert not context_result.is_error
    context = extract_result(context_result)
    assert context["estimated_tokens"] <= context["token_budget"]
    assert any(
        item["type"] == "memory"
        and "exponential backoff" in item["content"]
        for item in context["context_items"]
    )
    assert any(item["type"] == "handoff" for item in context["context_items"])

    history_result = await session_b_server.call_tool(
        "conversation_history",
        {"session_id": session_id, "workspace_id": scenario_workspace},
    )
    assert not history_result.is_error
    history = extract_result(history_result)
    assert history["count"] == 1
    assert history["messages"][0]["content"] == (
        "I confirmed the retry policy in the implementation."
    )
