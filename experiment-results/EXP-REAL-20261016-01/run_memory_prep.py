"""
Memory Preparation Session for Condition B (hackathon-eval-real-ab01).
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add graph-agent-memory/src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "graph-agent-memory" / "src"))

from graph_memory.db import get_db
from graph_memory.mcp_server import create_mcp_server

WORKSPACE_ID = "hackathon-eval-real-ab01"


def extract_result(tool_result):
    if tool_result.structured_content and "result" in tool_result.structured_content:
        return tool_result.structured_content["result"]
    if tool_result.content and hasattr(tool_result.content[0], "text"):
        return json.loads(tool_result.content[0].text)
    return tool_result.structured_content or {}


async def main():
    start_time = time.time()
    db = get_db()
    health = db.check_health()
    if health.get("status") != "healthy":
        print(f"Error: FalkorDB is unhealthy: {health}")
        sys.exit(1)

    db.init_schema()

    # Reset workspace cleanly
    db.query("MATCH (n) WHERE n.workspace_id = $ws DETACH DELETE n", {"ws": WORKSPACE_ID})
    db.query("MERGE (w:Workspace {id: $ws, name: 'EventRoute Real Evaluation Workspace'})", {"ws": WORKSPACE_ID})

    server = create_mcp_server()
    calls = []

    # 1. session_start
    r1 = await server.call_tool("session_start", {
        "agent_id": "arch-lead-agent",
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_eventroute_prep"
    })
    calls.append({"tool": "session_start", "result": extract_result(r1)})

    # 2. decision_record: HMAC-SHA256
    r2 = await server.call_tool("decision_record", {
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_eventroute_prep",
        "title": "HMAC-SHA256 Signature Header & Timing Attack Prevention",
        "rationale": "Inbound webhooks must be verified using X-Signature-256 header with HMAC-SHA256. To prevent timing attacks, comparisons must use constant-time hmac.compare_digest rather than standard equality operators.",
        "alternatives_considered": ["JWT tokens in Authorization header", "Plain shared API key"],
        "status": "accepted"
    })
    calls.append({"tool": "decision_record_hmac", "result": extract_result(r2)})

    # 3. memory_save: Retry policy
    r3 = await server.call_tool("memory_save", {
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_eventroute_prep",
        "memory_type": "procedural",
        "content": "Webhook dispatch to target URLs must implement exponential backoff on HTTP 5xx responses or timeouts: initial_delay=0.1s, backoff_factor=2.0, max_retries=3. Permanent HTTP 4xx client errors must be marked as FAILED immediately without retry to avoid hammering bad endpoints.",
        "source_type": "file",
        "source_ref": "docs/DISPATCH_POLICY.md",
        "confidence": 1.0
    })
    calls.append({"tool": "memory_save_retry", "result": extract_result(r3)})

    # 4. memory_save: SQLite WAL mode and schema
    r4 = await server.call_tool("memory_save", {
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_eventroute_prep",
        "memory_type": "semantic",
        "content": "SQLite delivery storage should use WAL mode (PRAGMA journal_mode=WAL) to allow concurrent non-blocking reads from the dashboard while delivery worker writes event logs. Schema requires event_id, source_id, topic, payload, idempotency_key, status (DELIVERED, RETRYING, FAILED), and attempts count.",
        "source_type": "file",
        "source_ref": "docs/STORAGE_SPEC.md",
        "confidence": 1.0
    })
    calls.append({"tool": "memory_save_storage", "result": extract_result(r4)})

    # 5. decision_record: Embedded Dashboard SPA
    r5 = await server.call_tool("decision_record", {
        "workspace_id": WORKSPACE_ID,
        "session_id": "sess_eventroute_prep",
        "title": "Embedded Lightweight SPA Dashboard Architecture",
        "rationale": "To avoid complex Node/NPM build chains while fulfilling frontend requirements, serve a self-contained vanilla HTML/CSS/JavaScript dashboard directly from FastAPI static files mounted at root / with REST API polling for live status.",
        "alternatives_considered": ["React/Next.js frontend in separate container", "Server-rendered Jinja templates only"],
        "status": "accepted"
    })
    calls.append({"tool": "decision_record_frontend", "result": extract_result(r5)})

    # 6. session_checkpoint
    r6 = await server.call_tool("session_checkpoint", {
        "session_id": "sess_eventroute_prep",
        "workspace_id": WORKSPACE_ID,
        "task_progress": "Core architecture, security validation policies, and persistence design established for EventRoute gateway.",
        "changed_files": ["app/main.py", "app/security.py", "app/storage.py", "app/dispatcher.py", "static/index.html"],
        "verified_findings": [
            "Constant-time HMAC comparison prevents timing attacks",
            "WAL mode enables concurrent dashboard reads during delivery writes",
            "4xx errors abort immediately while 5xx retry with backoff"
        ],
        "test_outcomes": "Architectural specifications confirmed",
        "next_steps": "Build EventRoute webhook gateway with ingestion, dispatcher, SQLite storage, and dashboard UI."
    })
    calls.append({"tool": "session_checkpoint", "result": extract_result(r6)})

    # 7. session_end
    r7 = await server.call_tool("session_end", {
        "session_id": "sess_eventroute_prep",
        "workspace_id": WORKSPACE_ID,
        "summary": "Completed memory preparation for EventRoute A/B evaluation."
    })
    calls.append({"tool": "session_end", "result": extract_result(r7)})

    elapsed = time.time() - start_time
    total_chars = sum(len(json.dumps(c, ensure_ascii=False)) for c in calls)
    approx_tokens = (total_chars + 3) // 4

    out_data = {
        "session_id": "sess_eventroute_prep",
        "workspace_id": WORKSPACE_ID,
        "tool_call_count": len(calls),
        "elapsed_seconds": round(elapsed, 3),
        "total_payload_characters": total_chars,
        "approx_prep_tokens": approx_tokens,
        "calls": calls
    }

    out_path = Path(__file__).resolve().parent / "memory_prep_record.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print(f"[SUCCESS] Prepared memory for {WORKSPACE_ID}. Calls: {len(calls)}, Approx tokens: {approx_tokens}, Time: {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
