# System Architecture: Graph-Based AI Agent Memory

## 1. Overview & Vision
Modern AI coding assistants suffer from severe context amnesia:
- Each session restarts with zero persistent memory of earlier architectural evaluations.
- Agents re-read large codebases repeatedly, missing implicit relationships between files, components, and tasks.
- Prior decisions and rationale are forgotten, leading to recurring mistakes and conflicting approaches.

The **Graph-Based AI Agent Memory System** provides a shared, persistent, graph-backed memory substrate built on **FalkorDB** and surfaced through the **Model Context Protocol (MCP)**. It enables autonomous agents and developers to preserve, query, traverse, and evolve contextual knowledge across sessions and workflows.

## 2. Architectural Blueprint

```mermaid
flowchart TD
    subgraph Clients["Agents & Developers"]
        Copilot["VS Code / Copilot Agent"]
        CLI_Agent["CLI Agent / Antigravity"]
        Dev["Developer Scripts"]
    end

    subgraph MCP_Boundary["MCP Interface (stdio / SSE)"]
        MCPServer["MCP Server (mcp_server.py)\nTools: memory, transcript, context & handoff"]
    end

    subgraph Service_Core["Memory Service Core"]
        RetrievalEngine["Retrieval Engine (retrieve.py)\n- Bounded Traversal\n- Relevance & Freshness Ranking\n- Conflict & Staleness Filtering"]
        IngestionEngine["Ingestion Engine (ingest.py, update.py)\n- Normalization & Validation\n- Deduplication & Hash Checking\n- Optimistic Versioning"]
        ProvenanceTracker["Provenance Tracker (provenance.py)\n- Attribution (Agent/Dev)\n- Session & Source Linking\n- Evidence Verification"]
        Coordination["Session Coordination\n- Persistent transcript turns\n- Versioned checkpoints\n- Cross-agent handoffs"]
    end

    subgraph Repositories["Data Repositories"]
        NodeRepo["Node Repository (repositories/nodes.py)"]
        RelRepo["Relationship Repository (repositories/relationships.py)"]
        DBClient["FalkorDB Client & Pool (db.py)"]
    end

    subgraph Storage["Persistent Graph Store"]
        FalkorDB[("FalkorDB Container (Docker)\n- Port 6379 (Localhost)\n- AOF Append-Only Persistence\n- OpenCypher Graph Engine")]
        Volume[("Persistent Volume\nfalkordb_data")]
    end

    Copilot <-->|MCP Protocol (JSON-RPC)| MCPServer
    CLI_Agent <-->|MCP Protocol (JSON-RPC)| MCPServer
    Dev <-->|Direct Python API| Service_Core

    MCPServer --> RetrievalEngine
    MCPServer --> IngestionEngine
    MCPServer --> ProvenanceTracker
    MCPServer --> Coordination

    RetrievalEngine --> NodeRepo
    RetrievalEngine --> RelRepo
    IngestionEngine --> NodeRepo
    IngestionEngine --> RelRepo
    ProvenanceTracker --> NodeRepo
    ProvenanceTracker --> RelRepo
    Coordination --> NodeRepo

    NodeRepo --> DBClient
    RelRepo --> DBClient
    DBClient -->|TCP / RESP3 Cypher| FalkorDB
    FalkorDB --- Volume
```

## 3. Core Subsystems

### 3.1 Persistence & Data Layer (`db.py`, `repositories/`)
- Uses official `falkordb` Python client with connection pooling and retry safety.
- Exposes strict, parameterized Cypher queries to prevent injection attacks.
- Manages schema creation, node indexing, and transactional boundaries.

### 3.2 Domain Models (`models.py`)
- Pydantic v2 schemas providing runtime type checking and serialization.
- Distinct types for episodic memories, semantic knowledge, architectural decisions, entities, tasks, sessions, and verifiable evidence.
- Enforces workspace isolation via mandatory `workspace_id` attributes.

### 3.3 Memory Ingestion & Update Pipeline (`memory/ingest.py`, `memory/update.py`)
- Follows the lifecycle: `Capture -> Validate -> Normalize -> Deduplicate -> Conflict Resolution -> Persist -> Verify`.
- Employs deterministic content hashing for deduplication.
- Protects against concurrent lost updates via optimistic concurrency version control.
- Distinguishes active, unverified, disputed, stale, and superseded memories.

### 3.4 Contextual Retrieval & Graph Traversal (`memory/retrieve.py`)
- Multi-signal ranking algorithm combining keyword relevance, temporal decay, validity intervals, confidence scores, and verified evidence bonuses.
- Bounded BFS/DFS traversal exploring connected entities, dependent modules, and historical decisions up to configurable hop limits.
- Generates a compact, budget-aware `ContextPacket` preventing token overflow.

### 3.5 Model Context Protocol Integration (`mcp_server.py`)
- Standardized tool interface following official MCP specification (`mcp` SDK).
- Transport over stdio for local editor integration (e.g., VS Code Copilot agent mode).
- Clean separation between protocol messages (stdout) and structured diagnostic telemetry (stderr).
- Offers a compact query-specific context bundle and session handoff tools so clients can retrieve selected knowledge rather than replaying full transcripts.

### 3.6 Session Coordination
- Conversation turns are persisted as workspace-scoped graph nodes linked to their owning session.
- Checkpoints retain changed files, verified findings, test outcomes, blockers, and next steps.
- Session mutations use version-checked writes; stale concurrent updates fail rather than silently overwriting newer handoffs.
