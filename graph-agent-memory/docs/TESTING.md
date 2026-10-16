# Testing Guide: Graph-Based AI Agent Memory

## 1. Test Architecture

The test suite is structured into four distinct layers:

| Layer | Directory | Description | External Dependencies |
|---|---|---|---|
| **Unit** | `tests/unit/` | Pure logic tests: models, validators, content hashing, deduplication logic, rankers, secret sanitizers. | None (runs in milliseconds). |
| **Integration**| `tests/integration/` | Database layer tests: FalkorDB connectivity, schema creation, Cypher queries, optimistic concurrency, workspace isolation. | Running FalkorDB container. |
| **MCP** | `tests/mcp/` | Model Context Protocol tests: tool registration, typed schema validation, stdio/in-memory handler calls. | FalkorDB (or configured test harness). |
| **Scenarios** | `tests/scenarios/` | Multi-session cross-agent memory, transcript, context, and handoff workflows. | Running FalkorDB container. |

---

## 2. Running Tests (PowerShell)

### Run Unit Tests Only (No Database Needed)
```powershell
.\.venv\Scripts\pytest tests/unit -v
```

### Start FalkorDB Container
```powershell
docker compose up -d
.\.venv\Scripts\python scripts/healthcheck.py
```

### Run All Tests (Including Integration & Scenarios)
```powershell
.\.venv\Scripts\pytest -v
```

### Run the End-to-End Acceptance Scenario
```powershell
.\.venv\Scripts\pytest tests/scenarios/test_cross_session_memory.py -v -s
```

### View Test Coverage
```powershell
.\.venv\Scripts\pytest --cov=graph_memory tests/
```
