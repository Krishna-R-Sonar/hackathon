"""
Memory Preparation Script for Condition B (with_memory).
Populates the dedicated evaluation workspace 'hackathon-eval-exp001'
in graph-agent-memory with domain architecture, patterns, decisions, and handoff.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add graph-agent-memory/src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "graph-agent-memory" / "src"))

from graph_memory.db import get_db
from graph_memory.mcp_server import create_mcp_server

WORKSPACE_ID = "hackathon-eval-exp001"


def extract_result(tool_result):
    if tool_result.structured_content and "result" in tool_result.structured_content:
        return tool_result.structured_content["result"]
    if tool_result.content and hasattr(tool_result.content[0], "text"):
        return json.loads(tool_result.content[0].text)
    return tool_result.structured_content or {}


async def prepare_memory():
    start_time = time.time()
    db = get_db()
    health = db.check_health()
    if health.get("status") != "healthy":
        print(f"Error: FalkorDB is not healthy: {health}")
        sys.exit(1)

    db.init_schema()

    # Clear workspace prior to clean preparation
    db.query("MATCH (n) WHERE n.workspace_id = $ws DETACH DELETE n", {"ws": WORKSPACE_ID})
    db.query("MERGE (w:Workspace {id: $ws, name: 'Evaluation Workspace exp001'})", {"ws": WORKSPACE_ID})

    server = create_mcp_server()
    calls = []
    
    # 1. session_start
    res1 = await server.call_tool("session_start", {
        "agent_id": "arch-prep-agent",
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_prep_001"
    })
    session_data = extract_result(res1)
    calls.append({"tool": "session_start", "result": session_data})

    # 2. decision_record: Idempotency Key Caching Policy
    res2 = await server.call_tool("decision_record", {
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_prep_001",
        "title": "Order Idempotency Key Caching Policy",
        "rationale": "To prevent duplicate order placements and double billing from network retries, clients provide an optional idempotency_key. If an order with that key already completed within the 10-minute cache window, the service immediately returns the cached completed Order without executing any stock reservation or payment processing again.",
        "alternatives_considered": ["Database unique constraint on order table", "Redis distributed lock per customer"],
        "status": "accepted"
    })
    decision_data = extract_result(res2)
    calls.append({"tool": "decision_record", "result": decision_data})

    # 3. memory_save: Procedural retry policy
    res3 = await server.call_tool("memory_save", {
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_prep_001",
        "memory_type": "procedural",
        "content": "When reserving inventory in OrderService, lock contention raises InventoryUnavailableError with is_transient=True. The service must automatically retry transient lock errors with exponential backoff (initial_delay=0.1s, backoff_factor=2.0, max_retries=3). Permanent stock exhaustion has is_transient=False and must not be retried.",
        "source_type": "file",
        "source_ref": "order_service/storage.py",
        "confidence": 1.0
    })
    memory_data1 = extract_result(res3)
    calls.append({"tool": "memory_save_retry_policy", "result": memory_data1})

    # 4. memory_save: Semantic audit logging requirement
    res4 = await server.call_tool("memory_save", {
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_prep_001",
        "memory_type": "semantic",
        "content": "Every order state transition must append an AuditLogEntry to order.audit_log with from_status, to_status, and message. When a retry succeeds after transient failures, an audit log entry with to_status='RETRIED' must be recorded before final completion.",
        "source_type": "file",
        "source_ref": "order_service/models.py",
        "confidence": 1.0
    })
    memory_data2 = extract_result(res4)
    calls.append({"tool": "memory_save_audit_policy", "result": memory_data2})

    # 5. session_checkpoint: Checkpoint with findings and next steps
    res5 = await server.call_tool("session_checkpoint", {
        "session_id": "sess_prep_001",
        "workspace_id": WORKSPACE_ID,
        "task_progress": "Architecture patterns for idempotency, retry backoff, and audit logging defined.",
        "changed_files": ["order_service/service.py", "order_service/storage.py", "order_service/models.py"],
        "verified_findings": [
            "Transient lock contention is marked by is_transient=True on InventoryUnavailableError.",
            "Idempotent cache must return existing completed order without inventory changes.",
            "Audit log records all state transitions including RETRIED."
        ],
        "test_outcomes": "Baseline tests passing 3/3",
        "next_steps": "Implement the idempotency cache, exponential backoff retry loop, and RETRIED audit logging."
    })
    checkpoint_data = extract_result(res5)
    calls.append({"tool": "session_checkpoint", "result": checkpoint_data})

    # 6. session_end
    res6 = await server.call_tool("session_end", {
        "session_id": "sess_prep_001",
        "workspace_id": WORKSPACE_ID,
        "summary": "Completed memory preparation with architectural patterns, decisions, and handoff state."
    })
    end_data = extract_result(res6)
    calls.append({"tool": "session_end", "result": end_data})

    elapsed = time.time() - start_time

    # Approximate prep token estimation
    total_prep_chars = sum(len(json.dumps(c, ensure_ascii=False)) for c in calls)
    prep_est_tokens = (total_prep_chars + 3) // 4

    prep_record = {
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_prep_001",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(elapsed, 3),
        "tool_call_count": len(calls),
        "total_payload_characters": total_prep_chars,
        "approx_prep_tokens": prep_est_tokens,
        "calls": calls
    }

    out_path = Path(__file__).resolve().parent / "prep_session_record.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(prep_record, f, indent=2)

    print(f"[SUCCESS] Prepared memory in workspace '{WORKSPACE_ID}'. Calls: {len(calls)}, Approx tokens: {prep_est_tokens}, Elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(prepare_memory())
