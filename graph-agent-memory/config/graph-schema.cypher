// ==============================================================================
// Graph Schema Definitions & Indexes for FalkorDB
// Graph: agent_memory
// ==============================================================================

// --- Node Type Indexes ---

// 1. Workspace
CREATE INDEX FOR (w:Workspace) ON (w.id);

// 2. Developer
CREATE INDEX FOR (d:Developer) ON (d.id);

// 3. Agent
CREATE INDEX FOR (a:Agent) ON (a.id);

// 4. Session
CREATE INDEX FOR (s:Session) ON (s.id);
CREATE INDEX FOR (s:Session) ON (s.workspace_id);

// 5. Conversation Message
CREATE INDEX FOR (msg:ConversationMessage) ON (msg.id);
CREATE INDEX FOR (msg:ConversationMessage) ON (msg.workspace_id);
CREATE INDEX FOR (msg:ConversationMessage) ON (msg.session_id);

// 6. Memory
CREATE INDEX FOR (m:Memory) ON (m.id);
CREATE INDEX FOR (m:Memory) ON (m.workspace_id);
CREATE INDEX FOR (m:Memory) ON (m.status);
CREATE INDEX FOR (m:Memory) ON (m.memory_type);

// 7. Decision
CREATE INDEX FOR (dec:Decision) ON (dec.id);
CREATE INDEX FOR (dec:Decision) ON (dec.workspace_id);
CREATE INDEX FOR (dec:Decision) ON (dec.status);

// 8. Entity
CREATE INDEX FOR (e:Entity) ON (e.id);
CREATE INDEX FOR (e:Entity) ON (e.workspace_id);
CREATE INDEX FOR (e:Entity) ON (e.name);
CREATE INDEX FOR (e:Entity) ON (e.entity_type);

// 9. Task
CREATE INDEX FOR (t:Task) ON (t.id);
CREATE INDEX FOR (t:Task) ON (t.workspace_id);
CREATE INDEX FOR (t:Task) ON (t.status);

// 10. Evidence
CREATE INDEX FOR (ev:Evidence) ON (ev.id);
CREATE INDEX FOR (ev:Evidence) ON (ev.workspace_id);
