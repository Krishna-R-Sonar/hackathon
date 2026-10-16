"""
Provenance tracking and audit module.
Records authorship, session origins, source file/commit references, and supporting evidence.
"""

from typing import Any, Dict, List, Optional
from graph_memory.db import FalkorDBClient, get_db
from graph_memory.models import AuthorType
from graph_memory.repositories.nodes import NodeRepository
from graph_memory.repositories.relationships import RelationshipRepository


class ProvenanceTracker:
    """Manages and inspects provenance metadata and audit trails across graph nodes."""

    def __init__(self, db: Optional[FalkorDBClient] = None):
        self.db = db or get_db()
        self.node_repo = NodeRepository(self.db)
        self.rel_repo = RelationshipRepository(self.db)

    def attach_authorship(
        self,
        node_id: str,
        author_id: str,
        author_type: AuthorType,
        workspace_id: str,
        rel_type: str = "DISCOVERED",
    ) -> None:
        """Links an Agent or Developer to a created Memory or Decision."""
        if author_type == AuthorType.AGENT:
            self.node_repo.ensure_agent(author_id)
            self.rel_repo.create_relationship(author_id, rel_type, node_id, workspace_id=workspace_id)
        else:
            self.node_repo.ensure_developer(author_id, name=author_id)
            self.rel_repo.create_relationship(author_id, rel_type, node_id, workspace_id=workspace_id)

    def attach_session(self, session_id: str, node_id: str, workspace_id: str) -> None:
        """Links an originating session to a recorded artifact with RECORDED."""
        self.rel_repo.create_relationship(session_id, "RECORDED", node_id, workspace_id=workspace_id)

    def get_provenance(self, node_id: str, workspace_id: str) -> Dict[str, Any]:
        """
        Retrieves the complete provenance tree for a memory or decision:
        authorship, session origin, supporting evidence, and supersession chain.
        """
        cypher = """
        MATCH (target {id: $id, workspace_id: $workspace_id})
        OPTIONAL MATCH (author)-[r_auth:DISCOVERED|DECIDED]->(target)
        OPTIONAL MATCH (sess:Session)-[:RECORDED]->(target)
        OPTIONAL MATCH (target)-[:SUPPORTED_BY]->(ev:Evidence)
        OPTIONAL MATCH (target)-[:SUPERSEDES]->(prior)
        OPTIONAL MATCH (newer)-[:SUPERSEDES]->(target)
        RETURN target,
               properties(author) AS author_props,
               labels(author) AS author_labels,
               properties(sess) AS session_props,
               collect(DISTINCT properties(ev)) AS evidence_list,
               collect(DISTINCT prior.id) AS supersedes_ids,
               collect(DISTINCT newer.id) AS superseded_by_ids
        """
        res = self.db.query(cypher, {"id": node_id, "workspace_id": workspace_id}, read_only=True)
        if not res.result_set:
            return {}

        row = res.result_set[0]
        target_node = row[0]
        author_props = row[1]
        author_labels = row[2]
        session_props = row[3]
        evidence_list = row[4] or []
        supersedes_ids = [s for s in row[5] if s is not None]
        superseded_by_ids = [s for s in row[6] if s is not None]

        return {
            "node_id": node_id,
            "workspace_id": workspace_id,
            "node_type": target_node.labels[0] if target_node.labels else "Unknown",
            "properties": target_node.properties,
            "author": {
                "id": author_props.get("id") if author_props else target_node.properties.get("author_id"),
                "type": author_labels[0] if author_labels else target_node.properties.get("author_type"),
                "details": author_props,
            },
            "originating_session": session_props,
            "supporting_evidence": evidence_list,
            "supersedes": supersedes_ids,
            "superseded_by": superseded_by_ids,
            "created_at": target_node.properties.get("created_at"),
            "updated_at": target_node.properties.get("updated_at"),
            "version": target_node.properties.get("version", 1),
        }
