"""
Fetch memory bundle for Condition B from workspace hackathon-eval-real-ab01.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add graph-agent-memory/src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "graph-agent-memory" / "src"))

from graph_memory.mcp_server import create_mcp_server

WORKSPACE_ID = "hackathon-eval-real-ab01"


def extract_result(tool_result):
    if tool_result.structured_content and "result" in tool_result.structured_content:
        return tool_result.structured_content["result"]
    if tool_result.content and hasattr(tool_result.content[0], "text"):
        return json.loads(tool_result.content[0].text)
    return tool_result.structured_content or {}


async def main():
    server = create_mcp_server()
    res = await server.call_tool("agent_context", {
        "workspace_id": WORKSPACE_ID,
        "query": "EventRoute webhook gateway HMAC signature verification retry backoff SQLite WAL dashboard"
    })
    result = extract_result(res)

    out_path = Path(__file__).resolve().parent / "retrieved_memory_bundle.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"[SUCCESS] Retrieved {len(result.get('context_items', []))} items from {WORKSPACE_ID}. Approx tokens: {result.get('estimated_tokens')}")


if __name__ == "__main__":
    asyncio.run(main())
