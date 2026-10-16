"""
Memory ingestion pipeline module.
Executes the mandatory lifecycle:
Capture -> Validate -> Normalize -> Deduplicate -> Conflict Resolution -> Persist -> Verify.
"""

from datetime import datetime, timezone
import logging
from typing import Optional
import uuid

from graph_memory.db import FalkorDBClient, get_db
from graph_memory.models import (
    AuthorType,
    DecisionModel,
    DecisionRecordInput,
    EvidenceModel,
    EvidenceType,
    MemoryModel,
    MemorySaveInput,
    MemoryStatus,
    current_iso_timestamp,
)
from graph_memory.memory.deduplicate import DeduplicationEngine, compute_content_hash, normalize_content
from graph_memory.memory.provenance import ProvenanceTracker
from graph_memory.repositories.nodes import NodeRepository
from graph_memory.repositories.relationships import RelationshipRepository

logger = logging.getLogger(__name__)


class IngestionEngine:
    """Orchestrates memory and decision ingestion with deduplication and provenance linking."""

    def __init__(self, db: Optional[FalkorDBClient] = None):
        self.db = db or get_db()
        self.node_repo = NodeRepository(self.db)
        self.rel_repo = RelationshipRepository(self.db)
        self.dedup_engine = DeduplicationEngine(self.db)
        self.provenance = ProvenanceTracker(self.db)

    def ingest_memory(self, input_data: MemorySaveInput, workspace_id: str) -> MemoryModel:
        """
        Ingests a new memory following the 7-step lifecycle.
        """
        # Step 1 & 2: Capture & Validate (handled by Pydantic models & secret validator)
        raw_content = input_data.content.strip()

        # Step 3: Normalize
        norm_content = normalize_content(raw_content)
        content_hash = compute_content_hash(raw_content, workspace_id, input_data.memory_type)

        # Step 4: Deduplicate
        existing_dup = self.dedup_engine.find_duplicate(
            content=raw_content,
            workspace_id=workspace_id,
            memory_type=input_data.memory_type,
        )
        if existing_dup:
            logger.info("Deduplication matched existing memory: %s", existing_dup.id)
            # Idempotently reinforce existing memory
            now = current_iso_timestamp()
            updated = self.node_repo.update_memory(
                memory_id=existing_dup.id,
                workspace_id=workspace_id,
                expected_version=existing_dup.version,
                updates={
                    "confidence": min(1.0, existing_dup.confidence + 0.05),
                },
            )
            return updated

        # Step 5: Conflict Resolution (New memory creation)
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        now = current_iso_timestamp()

        author_id = input_data.author_id or "system"
        author_type = input_data.author_type or AuthorType.AGENT

        mem_model = MemoryModel(
            id=memory_id,
            workspace_id=workspace_id,
            content=raw_content,
            memory_type=input_data.memory_type,
            status=MemoryStatus.ACTIVE,
            confidence=input_data.confidence,
            source_type=input_data.source_type,
            source_ref=input_data.source_ref,
            author_id=author_id,
            author_type=author_type,
            session_id=input_data.session_id,
            version=1,
            content_hash=content_hash,
            created_at=now,
            updated_at=now,
        )

        # Step 6: Persist
        saved = self.node_repo.save_memory(mem_model)

        # Attach Provenance & Links
        self.provenance.attach_authorship(
            node_id=saved.id,
            author_id=author_id,
            author_type=author_type,
            workspace_id=workspace_id,
            rel_type="DISCOVERED",
        )

        if input_data.session_id:
            self.provenance.attach_session(
                session_id=input_data.session_id,
                node_id=saved.id,
                workspace_id=workspace_id,
            )

        if input_data.entity_ids:
            for ent_id in input_data.entity_ids:
                self.rel_repo.link_memory_to_entity(saved.id, ent_id, workspace_id)

        if input_data.evidence_content:
            evidence_id = f"evi_{uuid.uuid4().hex[:10]}"
            evidence_model = EvidenceModel(
                id=evidence_id,
                workspace_id=workspace_id,
                evidence_type=EvidenceType.TEST_RESULT,
                content=input_data.evidence_content,
                source_uri=input_data.source_ref,
                verified=True,
                created_at=now,
            )
            self.node_repo.save_evidence(evidence_model)
            self.rel_repo.link_memory_to_evidence(saved.id, evidence_id, workspace_id)

        # Step 7: Verify Read-Back
        verified = self.node_repo.get_memory(saved.id, workspace_id)
        if not verified:
            raise RuntimeError(f"Post-write verification failed for memory '{saved.id}'")

        return verified

    def ingest_decision(self, input_data: DecisionRecordInput, workspace_id: str) -> DecisionModel:
        """
        Persists an architectural decision with rationale, alternatives, and backing evidence.
        """
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        now = current_iso_timestamp()

        author_id = input_data.author_id or "system"
        author_type = input_data.author_type or AuthorType.AGENT

        dec_model = DecisionModel(
            id=decision_id,
            workspace_id=workspace_id,
            title=input_data.title.strip(),
            rationale=input_data.rationale.strip(),
            alternatives_considered=input_data.alternatives_considered or [],
            status=input_data.status,
            author_id=author_id,
            author_type=author_type,
            session_id=input_data.session_id,
            version=1,
            created_at=now,
            updated_at=now,
        )

        saved = self.node_repo.save_decision(dec_model)

        # Attach Authorship & Session
        self.provenance.attach_authorship(
            node_id=saved.id,
            author_id=author_id,
            author_type=author_type,
            workspace_id=workspace_id,
            rel_type="DECIDED",
        )

        if input_data.session_id:
            self.provenance.attach_session(
                session_id=input_data.session_id,
                node_id=saved.id,
                workspace_id=workspace_id,
            )

        # Attach Evidence if provided
        if input_data.evidence_content:
            evidence_id = f"evi_{uuid.uuid4().hex[:10]}"
            evidence_model = EvidenceModel(
                id=evidence_id,
                workspace_id=workspace_id,
                evidence_type=EvidenceType.TEST_RESULT,
                content=input_data.evidence_content,
                source_uri=input_data.evidence_source or "session",
                verified=True,
                created_at=now,
            )
            self.node_repo.save_evidence(evidence_model)
            self.rel_repo.link_decision_to_evidence(saved.id, evidence_id, workspace_id)

        # Verify Read-Back
        verified = self.node_repo.get_decision(saved.id, workspace_id)
        if not verified:
            raise RuntimeError(f"Post-write verification failed for decision '{saved.id}'")

        return verified
