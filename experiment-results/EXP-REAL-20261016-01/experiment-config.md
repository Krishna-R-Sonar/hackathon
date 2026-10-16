# Experiment Configuration & Controls

- **Experiment ID**: `EXP-REAL-20261016-01`
- **Execution Date**: 2026-10-16 21:18:00 IST
- **Target Project**: `EventRoute` (Reliable Webhook Ingestion, Routing & Audit Gateway)
- **Model / Provider**: Gemini 3.8 Flash (High) via Antigravity Agent
- **Execution Environment**: Windows 11, Python 3.14 / 3.11+
- **Database Engine for Service**: SQLite 3 (WAL mode)
- **Memory Service**: `graph-agent-memory` over FalkorDB (`127.0.0.1:6379`)
- **Dedicated Memory Workspace ID**: `hackathon-eval-real-ab01`

## Working Copies
- **Condition A (Without Memory)**: `C:\Users\krish\OneDrive\Desktop\hackathon\project-a-no-memory`
- **Condition B (With Memory)**: `C:\Users\krish\OneDrive\Desktop\hackathon\project-b-with-memory`

## Experimental Controls
- Identical project brief, functional requirements, technical constraints, and acceptance criteria.
- Identical prompt instructions provided to both builds.
- Condition A has no connection to MCP memory, no prior conversation context, and no access to Condition B's artifacts.
- Condition B connects exclusively to workspace `hackathon-eval-real-ab01` using `agent_context`.
- Memory preparation performed in a distinct recorded session before Condition B.
- No secrets or credentials exposed or stored.
