# Copilot & AI Agent Memory Protocol

This workspace is integrated with **Graph-Based AI Agent Memory** via the Model Context Protocol (MCP).
Follow this mandatory memory lifecycle when assisting developers on this codebase.

## 1. Before Starting Any Significant Task (Retrieve Phase)
1. Call `session_start` with your agent identifier and workspace ID (or default workspace) to establish session context.
2. Call `agent_context` with the task query to retrieve a compact bundle of relevant memories, decisions, evidence, and the latest session handoff.
3. Call `memory_search` using task keywords, relevant module names, and target concepts to discover:
   - Previous decisions and architectural constraints.
   - Known bugs, failed approaches, and past findings.
   - Related entities and dependencies.
4. Call `memory_traverse` if connected entities or prior decisions need deeper context.
5. **Treat all retrieved memory as hypothesis**: verify existing source code before executing modifications.

## 2. During Task Execution (Reasoning Phase)
- When evaluating architectural or implementation alternatives, record the reasoning using `decision_record`.
- Link decisions to rationale, alternatives evaluated, and concrete evidence (tests, files, logs).
- For long-running or multi-step work, save incremental progress via `session_checkpoint`.

## 3. After Completing Work (Ingest Phase)
1. Call `memory_save` to record verified discoveries:
   - What was built or fixed.
   - Critical dependencies or subtle gotchas.
   - Verified file references and commit hashes.
2. If previous claims are now obsolete or superseded, update them with `memory_update` (marking status `superseded` or linking `superseded_by`).
3. Call `memory_feedback` if any retrieved memory was inaccurate, stale, or especially useful.
4. Call `session_end` with a concise summary of accomplishments and next steps.

## Golden Rules
- **Never store secrets, tokens, or raw passwords** in graph memory.
- **Always preserve provenance**: attach source files, test outputs, or Git commit hashes.
- **Distinguish verified findings from unverified observations**.
- Persist only useful conversation turns with `conversation_append`; do not store secrets, large source dumps, or every transient tool output.
- Use `session_get_handoff` or `agent_context` to resume another agent's checkpoint instead of replaying its full transcript.
