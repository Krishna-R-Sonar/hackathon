"""
Memory update and conflict management module.
Coordinates optimistic version checks, supersession chains, invalidations, and feedback adjustments.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from graph_memory.db import FalkorDBClient, get_db
from graph_memory.models import (
    FeedbackRating,
    MemoryModel,
    MemoryStatus,
    MemoryUpdateInput,
)
from graph_memory.repositories.nodes import NodeRepository, ConcurrentModificationError
from graph_memory.repositories.relationships import RelationshipRepository

logger = logging.getLogger(__name__)


class UpdateManager:
    """Manages memory mutations, version conflict handling, supersessions, and feedback."""

    def __init__(self, db: Optional[FalkorDBClient] = None):
        self.db = db or get_db()
        self.node_repo = NodeRepository(self.db)
        self.rel_repo = RelationshipRepository(self.db)

    def update_memory(self, input_data: MemoryUpdateInput, workspace_id: str) -> MemoryModel:
        """
        Executes an optimistic concurrency update on a memory.
        """
        updates: Dict[str, Any] = {}
        if input_data.new_content is not None:
            updates["content"] = input_data.new_content
        if input_data.new_status is not None:
            updates["status"] = input_data.new_status
        if input_data.new_confidence is not None:
            updates["confidence"] = input_data.new_confidence
        if input_data.superseded_by is not None:
            updates["superseded_by"] = input_data.superseded_by

        updated_mem = self.node_repo.update_memory(
            memory_id=input_data.memory_id,
            workspace_id=workspace_id,
            expected_version=input_data.expected_version,
            updates=updates,
        )

        if input_data.superseded_by:
            self.rel_repo.link_supersession(
                new_id=input_data.superseded_by,
                old_id=input_data.memory_id,
                workspace_id=workspace_id,
            )

        return updated_mem

    def supersede_memory(
        self,
        old_memory_id: str,
        new_memory_id: str,
        workspace_id: str,
    ) -> None:
        """Explicitly deprecates old_memory_id in favor of new_memory_id."""
        old_mem = self.node_repo.get_memory(old_memory_id, workspace_id)
        if not old_mem:
            return

        # Bump version and mark superseded
        self.node_repo.update_memory(
            memory_id=old_memory_id,
            workspace_id=workspace_id,
            expected_version=old_mem.version,
            updates={
                "status": MemoryStatus.SUPERSEDED,
                "superseded_by": new_memory_id,
            },
        )
        self.rel_repo.link_supersession(new_memory_id, old_memory_id, workspace_id)

    def apply_feedback(
        self,
        memory_id: str,
        workspace_id: str,
        rating: FeedbackRating,
        notes: Optional[str] = None,
    ) -> MemoryModel:
        """
        Adjusts memory status and confidence based on agent or developer feedback.
        """
        mem = self.node_repo.get_memory(memory_id, workspace_id)
        if not mem:
            raise ValueError(f"Memory '{memory_id}' not found in workspace '{workspace_id}'")

        updates: Dict[str, Any] = {}
        if rating == FeedbackRating.USEFUL:
            # Positive reinforcement: slight confidence boost
            updates["confidence"] = min(1.0, mem.confidence + 0.05)
        elif rating == FeedbackRating.STALE:
            updates["status"] = MemoryStatus.STALE
            updates["confidence"] = max(0.1, mem.confidence - 0.2)
        elif rating in (FeedbackRating.INCORRECT, FeedbackRating.DISPUTED):
            updates["status"] = MemoryStatus.DISPUTED
            updates["confidence"] = max(0.0, mem.confidence - 0.5)

        return self.node_repo.update_memory(
            memory_id=memory_id,
            workspace_id=workspace_id,
            expected_version=mem.version,
            updates=updates,
        )
