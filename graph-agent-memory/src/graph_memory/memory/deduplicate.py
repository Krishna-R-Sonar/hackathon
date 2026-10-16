"""
Memory deduplication and content hashing module.
Computes deterministic signatures and resolves duplicate memories within workspaces.
"""

import hashlib
import re
from typing import Optional, Tuple
from graph_memory.db import FalkorDBClient, get_db
from graph_memory.models import MemoryModel, MemoryType


def normalize_content(text: str) -> str:
    """Normalizes whitespace, casing, and punctuation for deterministic hashing."""
    cleaned = text.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def compute_content_hash(content: str, workspace_id: str, memory_type: MemoryType) -> str:
    """Generates a deterministic SHA-256 signature for a memory payload."""
    normalized = normalize_content(content)
    raw = f"{workspace_id}::{memory_type.value}::{normalized}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class DeduplicationEngine:
    """Detects and resolves duplicate memories in FalkorDB."""

    def __init__(self, db: Optional[FalkorDBClient] = None):
        self.db = db or get_db()

    def find_duplicate(
        self,
        content: str,
        workspace_id: str,
        memory_type: MemoryType,
    ) -> Optional[MemoryModel]:
        """
        Checks if an identical memory already exists in the same workspace.
        First attempts hash lookup, then normalized content match.
        """
        content_hash = compute_content_hash(content, workspace_id, memory_type)
        
        # 1. Query by exact content_hash
        cypher = """
        MATCH (m:Memory {workspace_id: $workspace_id, content_hash: $content_hash})
        WHERE m.status IN ['active', 'unverified']
        RETURN m
        LIMIT 1
        """
        res = self.db.query(cypher, {"workspace_id": workspace_id, "content_hash": content_hash}, read_only=True)
        if res.result_set:
            return MemoryModel(**res.result_set[0][0].properties)

        # 2. Query by trimmed exact content string
        cypher_fallback = """
        MATCH (m:Memory {workspace_id: $workspace_id, memory_type: $memory_type})
        WHERE m.status IN ['active', 'unverified'] AND toLower(trim(m.content)) = $normalized
        RETURN m
        LIMIT 1
        """
        res_fb = self.db.query(
            cypher_fallback,
            {
                "workspace_id": workspace_id,
                "memory_type": memory_type.value,
                "normalized": normalize_content(content),
            },
            read_only=True,
        )
        if res_fb.result_set:
            return MemoryModel(**res_fb.result_set[0][0].properties)

        return None
