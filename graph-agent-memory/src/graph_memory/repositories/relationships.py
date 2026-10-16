"""
Repository for Relationship management and graph traversals in FalkorDB.
Handles relationships such as CONTAINS, RELATES_TO, DEPENDS_ON, IMPLEMENTS,
SUPPORTED_BY, SUPERSEDES, INVALIDATED_BY, and multi-hop traversals.
"""

import logging
from typing import Any, Dict, List, Optional
from graph_memory.db import FalkorDBClient, get_db

logger = logging.getLogger(__name__)

# Permitted relationship types to prevent arbitrary Cypher token injection
ALLOWED_RELATIONSHIPS = {
    "CONTAINS",
    "HAS_SESSION",
    "PARTICIPATED_IN",
    "RECORDED",
    "RELATES_TO",
    "DEPENDS_ON",
    "IMPLEMENTS",
    "DISCOVERED",
    "DECIDED",
    "SUPPORTED_BY",
    "SUPERSEDES",
    "INVALIDATED_BY",
}


class RelationshipRepository:
    """Manages relationships and traversals between graph nodes."""

    def __init__(self, db: Optional[FalkorDBClient] = None):
        self.db = db or get_db()

    def create_relationship(
        self,
        src_id: str,
        rel_type: str,
        dest_id: str,
        props: Optional[Dict[str, Any]] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        """
        Creates an edge between src_id and dest_id with strict relationship type validation
        and workspace boundary checks.
        """
        clean_rel = rel_type.upper().strip()
        if clean_rel not in ALLOWED_RELATIONSHIPS:
            raise ValueError(f"Disallowed relationship type: '{clean_rel}'. Must be one of {sorted(ALLOWED_RELATIONSHIPS)}")

        props_map = props or {}

        if workspace_id:
            cypher = f"""
            MATCH (a {{id: $src_id}}), (b {{id: $dest_id}})
            WHERE (a.workspace_id = $workspace_id OR a.workspace_id IS NULL)
              AND (b.workspace_id = $workspace_id OR b.workspace_id IS NULL)
            MERGE (a)-[r:{clean_rel}]->(b)
            SET r += $props
            RETURN type(r)
            """
            params = {
                "src_id": src_id,
                "dest_id": dest_id,
                "workspace_id": workspace_id,
                "props": props_map,
            }
        else:
            cypher = f"""
            MATCH (a {{id: $src_id}}), (b {{id: $dest_id}})
            MERGE (a)-[r:{clean_rel}]->(b)
            SET r += $props
            RETURN type(r)
            """
            params = {
                "src_id": src_id,
                "dest_id": dest_id,
                "props": props_map,
            }

        res = self.db.query(cypher, params)
        return bool(res.result_set)

    def link_memory_to_entity(self, memory_id: str, entity_id: str, workspace_id: str) -> bool:
        return self.create_relationship(memory_id, "RELATES_TO", entity_id, workspace_id=workspace_id)

    def link_decision_to_evidence(self, decision_id: str, evidence_id: str, workspace_id: str) -> bool:
        return self.create_relationship(decision_id, "SUPPORTED_BY", evidence_id, workspace_id=workspace_id)

    def link_memory_to_evidence(self, memory_id: str, evidence_id: str, workspace_id: str) -> bool:
        return self.create_relationship(memory_id, "SUPPORTED_BY", evidence_id, workspace_id=workspace_id)

    def link_supersession(self, new_id: str, old_id: str, workspace_id: str) -> bool:
        return self.create_relationship(new_id, "SUPERSEDES", old_id, workspace_id=workspace_id)

    def link_invalidation(self, memory_id: str, invalidator_id: str, workspace_id: str) -> bool:
        return self.create_relationship(memory_id, "INVALIDATED_BY", invalidator_id, workspace_id=workspace_id)

    def get_related_nodes(
        self,
        node_id: str,
        workspace_id: str,
        rel_type: Optional[str] = None,
        direction: str = "both",
    ) -> List[Dict[str, Any]]:
        """Returns 1-hop connected nodes within the same workspace."""
        arrow_in = "<-[r]" if direction in ("incoming", "both") else "-[r]"
        arrow_out = "->(target)" if direction in ("outgoing", "both") else "-(target)"

        rel_filter = ""
        if rel_type:
            clean_rel = rel_type.upper().strip()
            if clean_rel not in ALLOWED_RELATIONSHIPS:
                raise ValueError(f"Invalid relationship filter: {clean_rel}")
            rel_filter = f":{clean_rel}"

        if direction == "outgoing":
            pattern = f"(start {{id: $node_id}})-[r{rel_filter}]->(target)"
        elif direction == "incoming":
            pattern = f"(start {{id: $node_id}})<-[r{rel_filter}]-(target)"
        else:
            pattern = f"(start {{id: $node_id}})-[r{rel_filter}]-(target)"

        cypher = f"""
        MATCH {pattern}
        WHERE target.workspace_id = $workspace_id AND target.id <> $node_id
        RETURN DISTINCT target.id AS id, labels(target) AS labels, type(r) AS rel_type, properties(target) AS props
        LIMIT 50
        """
        res = self.db.query(cypher, {"node_id": node_id, "workspace_id": workspace_id}, read_only=True)
        results = []
        for row in res.result_set:
            results.append({
                "id": row[0],
                "labels": row[1],
                "relationship": row[2],
                "properties": row[3],
            })
        return results

    def traverse(
        self,
        start_id: str,
        workspace_id: str,
        max_depth: int = 2,
        rel_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Performs bounded graph traversal up to max_depth hops starting from start_id.
        Constrained strictly to the specified workspace_id.
        """
        depth = max(1, min(max_depth, 4))
        capped_limit = max(1, min(limit, 50))

        rel_spec = ""
        if rel_types:
            validated_types = [t.upper().strip() for t in rel_types if t.upper().strip() in ALLOWED_RELATIONSHIPS]
            if validated_types:
                rel_spec = ":" + "|".join(validated_types)

        cypher = f"""
        MATCH path = (start {{id: $start_id}})-[{rel_spec}*1..{depth}]-(target)
        WHERE (target.workspace_id = $workspace_id) AND (target.id <> $start_id)
        RETURN DISTINCT target.id AS id, labels(target) AS labels, length(path) AS depth, properties(target) AS props
        ORDER BY depth ASC
        LIMIT {capped_limit}
        """

        res = self.db.query(cypher, {"start_id": start_id, "workspace_id": workspace_id}, read_only=True)
        results = []
        for row in res.result_set:
            results.append({
                "id": row[0],
                "labels": row[1],
                "depth": row[2],
                "properties": row[3],
            })
        return results
