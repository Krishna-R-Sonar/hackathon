"""
MCP Server protocol and tool execution tests.
Verifies tool registration, schema adherence, and end-to-end tool execution via MCPServer.
"""

import pytest
import uuid
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


@pytest.fixture(scope="module")
def mcp_app():
    return create_mcp_server()


@pytest.fixture
def mcp_workspace(db_client):
    ws_id = f"test_mcp_{uuid.uuid4().hex[:8]}"
    db_client.query("MERGE (w:Workspace {id: $ws}) SET w.name = $ws", {"ws": ws_id})
    yield ws_id
    db_client.query("MATCH (n) WHERE n.workspace_id = $ws DETACH DELETE n", {"ws": ws_id})
    db_client.query("MATCH (w:Workspace {id: $ws}) DETACH DELETE w", {"ws": ws_id})


import json

def extract_result(tool_res):
    if tool_res.structured_content and "result" in tool_res.structured_content:
        return tool_res.structured_content["result"]
    if tool_res.content and hasattr(tool_res.content[0], "text"):
        return json.loads(tool_res.content[0].text)
    return tool_res.structured_content or {}


@pytest.mark.asyncio
async def test_mcp_tool_registration(mcp_app):
    tools = await mcp_app.list_tools()
    tool_names = {t.name for t in tools}
    expected_tools = {
        "memory_search",
        "memory_get",
        "memory_traverse",
        "memory_save",
        "memory_update",
        "decision_record",
        "session_start",
        "session_checkpoint",
        "session_end",
        "memory_feedback",
        "conversation_append",
        "conversation_history",
        "session_get_handoff",
        "agent_context",
    }
    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"
    assert len(tools) == 14


@pytest.mark.asyncio
async def test_mcp_session_lifecycle(mcp_app, mcp_workspace):
    # 1. session_start
    res_start = await mcp_app.call_tool(
        "session_start",
        {"agent_id": "test_agent_1", "workspace_id": mcp_workspace},
    )
    assert not res_start.is_error
    sess_data = extract_result(res_start)
    session_id = sess_data["id"]
    assert session_id.startswith("sess_")
    assert sess_data["status"] == "active"

    # Transcript messages persist independently of the MCP server process.
    res_message = await mcp_app.call_tool(
        "conversation_append",
        {
            "session_id": session_id,
            "workspace_id": mcp_workspace,
            "role": "user",
            "content": "Investigate the retry behavior.",
            "message_id": f"msg_{uuid.uuid4().hex}",
        },
    )
    assert not res_message.is_error
    msg_data = extract_result(res_message)
    assert msg_data["session_id"] == session_id

    res_history = await mcp_app.call_tool(
        "conversation_history",
        {"session_id": session_id, "workspace_id": mcp_workspace, "limit": 1},
    )
    assert not res_history.is_error
    history = extract_result(res_history)
    assert history["count"] == 1
    assert history["messages"][0]["content"] == "Investigate the retry behavior."

    # 2. session_checkpoint
    res_ckpt = await mcp_app.call_tool(
        "session_checkpoint",
        {
            "session_id": session_id,
            "workspace_id": mcp_workspace,
            "task_progress": "Implemented initial module skeleton",
            "verified_findings": ["Module compiles with 0 errors"],
            "changed_files": ["src/worker.py"],
            "test_outcomes": "8 passed",
            "blockers": "Waiting for API contract approval",
            "next_steps": "Write unit tests",
        },
    )
    assert not res_ckpt.is_error
    ckpt_data = extract_result(res_ckpt)
    assert ckpt_data["status"] == "checkpointed"

    # A second agent can recover a bounded handoff from the workspace graph.
    res_next_session = await mcp_app.call_tool(
        "session_start",
        {"agent_id": "test_agent_2", "workspace_id": mcp_workspace},
    )
    assert not res_next_session.is_error
    next_session = extract_result(res_next_session)
    res_handoff = await mcp_app.call_tool(
        "session_get_handoff",
        {
            "workspace_id": mcp_workspace,
            "exclude_session_id": next_session["id"],
        },
    )
    assert not res_handoff.is_error
    handoff = extract_result(res_handoff)["handoff"]
    assert handoff["id"] == session_id
    assert handoff["changed_files"] == ["src/worker.py"]
    assert handoff["test_outcomes"] == "8 passed"
    assert handoff["blockers"] == "Waiting for API contract approval"

    # 3. session_end
    res_end = await mcp_app.call_tool(
        "session_end",
        {
            "session_id": session_id,
            "workspace_id": mcp_workspace,
            "summary": "Completed milestone implementation successfully.",
        },
    )
    assert not res_end.is_error
    end_data = extract_result(res_end)
    assert end_data["status"] == "closed"


@pytest.mark.asyncio
async def test_mcp_memory_and_decision_tools(mcp_app, mcp_workspace):
    # 1. memory_save
    res_save = await mcp_app.call_tool(
        "memory_save",
        {
            "content": "FalkorDB stores graph attributes in optimized sparse matrices.",
            "workspace_id": mcp_workspace,
            "memory_type": "semantic",
            "confidence": 0.95,
            "source_ref": "docs/architecture.md",
            "evidence_content": "Benchmark verified 5x throughput improvement",
        },
    )
    assert not res_save.is_error
    mem = extract_result(res_save)
    mem_id = mem["id"]
    assert mem["version"] == 1

    # 2. memory_get
    res_get = await mcp_app.call_tool(
        "memory_get",
        {"memory_id": mem_id, "workspace_id": mcp_workspace},
    )
    assert not res_get.is_error
    get_data = extract_result(res_get)
    assert get_data["memory"]["id"] == mem_id
    assert len(get_data["provenance"]["supporting_evidence"]) >= 1

    # 3. decision_record
    res_dec = await mcp_app.call_tool(
        "decision_record",
        {
            "title": "Use exponential backoff with jitter",
            "rationale": "Prevents synchronized retry spikes during network blips.",
            "workspace_id": mcp_workspace,
            "alternatives_considered": ["Fixed delay", "No retry"],
            "evidence_content": "Simulated stress test proved 99.8% recovery",
            "author_id": "architect-agent",
        },
    )
    assert not res_dec.is_error
    dec = extract_result(res_dec)
    dec_id = dec["id"]
    assert dec_id.startswith("dec_")

    # 4. memory_search
    res_search = await mcp_app.call_tool(
        "memory_search",
        {
            "query": "exponential backoff retry strategy",
            "workspace_id": mcp_workspace,
        },
    )
    assert not res_search.is_error
    packet = extract_result(res_search)
    assert len(packet["decisions"]) >= 1
    assert "exponential backoff" in packet["decisions"][0]["title"].lower()

    # 5. memory_update (optimistic versioning)
    res_update = await mcp_app.call_tool(
        "memory_update",
        {
            "memory_id": mem_id,
            "expected_version": 1,
            "workspace_id": mcp_workspace,
            "new_content": "Updated verified claim regarding sparse matrix representation.",
        },
    )
    assert not res_update.is_error
    upd_data = extract_result(res_update)
    assert upd_data["version"] == 2

    # 6. memory_feedback
    res_fb = await mcp_app.call_tool(
        "memory_feedback",
        {
            "memory_id": mem_id,
            "rating": "useful",
            "workspace_id": mcp_workspace,
        },
    )
    assert not res_fb.is_error
    fb_data = extract_result(res_fb)
    assert fb_data["confidence"] >= 0.95
