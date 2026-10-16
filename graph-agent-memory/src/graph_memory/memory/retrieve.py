"""
Memory Retrieval Engine.
Implements bounded multi-signal graph search, relevance ranking, relationship traversal,
conflict detection, and context packet generation.
"""

from datetime import datetime, timezone
import logging
import math
import re
from typing import Any, Dict, List, Optional, Set

from graph_memory.config import settings
from graph_memory.db import FalkorDBClient, get_db
from graph_memory.models import (
    ContextPacket,
    MemorySearchInput,
    MemoryStatus,
)
from graph_memory.repositories.relationships import RelationshipRepository

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "by", "is", "it", "this", "that", "was", "be", "as", "are", "from", "how", "why", "what"
}


def extract_keywords(query: Optional[str]) -> List[str]:
    """Extracts non-stopword alphanumeric keywords from a search query."""
    if not query:
        return []
    words = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", query.lower())
    return [w for w in words if w not in STOPWORDS]


def compute_freshness(timestamp_str: Optional[str]) -> float:
    """Calculates a freshness factor between 0.5 and 1.0 based on elapsed days."""
    if not timestamp_str:
        return 0.7
    try:
        created = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        elapsed_days = max(0.0, (now - created).total_seconds() / 86400.0)
        # Half-life of 30 days, min floor of 0.5
        return max(0.5, math.exp(-0.02 * elapsed_days))
    except Exception:
        return 0.7


