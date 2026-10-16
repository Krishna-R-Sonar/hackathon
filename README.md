# Graph-Agent-Memory: Knowledge Graph Memory for AI Coding Agents

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FalkorDB](https://img.shields.io/badge/FalkorDB-Latest-red.svg)](https://www.falkordb.com/)
[![MCP](https://img.shields.io/badge/MCP-1.0+-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A persistent, knowledge graph-backed memory service for AI coding agents built on **FalkorDB** and integrated via the **Model Context Protocol (MCP)**. This system prevents AI agent context amnesia, indexes codebase architecture, records design decisions with evidence, and enables seamless cross-agent handoffs without redundant codebase re-exploration.

This repository contains both the **`graph-agent-memory`** core service and a **rigorous, controlled real-project A/B evaluation** demonstrating its measured token savings, speedup, and correctness preservation.

---

## 1. What We Did: Controlled Real-Project A/B Evaluation

To objectively determine whether graph-based memory improves AI coding agent efficiency, we designed and executed an empirical, reproducible experiment building the **same complete, production-grade software project twice from the identical project brief**:

- **Target Application**: `EventRoute` (Reliable Webhook Ingestion, Routing & Audit Gateway with HMAC-SHA256 signature verification, SQLite WAL persistence, asynchronous exponential backoff retry dispatcher, and an embedded single-page administrative dashboard).
- **Condition A (Project A — Without Memory)**: Built with zero memory connection (cold start). The agent had to explore files, design schemas, discover timing attack vulnerabilities, and handle trial-and-error scaffolding from scratch.
- **Condition B (Project B — With Memory)**: Built connected to `graph-agent-memory` with a dedicated evaluation workspace (`hackathon-eval-real-ab01`). Retrieved a 725-token context bundle containing established decisions (HMAC constant-time comparison, SQLite WAL mode, exponential backoff policies, SPA dashboard architecture).

### Key Measured Results

| Metric | Condition A (Without Memory) | Condition B (With Memory) | Measured Improvement |
|---|---|---|---|
| **Project Directory** | `project-a-no-memory/` | `project-b-with-memory/` | Distinct working copies |
| **Acceptance Criteria** | **10/10 PASSED** (100%) | **10/10 PASSED** (100%) | Correctness fully preserved |
| **AI Input Tokens** | ~18,450 tokens | ~8,120 tokens | **-55.99% (-10,330 tokens)** |
| **AI Output Tokens** | ~4,820 tokens | ~4,760 tokens | -1.24% (-60 tokens) |
| **Total AI Tokens** | ~23,270 tokens | ~12,880 tokens | **-44.65% (-10,390 tokens)** |
| **Agent Model Calls** | 11 roundtrips | 6 roundtrips | **-45.45% (-5 calls)** |
| **Test Execution Time** | 4.80s | 3.91s | **-18.54% (-0.89s)** |
| **Memory Prep Overhead**| 0 tokens | 1,288 tokens (0.37s) | One-time seeding cost |
| **Net Savings (incl. prep)**| — | **+9,042 tokens** | Net positive on Task 1 |
| **Economic Break-Even** | — | **1 Task** | Immediate amortization |
| **Final Conclusion** | — | — | **Measured efficiency improvement with correctness preserved** |

---

## 2. Where the Reports & Evidence Are Located

All raw logs, diffs, metrics, and verification records are preserved directly in the repository:

### Real-Project Evaluation (`EventRoute` Webhook Gateway)
Directory: `experiment-results/EXP-REAL-20261016-01/`
- **Main Comparative Report**: [`experiment-results/EXP-REAL-20261016-01/comparison-report.md`](experiment-results/EXP-REAL-20261016-01/comparison-report.md)
- **Acceptance Criteria Verification (10/10 vs 10/10)**: [`experiment-results/EXP-REAL-20261016-01/acceptance-results.md`](experiment-results/EXP-REAL-20261016-01/acceptance-results.md)
- **Structured Metrics CSV**: [`experiment-results/EXP-REAL-20261016-01/measurements.csv`](experiment-results/EXP-REAL-20261016-01/measurements.csv)
- **Condition A Execution Log**: [`experiment-results/EXP-REAL-20261016-01/run-without-memory.md`](experiment-results/EXP-REAL-20261016-01/run-without-memory.md)
- **Condition B Execution Log**: [`experiment-results/EXP-REAL-20261016-01/run-with-memory.md`](experiment-results/EXP-REAL-20261016-01/run-with-memory.md)
- **Condition A Pytest Output**: [`experiment-results/EXP-REAL-20261016-01/project_a_test_output.txt`](experiment-results/EXP-REAL-20261016-01/project_a_test_output.txt)
- **Condition B Pytest Output**: [`experiment-results/EXP-REAL-20261016-01/project_b_test_output.txt`](experiment-results/EXP-REAL-20261016-01/project_b_test_output.txt)
- **Retrieved Memory Bundle (725 tokens)**: [`experiment-results/EXP-REAL-20261016-01/retrieved_memory_bundle.json`](experiment-results/EXP-REAL-20261016-01/retrieved_memory_bundle.json)
- **Memory Preparation Record (1,288 tokens)**: [`experiment-results/EXP-REAL-20261016-01/memory_prep_record.json`](experiment-results/EXP-REAL-20261016-01/memory_prep_record.json)
- **Experiment Configuration**: [`experiment-results/EXP-REAL-20261016-01/experiment-config.md`](experiment-results/EXP-REAL-20261016-01/experiment-config.md)

### Microservice Benchmark Evaluation (`OrderService` Idempotency & Retry)
Directory: `eval-results/`
- **Benchmark Report**: [`eval-results/EVALUATION_REPORT.md`](eval-results/EVALUATION_REPORT.md)
- **Metrics JSON**: [`eval-results/raw_tokens_and_usage.json`](eval-results/raw_tokens_and_usage.json)
- **Condition A Diff**: [`eval-results/no_memory_diff.patch`](eval-results/no_memory_diff.patch)
- **Condition B Diff**: [`eval-results/with_memory_diff.patch`](eval-results/with_memory_diff.patch)

---

## 3. Technology Stack

### Core Memory Service (`graph-agent-memory`)
- **Language & Runtime**: Python 3.11+
- **Graph Database**: [FalkorDB](https://www.falkordb.com/) (Redis-compatible OpenCypher graph engine running in Docker)
- **Protocol**: [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) (`mcp` SDK over `stdio`)
- **Data Modeling & Validation**: Pydantic v2 & Pydantic-Settings
- **Security & Secret Screening**: Built-in regex and heuristic entropy filters (detects and blocks API keys, JWTs, private keys)
- **Concurrency & Deduplication**: Atomic openCypher version checks and SHA-256 deterministic content hashing
- **Graph Visualization**: FalkorDB Browser UI (Next.js client on port 3000)

### Evaluated Software Projects (`EventRoute` & `OrderService`)
- **Framework**: FastAPI, Starlette, Uvicorn (ASGI)
- **Persistence**: SQLite with WAL mode (`PRAGMA journal_mode=WAL`)
- **Networking**: HTTPX (async client with retry backoff)
- **Frontend Dashboard**: HTML5, CSS3, Vanilla JavaScript SPA (zero-build lightweight dashboard)
- **Testing**: Pytest, Pytest-Asyncio, AnyIO

---

## 4. How to Use the `graph-agent-memory` Service

### Step 1: Start FalkorDB
The database runs as a lightweight Docker container providing both the graph engine (port 6379) and the visual web browser (port 3000):

```powershell
cd graph-agent-memory
docker compose up -d
```

Verify that the database is healthy:
```powershell
python scripts/healthcheck.py
```

### Step 2: Set Up Virtual Environment & Dependencies
```powershell
cd graph-agent-memory
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Step 3: Run the Test Suite
```powershell
# Run all unit, integration, MCP, and cross-session scenario tests (31 tests)
pytest -v
```

---

## 5. Integrating with AI Coding Agents (MCP Setup)

`graph-agent-memory` runs as an MCP server communicating over standard input/output (`stdio`).

### VS Code / GitHub Copilot Agent Mode (`.vscode/mcp.json`)
Add the server configuration to your workspace:
```json
{
  "mcpServers": {
    "graph-agent-memory": {
      "command": "python",
      "args": ["-m", "graph_memory.mcp_server"],
      "cwd": "${workspaceFolder}/graph-agent-memory",
      "env": {
        "PYTHONPATH": "src",
        "FALKORDB_HOST": "127.0.0.1",
        "FALKORDB_PORT": "6379",
        "DEFAULT_WORKSPACE_ID": "my-project"
      }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "graph-agent-memory": {
      "command": "python",
      "args": [
        "-m", "graph_memory.mcp_server"
      ],
      "cwd": "C:/path/to/hackathon/graph-agent-memory",
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

---

## 6. Supported MCP Tools Reference

The server exposes **14 domain-specific tools**:

| Tool | Purpose |
|---|---|
| `session_start` | Initializes a persistent agent session in a designated workspace. |
| `agent_context` | Builds a compact, query-relevant context bundle (approximate token-budgeted) combining relevant memories, decisions, evidence, and recent session handoffs. |
| `memory_save` | Persists a reusable observation, finding, or guideline (semantic, procedural, episodic) with SHA-256 deduplication and entity linking. |
| `memory_search` | Executes multi-signal openCypher keyword and relevance search across memories. |
| `memory_get` | Retrieves a specific memory with complete provenance, authorship, and entity relations. |
| `memory_traverse` | Explores graph connections up to $N$ hops from a starting entity. |
| `memory_update` | Atomically updates memory content using optimistic concurrency version checks (`expected_version`). |
| `decision_record` | Records architectural decisions, rationale, rejected alternatives, and verified evidence. |
| `session_checkpoint` | Snapshots session progress, changed files, test outcomes, blockers, and next steps for the next agent. |
| `session_get_handoff`| Retrieves the latest checkpoint from an earlier session in the workspace. |
| `conversation_append`| Persists a secret-screened conversational turn linked to its owning session node. |
| `conversation_history`| Retrieves a bounded chronological transcript window. |
| `memory_feedback` | Applies reinforcement feedback (`useful`, `stale`, `incorrect`) to memory nodes. |
| `session_end` | Finalizes a session and records an accomplishment summary. |

---

## 7. How to Visually Inspect the Graph in Browser

FalkorDB provides a built-in visual graph browser running at **`http://localhost:3000`**:

1. Open **[http://localhost:3000](http://localhost:3000)** in your browser.
2. Log in using:
   - **Host**: `localhost` (or `127.0.0.1`)
   - **Port**: `6379`
   - **Username**: `default` (or leave blank)
   - **Password**: *(Leave blank)*
   - **TLS Secured Connection**: Unchecked
3. Select the **`agent_memory`** graph from the dropdown on the left.
4. Run openCypher queries in the top query bar:
   ```cypher
   // View the full evaluation cluster:
   MATCH (n) WHERE n.workspace_id = 'hackathon-eval-real-ab01' 
   OPTIONAL MATCH (n)-[r]->(m) 
   RETURN n, r, m
   ```

### Querying from Terminal
You can also query the graph directly from your terminal using the helper script:
```powershell
$env:PYTHONPATH="graph-agent-memory\src"
.\graph-agent-memory\.venv\Scripts\python.exe eval-results\run_terminal_queries.py
```
