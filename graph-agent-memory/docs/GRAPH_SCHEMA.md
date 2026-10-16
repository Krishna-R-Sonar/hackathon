# Graph Schema & Data Model

This document specifies the openCypher graph schema implemented in FalkorDB for the AI Agent Memory System.

## 1. Node Definitions

### 1.1 `Workspace`
Defines an isolated administrative boundary (e.g., repository or project). All memories, decisions, and tasks are strictly partitioned by workspace.
- `id` (STRING, Primary): Unique workspace identifier (e.g., `graph-agent-memory`).
- `name` (STRING): Human-readable name.
- `description` (STRING, optional): Description of the project workspace.
- `created_at` (STRING): ISO-8601 creation timestamp.

### 1.2 `Developer`
Represents a human engineer interacting with the codebase or authoring decisions.
- `id` (STRING, Primary): Unique developer ID / username.
- `name` (STRING): Full name.
- `email` (STRING, optional): Contact email.

### 1.3 `Agent`
Represents an autonomous AI agent (e.g., Copilot, Antigravity, custom subagent).
- `id` (STRING, Primary): Agent identifier (e.g., `copilot-agent-v1`).
- `model` (STRING): Underlying foundation model (e.g., `gemini-pro`, `gpt-4o`).
- `role` (STRING): Configured agent persona / role.

### 1.4 `Session`
Represents a contiguous unit of agent or developer interaction.
- `id` (STRING, Primary): Unique session ID (e.g., `sess_a1b2c3d4`).
- `workspace_id` (STRING, Indexed): Associated workspace.
- `agent_id` (STRING): Agent conducting the session.
- `status` (STRING): `active`, `checkpointed`, `closed`.
- `started_at` (STRING): ISO-8601 start timestamp.
- `ended_at` (STRING, optional): ISO-8601 end timestamp.
- `last_checkpoint_at` (STRING, optional): ISO-8601 last checkpoint timestamp.
- `summary` (STRING, optional): Final summary of accomplishments.
- `changed_files`, `verified_findings` (LIST of STRING): Checkpoint information for agent handoffs.
- `test_outcomes`, `blockers`, `next_steps` (STRING, optional): Validation and coordination state.
- `version` (INTEGER): Optimistic concurrency version counter.

### 1.5 `ConversationMessage`
Stores an explicitly recorded conversation turn linked to one session.
- `id` (STRING, Primary): Idempotent message ID.
- `workspace_id`, `session_id` (STRING, Indexed): Owning workspace and session.
- `role` (STRING): `user`, `assistant`, `tool`, or `system`.
- `content` (STRING): Secret-screened message text.
- `created_at` (STRING): ISO-8601 timestamp.

### 1.6 `Memory`
Stores an individual observation, finding, or reusable knowledge item.
- `id` (STRING, Primary): Unique memory ID (e.g., `mem_9f8e7d6c`).
- `workspace_id` (STRING, Indexed): Owning workspace.
- `content` (STRING): Textual observation, finding, or guideline.
- `memory_type` (STRING): `episodic`, `semantic`, `procedural`, `observation`, `finding`, `feedback`.
- `status` (STRING): `active`, `stale`, `disputed`, `superseded`, `unverified`, `archived`.
- `confidence` (FLOAT): Confidence rating between 0.0 and 1.0.
- `source_type` (STRING): `file`, `session`, `test_run`, `git_commit`, `manual`, `agent`.
- `source_ref` (STRING): Pointer to file path, commit hash, or session ID.
- `author_id` (STRING): ID of the creating agent or developer.
- `author_type` (STRING): `agent` or `developer`.
- `session_id` (STRING): Originating session.
- `version` (INTEGER): Optimistic concurrency version counter (starts at 1).
- `superseded_by` (STRING, optional): ID of superseding memory.
- `valid_until` (STRING, optional): Expiration ISO-8601 timestamp.
- `created_at` (STRING): ISO-8601 timestamp.
- `updated_at` (STRING): ISO-8601 timestamp.

### 1.7 `Decision`
Records an architectural or design decision with rationale and evaluated alternatives.
- `id` (STRING, Primary): Unique decision ID (e.g., `dec_4a5b6c7d`).
- `workspace_id` (STRING, Indexed): Owning workspace.
- `title` (STRING): Short title (e.g., "Use exponential backoff for transient failures").
- `rationale` (STRING): Why this choice was selected.
- `alternatives_considered` (STRING / JSON): Alternatives evaluated and rejected.
- `status` (STRING): `accepted`, `rejected`, `deprecated`, `superseded`.
- `author_id` (STRING): Authoring agent or developer.
- `author_type` (STRING): `agent` or `developer`.
- `session_id` (STRING, optional): Associated session ID.
- `created_at` (STRING): ISO-8601 timestamp.
- `updated_at` (STRING): ISO-8601 timestamp.

