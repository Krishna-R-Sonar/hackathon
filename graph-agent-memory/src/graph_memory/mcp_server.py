"""
Model Context Protocol (MCP) Server for Graph-Based AI Agent Memory.
Exposes 10 domain-specific tools over stdio transport.
Diagnostic logs are written strictly to sys.stderr, while protocol frames write to stdout.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any, Dict, List, Optional
import uuid

from mcp.server.mcpserver import MCPServer

from graph_memory.config import settings
from graph_memory.db import get_db
from graph_memory.memory.ingest import IngestionEngine
from graph_memory.memory.provenance import ProvenanceTracker
from graph_memory.memory.retrieve import RetrievalEngine
from graph_memory.memory.update import UpdateManager
from graph_memory.models import (
    AuthorType,
    ConversationMessageModel,
    DecisionRecordInput,
    DecisionStatus,
    FeedbackRating,
    MemoryFeedbackInput,
    MemorySaveInput,
    MemorySearchInput,
    MemoryStatus,
    MemoryTraverseInput,
    MemoryType,
    MemoryUpdateInput,
    SessionCheckpointInput,
    SessionEndInput,
    SessionModel,
    SessionStartInput,
    SessionStatus,
    SourceType,
    current_iso_timestamp,
)
from graph_memory.repositories.nodes import (
    NodeRepository,
    ConcurrentModificationError,
    NodeNotFoundError,
)
from graph_memory.repositories.relationships import RelationshipRepository

# Configure logging strictly to sys.stderr
logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("graph_memory.mcp")


def create_mcp_server() -> MCPServer:
    """Constructs and registers the memory, transcript, and coordination tools."""
    server = MCPServer(settings.mcp_server_name)
    db = get_db()
    node_repo = NodeRepository(db)
    rel_repo = RelationshipRepository(db)
    ingest_engine = IngestionEngine(db)
    retrieve_engine = RetrievalEngine(db)
    update_mgr = UpdateManager(db)
    provenance_tracker = ProvenanceTracker(db)

    def _resolve_workspace(ws_id: Optional[str]) -> str:
        return (ws_id.strip() if ws_id and ws_id.strip() else settings.default_workspace_id)

    # 1. memory_search
    @server.tool(name="memory_search", description="Search workspace-scoped memories by task, keywords, metadata, and optional entity references.")
    def memory_search(
        query: Optional[str] = None,
        workspace_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        status: Optional[str] = "active",
        limit: int = 10,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        m_type = MemoryType(memory_type) if memory_type else None
        m_status = MemoryStatus(status) if status else MemoryStatus.ACTIVE
        search_input = MemorySearchInput(
            query=query,
            workspace_id=ws,
            entity_id=entity_id,
            memory_type=m_type,
            status=m_status,
            limit=limit,
        )
        packet = retrieve_engine.search(search_input, workspace_id=ws)
        return packet.model_dump()

    # 2. memory_get
    @server.tool(name="memory_get", description="Retrieve a specific memory together with relevant provenance, author, and relationships.")
    def memory_get(
        memory_id: str,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        mem = node_repo.get_memory(memory_id, ws)
        if not mem:
            return {"error": f"Memory '{memory_id}' not found in workspace '{ws}'"}

        prov = provenance_tracker.get_provenance(memory_id, ws)
        related = rel_repo.get_related_nodes(memory_id, ws)
        return {
            "memory": mem.model_dump(),
            "provenance": prov,
            "related_nodes": related,
        }

    # 3. memory_traverse
    @server.tool(name="memory_traverse", description="Traverse a bounded number of graph relationships from specified entities or memories.")
    def memory_traverse(
        start_node_id: str,
        workspace_id: Optional[str] = None,
        max_depth: int = 2,
        relationship_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        traversed = rel_repo.traverse(
            start_id=start_node_id,
            workspace_id=ws,
            max_depth=max_depth,
            rel_types=relationship_types,
            limit=limit,
        )
        return {
            "start_node_id": start_node_id,
            "workspace_id": ws,
            "traversed_nodes": traversed,
            "count": len(traversed),
        }

    # 4. memory_save
    @server.tool(name="memory_save", description="Validate and persist a memory with provenance and optional entity links.")
    def memory_save(
        content: str,
        workspace_id: Optional[str] = None,
        memory_type: str = "finding",
        confidence: float = 1.0,
        source_type: str = "agent",
        source_ref: str = "unknown",
        entity_ids: Optional[List[str]] = None,
        evidence_content: Optional[str] = None,
        session_id: Optional[str] = None,
        author_id: Optional[str] = None,
        author_type: str = "agent",
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        input_data = MemorySaveInput(
            workspace_id=ws,
            content=content,
            memory_type=MemoryType(memory_type.lower()),
            confidence=confidence,
            source_type=SourceType(source_type.lower()),
            source_ref=source_ref,
            entity_ids=entity_ids,
            evidence_content=evidence_content,
            session_id=session_id,
            author_id=author_id,
            author_type=AuthorType(author_type.lower()),
        )
        saved = ingest_engine.ingest_memory(input_data, workspace_id=ws)
        return saved.model_dump()

    # 5. memory_update
    @server.tool(name="memory_update", description="Update an existing memory using version checks and conflict protection.")
    def memory_update(
        memory_id: str,
        expected_version: int,
        workspace_id: Optional[str] = None,
        new_content: Optional[str] = None,
        new_status: Optional[str] = None,
        new_confidence: Optional[float] = None,
        superseded_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        input_data = MemoryUpdateInput(
            memory_id=memory_id,
            workspace_id=ws,
            expected_version=expected_version,
            new_content=new_content,
            new_status=MemoryStatus(new_status) if new_status else None,
            new_confidence=new_confidence,
            superseded_by=superseded_by,
        )
        try:
            updated = update_mgr.update_memory(input_data, workspace_id=ws)
            return updated.model_dump()
        except ConcurrentModificationError as e:
            return {"error": "Conflict", "message": str(e), "status_code": 409}
        except NodeNotFoundError as e:
            return {"error": "NotFound", "message": str(e), "status_code": 404}

    # 6. decision_record
    @server.tool(name="decision_record", description="Save a decision, its rationale, alternatives, evidence, author, and status.")
    def decision_record(
        title: str,
        rationale: str,
        workspace_id: Optional[str] = None,
        alternatives_considered: Optional[List[str]] = None,
        evidence_content: Optional[str] = None,
        evidence_source: Optional[str] = "session",
        session_id: Optional[str] = None,
        author_id: Optional[str] = None,
        author_type: str = "agent",
        status: str = "accepted",
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        input_data = DecisionRecordInput(
            workspace_id=ws,
            title=title,
            rationale=rationale,
            alternatives_considered=alternatives_considered or [],
            evidence_content=evidence_content,
            evidence_source=evidence_source,
            session_id=session_id,
            author_id=author_id,
            author_type=AuthorType(author_type.lower()),
            status=DecisionStatus(status.lower()),
        )
        saved = ingest_engine.ingest_decision(input_data, workspace_id=ws)
        return saved.model_dump()

    # 7. session_start
    @server.tool(name="session_start", description="Create a persistent session for an agent and workspace.")
    def session_start(
        agent_id: str,
        workspace_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        s_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        now = current_iso_timestamp()
        model = SessionModel(
            id=s_id,
            workspace_id=ws,
            agent_id=agent_id,
            status=SessionStatus.ACTIVE,
            started_at=now,
        )
        saved = node_repo.save_session(model)
        return saved.model_dump()

    # 8. session_checkpoint
    @server.tool(name="session_checkpoint", description="Save task progress, changed files, verified findings, test outcomes, blockers, and next steps.")
    def session_checkpoint(
        session_id: str,
        task_progress: str,
        workspace_id: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
        verified_findings: Optional[List[str]] = None,
        test_outcomes: Optional[str] = None,
        blockers: Optional[str] = None,
        next_steps: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        checkpoint = SessionCheckpointInput(
            session_id=session_id,
            workspace_id=ws,
            task_progress=task_progress,
            changed_files=changed_files,
            verified_findings=verified_findings,
            test_outcomes=test_outcomes,
            blockers=blockers,
            next_steps=next_steps,
        )
        existing = node_repo.get_session(session_id, ws)
        if not existing:
            return {"error": f"Session '{session_id}' not found in workspace '{ws}'"}

        now = current_iso_timestamp()
        existing.status = SessionStatus.CHECKPOINTED
        existing.last_checkpoint_at = now
        existing.summary = checkpoint.task_progress
        existing.changed_files = checkpoint.changed_files or []
        existing.verified_findings = checkpoint.verified_findings or []
        existing.test_outcomes = checkpoint.test_outcomes
        existing.blockers = checkpoint.blockers
        existing.next_steps = checkpoint.next_steps
        node_repo.update_session(existing, expected_version=existing.version)

        # Ingest findings if provided in checkpoint
        if checkpoint.verified_findings:
            for item in checkpoint.verified_findings:
                ingest_engine.ingest_memory(
                    MemorySaveInput(
                        content=item,
                        workspace_id=ws,
                        memory_type=MemoryType.FINDING,
                        session_id=session_id,
                        author_id=existing.agent_id,
                    ),
                    workspace_id=ws,
                )

        return {
            "session_id": session_id,
            "status": "checkpointed",
            "last_checkpoint_at": now,
            "task_progress": checkpoint.task_progress,
            "changed_files": checkpoint.changed_files or [],
            "verified_findings_count": len(checkpoint.verified_findings or []),
            "test_outcomes": checkpoint.test_outcomes,
            "blockers": checkpoint.blockers,
            "next_steps": checkpoint.next_steps,
        }

    # 9. session_end
    @server.tool(name="session_end", description="Close a session and record a final summary without discarding its history.")
    def session_end(
        session_id: str,
        summary: str,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        end_input = SessionEndInput(
            session_id=session_id,
            workspace_id=ws,
            summary=summary,
        )
        existing = node_repo.get_session(session_id, ws)
        if not existing:
            return {"error": f"Session '{session_id}' not found in workspace '{ws}'"}

        now = current_iso_timestamp()
        existing.status = SessionStatus.CLOSED
        existing.ended_at = now
        existing.summary = end_input.summary
        saved = node_repo.update_session(existing, expected_version=existing.version)
        return saved.model_dump()

    # 10. memory_feedback
    @server.tool(name="memory_feedback", description="Record whether a retrieved memory was useful, stale, or incorrect.")
    def memory_feedback(
        memory_id: str,
        rating: str,
        workspace_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        try:
            fb_rating = FeedbackRating(rating.lower())
            updated = update_mgr.apply_feedback(
                memory_id=memory_id,
                workspace_id=ws,
                rating=fb_rating,
                notes=notes,
            )
            return updated.model_dump()
        except Exception as e:
            return {"error": "FeedbackFailed", "message": str(e)}

    # 11. conversation_append
    @server.tool(
        name="conversation_append",
        description="Persist a user, assistant, tool, or system turn in a workspace session for cross-session memory.",
    )
    def conversation_append(
        session_id: str,
        role: str,
        content: str,
        workspace_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        message = ConversationMessageModel(
            id=message_id or f"msg_{uuid.uuid4().hex}",
            workspace_id=ws,
            session_id=session_id,
            role=role,
            content=content,
        )
        saved = node_repo.save_conversation_message(message)
        return saved.model_dump()

    # 12. conversation_history
    @server.tool(
        name="conversation_history",
        description="Retrieve the latest bounded conversation window for a session, in chronological order.",
    )
    def conversation_history(
        session_id: str,
        workspace_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        if not node_repo.get_session(session_id, ws):
            return {"error": f"Session '{session_id}' not found in workspace '{ws}'"}
        messages = node_repo.get_conversation_history(session_id, ws, limit=limit)
        return {
            "session_id": session_id,
            "workspace_id": ws,
            "messages": [message.model_dump() for message in messages],
            "count": len(messages),
        }

    # 13. session_get_handoff
    @server.tool(
        name="session_get_handoff",
        description="Retrieve the latest checkpoint from another session in this workspace for agent handoff and coordination.",
    )
    def session_get_handoff(
        workspace_id: Optional[str] = None,
        exclude_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        handoff = node_repo.get_latest_handoff(ws, exclude_session_id)
        return {
            "workspace_id": ws,
            "handoff": handoff.model_dump() if handoff else None,
        }

    # 14. agent_context
    @server.tool(
        name="agent_context",
        description="Build a compact, query-relevant context bundle from workspace memories, decisions, evidence, and the latest agent handoff.",
    )
    def agent_context(
        query: str,
        workspace_id: Optional[str] = None,
        exclude_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _resolve_workspace(workspace_id)
        packet = retrieve_engine.search(
            MemorySearchInput(
                query=query,
                workspace_id=ws,
                limit=settings.max_retrieval_limit,
            ),
            workspace_id=ws,
        )
        context_items: List[Dict[str, Any]] = []

        handoff = node_repo.get_latest_handoff(ws, exclude_session_id)
        if handoff:
            context_items.append({
                "type": "handoff",
                "session_id": handoff.id,
                "summary": (handoff.summary or "")[:400],
                "changed_files": handoff.changed_files[:10],
                "verified_findings": [item[:300] for item in handoff.verified_findings[:10]],
                "test_outcomes": (handoff.test_outcomes or "")[:300],
                "blockers": (handoff.blockers or "")[:300],
                "next_steps": (handoff.next_steps or "")[:300],
            })

        for decision in packet.decisions:
            evidence = decision.get("evidence", [])
            context_items.append({
                "type": "decision",
                "id": decision.get("id"),
                "title": (decision.get("title") or "")[:200],
                "rationale": (decision.get("rationale") or "")[:400],
                "evidence": [
                    {
                        "id": item.get("id"),
                        "source_uri": item.get("source_uri"),
                        "content": (item.get("content") or "")[:240],
                    }
                    for item in evidence[:1]
                ],
            })

        for finding in packet.findings:
            entities = finding.get("connected_entities", [])
            evidence = finding.get("evidence", [])
            context_items.append({
                "type": "memory",
                "id": finding.get("id"),
                "memory_type": finding.get("memory_type"),
                "content": (finding.get("content") or "")[:600],
                "source_ref": finding.get("source_ref"),
                "related_entities": [entity.get("name") for entity in entities[:3]],
                "evidence": [
                    {
                        "id": item.get("id"),
                        "source_uri": item.get("source_uri"),
                        "content": (item.get("content") or "")[:240],
                    }
                    for item in evidence[:1]
                ],
            })

        selected: List[Dict[str, Any]] = []
        estimated_tokens = 0
        token_budget = settings.context_token_budget
        omitted_items = 0
        for item in context_items:
            item_tokens = max(
                1,
                (len(json.dumps(item, ensure_ascii=False)) + 3) // 4,
            )
            if estimated_tokens + item_tokens <= token_budget:
                selected.append(item)
                estimated_tokens += item_tokens
            else:
                omitted_items += 1

        return {
            "workspace_id": ws,
            "query": query[:300],
            "context_items": selected,
            "estimated_tokens": estimated_tokens,
            "token_budget": token_budget,
            "token_estimation": "JSON character count divided by 4; approximate, not model-tokenizer exact",
            "omitted_items": omitted_items,
            "suggested_next_steps": [step[:200] for step in packet.suggested_next_steps[:5]],
        }

    return server


def main() -> None:
    """Launches the MCP Server on stdio transport."""
    server = create_mcp_server()
    logger.info("Initializing Graph-Based AI Agent Memory MCP Server on stdio transport...")
    try:
        # Initialize database schema on startup
        db = get_db()
        db.init_schema()
        logger.info("Database schema validated.")
        server.run(transport="stdio")
    except Exception as e:
        logger.error("Fatal error running MCP Server: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
