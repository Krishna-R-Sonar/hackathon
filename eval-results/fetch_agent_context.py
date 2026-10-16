"""
Test query to agent_context for Condition B.
Saves the retrieved context bundle into eval-results/retrieved_memory_bundle.json.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "graph-agent-memory" / "src"))

from graph_memory.mcp_server import create_mcp_server

WORKSPACE_ID = "hackathon-eval-exp001"


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
        "query": "implement idempotency retry backoff and audit log"
    })
    result = extract_result(res)
    
    out_path = Path(__file__).resolve().parent / "retrieved_memory_bundle.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        
    print(f"[SUCCESS] agent_context returned {len(result.get('context_items', []))} items. Estimated tokens: {result.get('estimated_tokens')}")


if __name__ == "__main__":
    asyncio.run(main())