class RetrievalEngine:
    """Bounded, graph-aware memory search and ranking engine."""

    def __init__(self, db: Optional[FalkorDBClient] = None):
        self.db = db or get_db()
        self.rel_repo = RelationshipRepository(self.db)

    def search(self, search_input: MemorySearchInput, workspace_id: str) -> ContextPacket:
        """
        Executes bounded graph search and returns a structured ContextPacket.
        """
        query_text = search_input.query or ""
        keywords = extract_keywords(query_text)
        limit = min(search_input.limit, settings.max_retrieval_limit)

        # 1. Fetch Candidate Memories
        candidate_memories = self._fetch_candidate_memories(
            workspace_id=workspace_id,
            keywords=keywords,
            memory_type=search_input.memory_type.value if search_input.memory_type else None,
            entity_id=search_input.entity_id,
        )

        # 2. Fetch Relevant Decisions
        candidate_decisions = self._fetch_candidate_decisions(
            workspace_id=workspace_id,
            keywords=keywords,
        )

        # 3. Score and Rank Memories
        ranked_memories: List[Dict[str, Any]] = []
        conflicts_and_stale: List[Dict[str, Any]] = []
        failed_approaches: List[Dict[str, Any]] = []

        for mem in candidate_memories:
            props = mem["properties"]
            status = props.get("status", "active")
            content = props.get("content", "")

            # Check for failed approaches
            if "fail" in content.lower() or "error" in content.lower() or status == "disputed":
                if "fail" in content.lower():
                    failed_approaches.append(props)

            if status in (MemoryStatus.STALE.value, MemoryStatus.DISPUTED.value):
                conflicts_and_stale.append(props)
                continue  # Separate from primary verified findings

            if status == MemoryStatus.SUPERSEDED.value:
                continue  # Never return superseded claims in primary findings

            score = self._score_item(props, keywords, has_evidence=mem["has_evidence"])
            ranked_memories.append({
                **props,
                "score": score,
                "evidence": mem["evidence"],
                "connected_entities": mem["entities"],
            })

        ranked_memories.sort(key=lambda x: x["score"], reverse=True)
        top_memories = ranked_memories[:limit]

        # 4. Score and Rank Decisions
        ranked_decisions: List[Dict[str, Any]] = []
        for dec in candidate_decisions:
            props = dec["properties"]
            score = self._score_item(props, keywords, has_evidence=dec["has_evidence"], is_decision=True)
            ranked_decisions.append({
                **props,
                "score": score,
                "evidence": dec["evidence"],
            })
        ranked_decisions.sort(key=lambda x: x["score"], reverse=True)
        top_decisions = ranked_decisions[:limit]

        # 5. Extract Connected Entities across top memories & decisions
        connected_entities_map: Dict[str, Dict[str, Any]] = {}
        for m in top_memories:
            for ent in m.get("connected_entities", []):
                connected_entities_map[ent["id"]] = ent

        # 6. Extract Supporting Evidence
        all_evidence: List[Dict[str, Any]] = []
        for m in top_memories:
            all_evidence.extend(m.get("evidence", []))
        for d in top_decisions:
            all_evidence.extend(d.get("evidence", []))

        # Deduplicate evidence by ID
        unique_evidence = {e.get("id"): e for e in all_evidence if e.get("id")}

        # 7. Generate Next Steps Heuristics
        next_steps: List[str] = []
        if top_decisions:
            next_steps.append(f"Adhere to established decision: {top_decisions[0].get('title')}")
        if conflicts_and_stale:
            next_steps.append(f"Review and verify {len(conflicts_and_stale)} stale/disputed claim(s)")
        if not top_memories and not top_decisions:
            next_steps.append("No prior memories found for this task. Conduct initial investigation and save findings.")

        total_items = len(top_memories) + len(top_decisions) + len(unique_evidence)

        return ContextPacket(
            workspace_id=workspace_id,
            query=query_text,
            findings=top_memories,
            decisions=top_decisions,
            evidence=list(unique_evidence.values()),
            connected_entities=list(connected_entities_map.values()),
            failed_approaches=failed_approaches,
            conflicts_and_stale=conflicts_and_stale,
            suggested_next_steps=next_steps,
            total_items=total_items,
        )

    def _fetch_candidate_memories(
        self,
        workspace_id: str,
        keywords: List[str],
        memory_type: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries memories in the workspace with optional type and entity filtering."""
        where_clauses = ["m.workspace_id = $workspace_id"]
        params: Dict[str, Any] = {"workspace_id": workspace_id}

        if memory_type:
            where_clauses.append("m.memory_type = $memory_type")
            params["memory_type"] = memory_type

        if entity_id:
            where_clauses.append("(m)-[:RELATES_TO]->(:Entity {id: $entity_id})")
            params["entity_id"] = entity_id

        where_stmt = " AND ".join(where_clauses)
        cypher = f"""
        MATCH (m:Memory)
        WHERE {where_stmt}
        OPTIONAL MATCH (m)-[:SUPPORTED_BY]->(ev:Evidence)
        OPTIONAL MATCH (m)-[:RELATES_TO]->(e:Entity)
        RETURN m,
               collect(DISTINCT properties(ev)) AS evidence_list,
               collect(DISTINCT properties(e)) AS entity_list
        LIMIT 50
        """
        res = self.db.query(cypher, params, read_only=True)
        results = []
        for row in res.result_set:
            node = row[0]
            evidence = [e for e in row[1] if e]
            entities = [ent for ent in row[2] if ent]
            results.append({
                "properties": node.properties,
                "evidence": evidence,
                "has_evidence": bool(evidence),
                "entities": entities,
            })
        return results

    def _fetch_candidate_decisions(
        self,
        workspace_id: str,
        keywords: List[str],
    ) -> List[Dict[str, Any]]:
        """Queries decisions within the workspace along with attached evidence."""
        cypher = """
        MATCH (dec:Decision {workspace_id: $workspace_id})
        WHERE dec.status IN ['accepted', 'deprecated']
        OPTIONAL MATCH (dec)-[:SUPPORTED_BY]->(ev:Evidence)
        RETURN dec, collect(DISTINCT properties(ev)) AS evidence_list
        LIMIT 50
        """
        res = self.db.query(cypher, {"workspace_id": workspace_id}, read_only=True)
        results = []
        for row in res.result_set:
            node = row[0]
            evidence = [e for e in row[1] if e]
            results.append({
                "properties": node.properties,
                "evidence": evidence,
                "has_evidence": bool(evidence),
            })
        return results

    def _score_item(
        self,
        props: Dict[str, Any],
        keywords: List[str],
        has_evidence: bool = False,
        is_decision: bool = False,
    ) -> float:
        """
        Multi-signal ranking function:
        Score = (keyword_overlap * confidence * freshness * evidence_bonus)
        """
        text = (
            f"{props.get('title', '')} {props.get('content', '')} {props.get('rationale', '')}"
        ).lower()

        # 1. Keyword match ratio
        if not keywords:
            keyword_score = 0.5  # Neutral score when browsing without keyword
        else:
            matches = sum(1 for kw in keywords if kw in text)
            keyword_score = matches / len(keywords)

        # 2. Confidence multiplier
        confidence = float(props.get("confidence", 1.0))

        # 3. Freshness decay
        freshness = compute_freshness(props.get("created_at"))

        # 4. Evidence bonus (+25% bonus for verified backing facts)
        evidence_bonus = 1.25 if has_evidence else 1.0

        # Decisions receive slight architectural authority boost
        type_boost = 1.2 if is_decision else 1.0

        total_score = (keyword_score * 0.5 + 0.5) * confidence * freshness * evidence_bonus * type_boost
        return round(total_score, 4)
