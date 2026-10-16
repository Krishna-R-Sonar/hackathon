# Graph-Based AI Agent Memory System (FalkorDB + MCP)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FalkorDB](https://img.shields.io/badge/FalkorDB-Latest-red.svg)](https://www.falkordb.com/)
[![MCP](https://img.shields.io/badge/MCP-1.0+-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A persistent, knowledge graph-backed memory service for AI coding agents and engineering teams. Built on **FalkorDB** and integrated via the **Model Context Protocol (MCP)**, this service prevents context amnesia, indexes code relationships, records architectural decisions with evidence, and enables seamless cross-session collaboration without redundant codebase re-exploration.

---

## 1. Key Features

- **Knowledge Graph Core**: Uses FalkorDB and openCypher to preserve relationships between files, modules, decisions, tasks, sessions, and verifiable evidence.
- **MCP Native**: Exposes 14 typed MCP tools for seamless integration with GitHub Copilot agent mode, Antigravity, Claude Desktop, and compatible MCP clients.
- **Persistent Agent Memory**: Stores episodic conversation turns, semantic findings, and procedural memories across sessions.
- **Agent Handoffs**: Persists checkpoint details and lets the next agent retrieve workspace-scoped progress, tests, blockers, and next steps.
- **Compact Context**: `agent_context` bundles relevant graph memories, decisions, evidence, and handoff details within a configurable approximate token budget.
- **Concurrency & Deduplication**: Uses atomic optimistic version checks for memory and session updates and deterministic hashing for memory deduplication.
- **Strict Data Isolation**: Multi-tenant workspace partitioning ensures projects cannot read or corrupt each other's memories.
- **Zero Paid API Requirement**: Core retrieval engine operates using deterministic graph traversal, metadata indexing, and keyword relevance ranking.

---

## 2. Repository Structure

```
graph-agent-memory/
├── .github/
│   └── copilot-instructions.md    # Agent lifecycle instructions for Copilot
├── .vscode/
│   └── mcp.json                   # MCP client server definition for VS Code
├── config/
│   └── graph-schema.cypher        # FalkorDB openCypher schema and index setup
├── docs/
│   ├── ARCHITECTURE.md            # High-level architecture & design
│   ├── GRAPH_SCHEMA.md            # Schema, node types, and relationship specs
│   ├── MEMORY_LIFECYCLE.md        # State machine & optimistic concurrency
│   ├── SECURITY.md                # Secret prevention, Cypher safety, isolation
│   └── TESTING.md                 # Testing strategy and guide
├── src/
│   └── graph_memory/
│       ├── __init__.py
│       ├── config.py              # Environment and settings configuration
│       ├── db.py                  # FalkorDB connection, pooling & schema init
│       ├── models.py              # Pydantic domain models
│       ├── mcp_server.py          # MCP server & typed tool handlers
│       ├── memory/
│       │   ├── ingest.py          # Ingestion pipeline & validation
│       │   ├── retrieve.py        # Graph search & bounded traversal
│       │   ├── update.py          # Optimistic versioning & conflict checks
│       │   ├── provenance.py      # Authorship & session attribution
│       │   └── deduplicate.py     # Content hashing & duplicate resolution
│       └── repositories/
│           ├── nodes.py           # Node CRUD repository
│           └── relationships.py   # Relationship CRUD repository
├── tests/
│   ├── unit/                      # Unit tests (no DB required)
│   ├── integration/               # Database integration tests
│   ├── mcp/                       # MCP server protocol tests
│   └── scenarios/                 # Cross-session E2E acceptance tests
├── scripts/
│   ├── healthcheck.py             # FalkorDB health check script
│   └── seed_demo.py               # Seed demonstration data
├── docker-compose.yml             # FalkorDB Docker configuration
├── Dockerfile                     # Container definition for memory service
├── pyproject.toml                 # Package definition and dependencies
├── .env.sample                    # Safe environment configuration template
└── README.md
```

---

## 3. Quick Start (Windows 11 PowerShell)

### Prerequisites
- Python 3.11+
- Docker Desktop on Windows with WSL2

### Step 1: Clone & Create Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

### Step 2: Configure Environment
```powershell
if (-not (Test-Path .env)) { Copy-Item .env.sample .env } else { Write-Output ".env already exists; leaving it unchanged." }
```

`.env.sample` contains configuration keys and safe defaults only. Put credentials in `.env`, which is excluded from Git; never add secrets to the sample or commit `.env`.

### Step 3: Start FalkorDB
```powershell
docker compose up -d
```

Verify that the FalkorDB container is running and healthy:
```powershell
python scripts/healthcheck.py
```

### Step 4: Run Tests
```powershell
# Run unit tests
pytest tests/unit -v

# Run full test suite including DB integration and cross-session scenario
pytest -v
```

---

## 4. Model Context Protocol (MCP) Tools

The server exposes 14 structured tools over `stdio`:

1. `session_start` - Establish an active agent session in a workspace.
2. `memory_search` - Search workspace memories by keywords, tags, or entities.
3. `memory_get` - Fetch a single memory with complete provenance and links.
4. `memory_traverse` - Explore connected entities, decisions, and tasks up to $N$ hops.
5. `memory_save` - Validate and persist a memory with source references.
6. `memory_update` - Update memory content with optimistic version checking.
7. `decision_record` - Record an architectural decision with rationale and evidence.
8. `session_checkpoint` - Snapshot session progress, changed files, and blockers.
9. `session_end` - Finalize a session and record an overall summary.
10. `memory_feedback` - Provide reinforcement feedback (useful, stale, incorrect).
11. `conversation_append` - Persist a sanitized conversation turn linked to its session.
12. `conversation_history` - Retrieve a bounded, chronological transcript window.
13. `session_get_handoff` - Retrieve the latest checkpoint from another session in the workspace.
14. `agent_context` - Assemble relevant memories, decisions, evidence, and handoff into a compact context bundle.

### Track 02 workflow
1. Start a workspace session with `session_start`.
2. Append selected user/assistant/tool turns with `conversation_append`; the transcript is persisted in FalkorDB, not sent to an LLM by this service.
3. Before doing work, call `agent_context` with the task query to retrieve relevant memories and the latest handoff. It caps the returned context using `CONTEXT_TOKEN_BUDGET` (approximate character-based estimate, not tokenizer-exact).
4. Save reusable facts as `semantic` memories and repeatable methods as `procedural` memories with `memory_save`; attach source references and evidence.
5. Call `session_checkpoint` with verified findings, tests, blockers, changed files, and next steps. A later agent calls `session_get_handoff` or `agent_context` to resume without replaying the full transcript.

---

## 5. End-to-End Acceptance Scenario

`tests/scenarios/test_cross_session_memory.py` exercises the Track 02 flow:
1. **Session A**: Persists a procedural retry memory, a conversation turn, and a checkpoint.
2. **New agent instance**: A second MCP server instance is created against the same FalkorDB graph.
3. **Session B**: Retrieves compact task-relevant context, the checkpoint handoff, and Session A's saved transcript without replaying the entire conversation to a model.
