"""
Repository for Node CRUD operations in FalkorDB.
Handles Workspace, Developer, Agent, Session, Memory, Decision, Entity, Task, and Evidence nodes.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from graph_memory.db import FalkorDBClient, get_db
from graph_memory.models import (
    WorkspaceModel,
    DeveloperModel,
    AgentModel,
    SessionModel,
    ConversationMessageModel,
    MemoryModel,
    DecisionModel,
    EntityModel,
    TaskModel,
    EvidenceModel,
    SessionStatus,
    MemoryStatus,
    DecisionStatus,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class ConcurrentModificationError(Exception):
    """Raised when an optimistic concurrency version check fails."""
    pass


class NodeNotFoundError(Exception):
    """Raised when a requested node is not found in the specified workspace."""
    pass


class NodeRepository:
    """Provides strongly typed CRUD operations for all node types in FalkorDB."""

    def __init__(self, db: Optional[FalkorDBClient] = None):
        self.db = db or get_db()

    # --- Workspace ---

    def ensure_workspace(self, workspace_id: str, name: Optional[str] = None) -> WorkspaceModel:
        """Idempotently creates or updates a Workspace node."""
        w_name = name or workspace_id
        cypher = """
        MERGE (w:Workspace {id: $id})
        ON CREATE SET w.name = $name, w.created_at = $created_at
        ON MATCH SET w.name = coalesce(w.name, $name)
        RETURN w
        """
        now = datetime.now(timezone.utc).isoformat()
        res = self.db.query(cypher, {"id": workspace_id, "name": w_name, "created_at": now})
        props = res.result_set[0][0].properties
        return WorkspaceModel(**props)

    def get_workspace(self, workspace_id: str) -> Optional[WorkspaceModel]:
        cypher = "MATCH (w:Workspace {id: $id}) RETURN w"
        res = self.db.query(cypher, {"id": workspace_id}, read_only=True)
        if not res.result_set:
            return None
        return WorkspaceModel(**res.result_set[0][0].properties)

    # --- Agent & Developer ---

    def ensure_agent(self, agent_id: str, model: str = "unknown", role: str = "assistant") -> AgentModel:
        cypher = """
        MERGE (a:Agent {id: $id})
        ON CREATE SET a.model = $model, a.role = $role
        RETURN a
        """
        res = self.db.query(cypher, {"id": agent_id, "model": model, "role": role})
        props = res.result_set[0][0].properties
        return AgentModel(**props)

    def ensure_developer(self, dev_id: str, name: str, email: Optional[str] = None) -> DeveloperModel:
        cypher = """
        MERGE (d:Developer {id: $id})
        ON CREATE SET d.name = $name, d.email = $email
        RETURN d
        """
        res = self.db.query(cypher, {"id": dev_id, "name": name, "email": email or ""})
        props = res.result_set[0][0].properties
        return DeveloperModel(**props)

    # --- Session ---

    def save_session(self, session: SessionModel) -> SessionModel:
        self.ensure_workspace(session.workspace_id)
        self.ensure_agent(session.agent_id)
        cypher = """
        MATCH (w:Workspace {id: $workspace_id})
        MATCH (a:Agent {id: $agent_id})
        MERGE (s:Session {id: $id, workspace_id: $workspace_id})
        ON CREATE SET
            s.started_at = $started_at,
            s.status = $status,
            s.agent_id = $agent_id,
            s.version = $version,
            s.summary = $summary,
            s.last_checkpoint_at = $last_checkpoint_at,
            s.changed_files = $changed_files,
            s.verified_findings = $verified_findings,
            s.test_outcomes = $test_outcomes,
            s.blockers = $blockers,
            s.next_steps = $next_steps
        ON MATCH SET
            s.status = $status,
            s.summary = $summary,
            s.ended_at = $ended_at,
            s.last_checkpoint_at = $last_checkpoint_at,
            s.changed_files = $changed_files,
            s.verified_findings = $verified_findings,
            s.test_outcomes = $test_outcomes,
            s.blockers = $blockers,
            s.next_steps = $next_steps
        MERGE (w)-[:HAS_SESSION]->(s)
        MERGE (a)-[:PARTICIPATED_IN]->(s)
        RETURN s
        """
        params = {
            "id": session.id,
            "workspace_id": session.workspace_id,
            "agent_id": session.agent_id,
            "version": session.version,
            "status": session.status.value,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "last_checkpoint_at": session.last_checkpoint_at,
            "summary": session.summary,
            "changed_files": session.changed_files,
            "verified_findings": session.verified_findings,
            "test_outcomes": session.test_outcomes,
            "blockers": session.blockers,
            "next_steps": session.next_steps,
        }
        res = self.db.query(cypher, params)
        props = res.result_set[0][0].properties
        return SessionModel(**props)

    def get_session(self, session_id: str, workspace_id: str) -> Optional[SessionModel]:
        cypher = "MATCH (s:Session {id: $id, workspace_id: $workspace_id}) RETURN s"
        res = self.db.query(cypher, {"id": session_id, "workspace_id": workspace_id}, read_only=True)
        if not res.result_set:
            return None
        return SessionModel(**res.result_set[0][0].properties)

    def update_session(
        self,
        session: SessionModel,
        expected_version: int,
    ) -> SessionModel:
        """Atomically updates session state and rejects stale concurrent writers."""
        cypher = """
        MATCH (s:Session {id: $id, workspace_id: $workspace_id})
        WHERE coalesce(s.version, 1) = $expected_version
        SET s.status = $status,
            s.summary = $summary,
            s.ended_at = $ended_at,
            s.last_checkpoint_at = $last_checkpoint_at,
            s.changed_files = $changed_files,
            s.verified_findings = $verified_findings,
            s.test_outcomes = $test_outcomes,
            s.blockers = $blockers,
            s.next_steps = $next_steps,
            s.version = coalesce(s.version, 1) + 1
        RETURN s
        """
        res = self.db.query(
            cypher,
            {
                "id": session.id,
                "workspace_id": session.workspace_id,
                "expected_version": expected_version,
                "status": session.status.value,
                "summary": session.summary,
                "ended_at": session.ended_at,
                "last_checkpoint_at": session.last_checkpoint_at,
                "changed_files": session.changed_files,
                "verified_findings": session.verified_findings,
                "test_outcomes": session.test_outcomes,
                "blockers": session.blockers,
                "next_steps": session.next_steps,
            },
        )
        if not res.result_set:
            if self.get_session(session.id, session.workspace_id) is None:
                raise NodeNotFoundError(
                    f"Session '{session.id}' not found in workspace '{session.workspace_id}'"
                )
            raise ConcurrentModificationError(
                f"Session '{session.id}' changed after version {expected_version} was read"
            )
        return SessionModel(**res.result_set[0][0].properties)

    def get_latest_handoff(
        self,
        workspace_id: str,
        exclude_session_id: Optional[str] = None,
    ) -> Optional[SessionModel]:
        """Returns the newest checkpointed or closed session in a workspace."""
        cypher = """
        MATCH (s:Session {workspace_id: $workspace_id})
        WHERE s.status IN ['checkpointed', 'closed']
          AND ($exclude_session_id IS NULL OR s.id <> $exclude_session_id)
        RETURN s
        ORDER BY coalesce(s.last_checkpoint_at, s.ended_at, s.started_at) DESC
        LIMIT 1
        """
        res = self.db.query(
            cypher,
            {"workspace_id": workspace_id, "exclude_session_id": exclude_session_id},
            read_only=True,
        )
        if not res.result_set:
            return None
        return SessionModel(**res.result_set[0][0].properties)

    def save_conversation_message(
        self,
        message: ConversationMessageModel,
    ) -> ConversationMessageModel:
        """Persists a transcript message only within its owning workspace session."""
        cypher = """
        MATCH (s:Session {id: $session_id, workspace_id: $workspace_id})
        MERGE (msg:ConversationMessage {id: $id, workspace_id: $workspace_id})
        ON CREATE SET
            msg.session_id = $session_id,
            msg.role = $role,
            msg.content = $content,
            msg.created_at = $created_at
        WITH s, msg
        WHERE msg.session_id = $session_id
        MERGE (s)-[:HAS_MESSAGE]->(msg)
        RETURN msg
        """
        res = self.db.query(
            cypher,
            {
                "id": message.id,
                "workspace_id": message.workspace_id,
                "session_id": message.session_id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at,
            },
        )
        if not res.result_set:
            raise NodeNotFoundError(
                f"Session '{message.session_id}' not found in workspace "
                f"'{message.workspace_id}', or message ID is already bound elsewhere"
            )
        saved = ConversationMessageModel(**res.result_set[0][0].properties)
        if (
            saved.session_id != message.session_id
            or saved.role != message.role
            or saved.content != message.content
        ):
            raise ValueError(
                f"Conversation message ID '{message.id}' already exists with different content"
            )
        return saved

    def get_conversation_history(
        self,
        session_id: str,
        workspace_id: str,
        limit: int = 50,
    ) -> List[ConversationMessageModel]:
        """Returns the latest bounded transcript window in chronological order."""
        bounded_limit = max(1, min(int(limit), 100))
        cypher = f"""
        MATCH (s:Session {{id: $session_id, workspace_id: $workspace_id}})
              -[:HAS_MESSAGE]->(msg:ConversationMessage {{workspace_id: $workspace_id}})
        RETURN msg
        ORDER BY msg.created_at DESC, msg.id DESC
        LIMIT {bounded_limit}
        """
        res = self.db.query(
            cypher,
            {
                "session_id": session_id,
                "workspace_id": workspace_id,
            },
            read_only=True,
        )
        messages = [
            ConversationMessageModel(**row[0].properties)
            for row in res.result_set
        ]
        return list(reversed(messages))

    # --- Memory ---

    def save_memory(self, memory: MemoryModel) -> MemoryModel:
        """Idempotently saves a Memory node linked to its Workspace."""
        self.ensure_workspace(memory.workspace_id)
        cypher = """
        MATCH (w:Workspace {id: $workspace_id})
        MERGE (m:Memory {id: $id, workspace_id: $workspace_id})
        ON CREATE SET
            m.content = $content,
            m.memory_type = $memory_type,
            m.status = $status,
            m.confidence = $confidence,
            m.source_type = $source_type,
            m.source_ref = $source_ref,
            m.author_id = $author_id,
            m.author_type = $author_type,
            m.session_id = $session_id,
            m.version = $version,
            m.superseded_by = $superseded_by,
            m.valid_until = $valid_until,
            m.content_hash = $content_hash,
            m.created_at = $created_at,
            m.updated_at = $updated_at
        ON MATCH SET
            m.content = $content,
            m.memory_type = $memory_type,
            m.status = $status,
            m.confidence = $confidence,
            m.source_type = $source_type,
            m.source_ref = $source_ref,
            m.updated_at = $updated_at
        MERGE (w)-[:CONTAINS]->(m)
        RETURN m
        """
        params = {
            "id": memory.id,
            "workspace_id": memory.workspace_id,
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "status": memory.status.value,
            "confidence": float(memory.confidence),
            "source_type": memory.source_type.value,
            "source_ref": memory.source_ref,
            "author_id": memory.author_id,
            "author_type": memory.author_type.value,
            "session_id": memory.session_id,
            "version": int(memory.version),
            "superseded_by": memory.superseded_by,
            "valid_until": memory.valid_until,
            "content_hash": memory.content_hash,
            "created_at": memory.created_at,
            "updated_at": memory.updated_at,
        }
        res = self.db.query(cypher, params)
        props = res.result_set[0][0].properties
        return MemoryModel(**props)

    def get_memory(self, memory_id: str, workspace_id: str) -> Optional[MemoryModel]:
        cypher = "MATCH (m:Memory {id: $id, workspace_id: $workspace_id}) RETURN m"
        res = self.db.query(cypher, {"id": memory_id, "workspace_id": workspace_id}, read_only=True)
        if not res.result_set:
            return None
        return MemoryModel(**res.result_set[0][0].properties)

    def update_memory(
        self,
        memory_id: str,
        workspace_id: str,
        expected_version: int,
        updates: Dict[str, Any],
    ) -> MemoryModel:
        """
        Updates a memory using optimistic concurrency control.
        Raises ConcurrentModificationError if the version does not match.
        """
        # First check if node exists
        existing = self.get_memory(memory_id, workspace_id)
        if not existing:
            raise NodeNotFoundError(f"Memory '{memory_id}' not found in workspace '{workspace_id}'")

        if existing.version != expected_version:
            raise ConcurrentModificationError(
                f"Conflict on memory '{memory_id}': expected version {expected_version}, but current version is {existing.version}"
            )

        now = datetime.now(timezone.utc).isoformat()
        new_version = expected_version + 1

        set_clauses = ["m.version = $new_version", "m.updated_at = $updated_at"]
        params: Dict[str, Any] = {
            "id": memory_id,
            "workspace_id": workspace_id,
            "expected_version": expected_version,
            "new_version": new_version,
            "updated_at": now,
        }

        if "content" in updates and updates["content"] is not None:
            set_clauses.append("m.content = $content")
            params["content"] = updates["content"]
        if "status" in updates and updates["status"] is not None:
            set_clauses.append("m.status = $status")
            params["status"] = updates["status"].value if hasattr(updates["status"], "value") else str(updates["status"])
        if "confidence" in updates and updates["confidence"] is not None:
            set_clauses.append("m.confidence = $confidence")
            params["confidence"] = float(updates["confidence"])
        if "superseded_by" in updates and updates["superseded_by"] is not None:
            set_clauses.append("m.superseded_by = $superseded_by")
            params["superseded_by"] = updates["superseded_by"]

        set_stmt = ", ".join(set_clauses)
        cypher = f"""
        MATCH (m:Memory {{id: $id, workspace_id: $workspace_id}})
        WHERE m.version = $expected_version
        SET {set_stmt}
        RETURN m
        """
        res = self.db.query(cypher, params)
        if not res.result_set:
            raise ConcurrentModificationError(
                f"Concurrent modification occurred on memory '{memory_id}' during commit."
            )
        props = res.result_set[0][0].properties
        return MemoryModel(**props)

    # --- Decision ---

    def save_decision(self, decision: DecisionModel) -> DecisionModel:
        self.ensure_workspace(decision.workspace_id)
        cypher = """
        MATCH (w:Workspace {id: $workspace_id})
        MERGE (dec:Decision {id: $id, workspace_id: $workspace_id})
        ON CREATE SET
            dec.title = $title,
            dec.rationale = $rationale,
            dec.alternatives_considered = $alternatives,
            dec.status = $status,
            dec.author_id = $author_id,
            dec.author_type = $author_type,
            dec.session_id = $session_id,
            dec.version = $version,
            dec.created_at = $created_at,
            dec.updated_at = $updated_at
        ON MATCH SET
            dec.title = $title,
            dec.rationale = $rationale,
            dec.alternatives_considered = $alternatives,
            dec.status = $status,
            dec.updated_at = $updated_at
        MERGE (w)-[:CONTAINS]->(dec)
        RETURN dec
        """
        params = {
            "id": decision.id,
            "workspace_id": decision.workspace_id,
            "title": decision.title,
            "rationale": decision.rationale,
            "alternatives": decision.alternatives_considered,
            "status": decision.status.value,
            "author_id": decision.author_id,
            "author_type": decision.author_type.value,
            "session_id": decision.session_id,
            "version": int(decision.version),
            "created_at": decision.created_at,
            "updated_at": decision.updated_at,
        }
        res = self.db.query(cypher, params)
        props = res.result_set[0][0].properties
        return DecisionModel(**props)

    def get_decision(self, decision_id: str, workspace_id: str) -> Optional[DecisionModel]:
        cypher = "MATCH (dec:Decision {id: $id, workspace_id: $workspace_id}) RETURN dec"
        res = self.db.query(cypher, {"id": decision_id, "workspace_id": workspace_id}, read_only=True)
        if not res.result_set:
            return None
        return DecisionModel(**res.result_set[0][0].properties)

    # --- Evidence ---

    def save_evidence(self, evidence: EvidenceModel) -> EvidenceModel:
        self.ensure_workspace(evidence.workspace_id)
        cypher = """
        MATCH (w:Workspace {id: $workspace_id})
        MERGE (ev:Evidence {id: $id, workspace_id: $workspace_id})
        ON CREATE SET
            ev.evidence_type = $evidence_type,
            ev.content = $content,
            ev.source_uri = $source_uri,
            ev.verified = $verified,
            ev.created_at = $created_at
        MERGE (w)-[:CONTAINS]->(ev)
        RETURN ev
        """
        params = {
            "id": evidence.id,
            "workspace_id": evidence.workspace_id,
            "evidence_type": evidence.evidence_type.value,
            "content": evidence.content,
            "source_uri": evidence.source_uri,
            "verified": evidence.verified,
            "created_at": evidence.created_at,
        }
        res = self.db.query(cypher, params)
        props = res.result_set[0][0].properties
        return EvidenceModel(**props)

    def get_evidence(self, evidence_id: str, workspace_id: str) -> Optional[EvidenceModel]:
        cypher = "MATCH (ev:Evidence {id: $id, workspace_id: $workspace_id}) RETURN ev"
        res = self.db.query(cypher, {"id": evidence_id, "workspace_id": workspace_id}, read_only=True)
        if not res.result_set:
            return None
        return EvidenceModel(**res.result_set[0][0].properties)

    # --- Entity ---

    def save_entity(self, entity: EntityModel) -> EntityModel:
        self.ensure_workspace(entity.workspace_id)
        cypher = """
        MATCH (w:Workspace {id: $workspace_id})
        MERGE (e:Entity {id: $id, workspace_id: $workspace_id})
        ON CREATE SET
            e.name = $name,
            e.entity_type = $entity_type,
            e.path = $path,
            e.properties_json = $properties_json
        ON MATCH SET
            e.name = $name,
            e.path = $path,
            e.properties_json = $properties_json
        MERGE (w)-[:CONTAINS]->(e)
        RETURN e
        """
        params = {
            "id": entity.id,
            "workspace_id": entity.workspace_id,
            "name": entity.name,
            "entity_type": entity.entity_type.value,
            "path": entity.path,
            "properties_json": json.dumps(entity.properties),
        }
        res = self.db.query(cypher, params)
        raw_props = res.result_set[0][0].properties
        props = dict(raw_props)
        if "properties_json" in props:
            props["properties"] = json.loads(props.pop("properties_json") or "{}")
        return EntityModel(**props)

    def get_entity(self, entity_id: str, workspace_id: str) -> Optional[EntityModel]:
        cypher = "MATCH (e:Entity {id: $id, workspace_id: $workspace_id}) RETURN e"
        res = self.db.query(cypher, {"id": entity_id, "workspace_id": workspace_id}, read_only=True)
        if not res.result_set:
            return None
        raw_props = res.result_set[0][0].properties
        props = dict(raw_props)
        if "properties_json" in props:
            props["properties"] = json.loads(props.pop("properties_json") or "{}")
        return EntityModel(**props)

    # --- Task ---

    def save_task(self, task: TaskModel) -> TaskModel:
        self.ensure_workspace(task.workspace_id)
        cypher = """
        MATCH (w:Workspace {id: $workspace_id})
        MERGE (t:Task {id: $id, workspace_id: $workspace_id})
        ON CREATE SET
            t.title = $title,
            t.status = $status,
            t.created_at = $created_at,
            t.updated_at = $updated_at
        ON MATCH SET
            t.title = $title,
            t.status = $status,
            t.updated_at = $updated_at
        MERGE (w)-[:CONTAINS]->(t)
        RETURN t
        """
        params = {
            "id": task.id,
            "workspace_id": task.workspace_id,
            "title": task.title,
            "status": task.status.value,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }
        res = self.db.query(cypher, params)
        props = res.result_set[0][0].properties
        return TaskModel(**props)

    def get_task(self, task_id: str, workspace_id: str) -> Optional[TaskModel]:
        cypher = "MATCH (t:Task {id: $id, workspace_id: $workspace_id}) RETURN t"
        res = self.db.query(cypher, {"id": task_id, "workspace_id": workspace_id}, read_only=True)
        if not res.result_set:
            return None
        return TaskModel(**res.result_set[0][0].properties)