### 1.8 `Entity`
Represents an architectural code artifact or domain concept (file, module, API, class, function).
- `id` (STRING, Primary): Unique entity key (e.g., `entity:src/graph_memory/db.py`).
- `workspace_id` (STRING, Indexed): Owning workspace.
- `name` (STRING, Indexed): Name (e.g., `db.py`, `FalkorDBClient`).
- `entity_type` (STRING): `file`, `module`, `class`, `function`, `service`, `api_endpoint`.
- `path` (STRING, optional): Relative file path.

### 1.9 `Task`
Tracks a task or milestone tackled by agents.
- `id` (STRING, Primary): Unique task ID (e.g., `task_01`).
- `workspace_id` (STRING, Indexed): Owning workspace.
- `title` (STRING): Task description.
- `status` (STRING): `pending`, `in_progress`, `completed`, `failed`, `blocked`.
- `created_at` (STRING): ISO-8601 timestamp.
- `updated_at` (STRING): ISO-8601 timestamp.

### 1.10 `Evidence`
Represents verifiable backing facts (test outputs, benchmarks, logs, commit diffs).
- `id` (STRING, Primary): Unique evidence ID (e.g., `evi_123`).
- `workspace_id` (STRING): Owning workspace.
- `evidence_type` (STRING): `test_result`, `benchmark`, `file_diff`, `log_output`, `doc_reference`.
- `content` (STRING): Verifiable snippet or summary.
- `source_uri` (STRING): URI, command, or file path.
- `verified` (BOOLEAN): True if programmatically confirmed.
- `created_at` (STRING): ISO-8601 timestamp.

---

## 2. Relationships

| Relationship | Source Label | Target Label | Description |
|---|---|---|---|
| `CONTAINS` | `Workspace` | `Memory`, `Decision`, `Entity`, `Task` | Workspace ownership boundary. |
| `HAS_SESSION` | `Workspace` | `Session` | Sessions initiated in workspace. |
| `HAS_MESSAGE` | `Session` | `ConversationMessage` | Persisted transcript turn owned by a session. |
| `PARTICIPATED_IN` | `Agent`, `Developer` | `Session` | Attribution of session participation. |
| `RECORDED` | `Session` | `Memory`, `Decision` | Artifacts recorded during session. |
| `RELATES_TO` | `Memory` | `Entity`, `Memory` | Contextual linkage between nodes. |
| `DEPENDS_ON` | `Entity`, `Task` | `Entity`, `Task` | Code or task dependencies. |
| `IMPLEMENTS` | `Entity` | `Decision`, `Task` | Code realizing a decision or task. |
| `DISCOVERED` | `Agent`, `Developer` | `Memory` | Discovery attribution. |
| `DECIDED` | `Agent`, `Developer` | `Decision` | Authorship attribution for decisions. |
| `SUPPORTED_BY` | `Memory`, `Decision` | `Evidence` | Verifiable backing evidence. |
| `SUPERSEDES` | `Memory`, `Decision` | `Memory`, `Decision` | Explicit deprecation and replacement. |
| `INVALIDATED_BY`| `Memory` | `Evidence`, `Memory` | Disproving or disputing a past claim. |

---

## 3. Index Specifications

All performance-critical lookup keys are indexed:
```cypher
CREATE INDEX FOR (w:Workspace) ON (w.id);
CREATE INDEX FOR (m:Memory) ON (m.id);
CREATE INDEX FOR (m:Memory) ON (m.workspace_id);
CREATE INDEX FOR (dec:Decision) ON (dec.id);
CREATE INDEX FOR (dec:Decision) ON (dec.workspace_id);
CREATE INDEX FOR (e:Entity) ON (e.id);
CREATE INDEX FOR (e:Entity) ON (e.workspace_id);
CREATE INDEX FOR (s:Session) ON (s.id);
CREATE INDEX FOR (s:Session) ON (s.workspace_id);
CREATE INDEX FOR (msg:ConversationMessage) ON (msg.id);
CREATE INDEX FOR (msg:ConversationMessage) ON (msg.workspace_id);
CREATE INDEX FOR (msg:ConversationMessage) ON (msg.session_id);
CREATE INDEX FOR (t:Task) ON (t.id);
CREATE INDEX FOR (ev:Evidence) ON (ev.id);
```
