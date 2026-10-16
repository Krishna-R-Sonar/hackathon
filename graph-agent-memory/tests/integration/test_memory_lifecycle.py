"""
Integration tests for the complete memory lifecycle:
Ingestion, Deduplication, Provenance, Updates, Feedback, and Retrieval.
"""

import pytest
import uuid
from graph_memory.db import get_db
from graph_memory.models import (
    DecisionRecordInput,
    DecisionStatus,
    FeedbackRating,
    MemorySaveInput,
    MemorySearchInput,
    MemoryStatus,
    MemoryType,
    MemoryUpdateInput,
)
from graph_memory.memory.ingest import IngestionEngine
from graph_memory.memory.retrieve import RetrievalEngine
from graph_memory.memory.update import UpdateManager
from graph_memory.memory.provenance import ProvenanceTracker


@pytest.fixture(scope="module")
def db_client():
    client = get_db()
    health = client.check_health()
    if health.get("status") != "healthy":
        pytest.skip(f"FalkorDB is not running: {health}")
    client.init_schema()
    return client


@pytest.fixture
def test_workspace(db_client):
    ws_id = f"test_lifecycle_ws_{uuid.uuid4().hex[:8]}"
    db_client.query("MERGE (w:Workspace {id: $ws})", {"ws": ws_id})
    yield ws_id
    db_client.query("MATCH (n) WHERE n.workspace_id = $ws DETACH DELETE n", {"ws": ws_id})
    db_client.query("MATCH (w:Workspace {id: $ws}) DETACH DELETE w", {"ws": ws_id})


def test_ingest_and_deduplicate(db_client, test_workspace):
    ingest_engine = IngestionEngine(db_client)

    input_data = MemorySaveInput(
        content="OpenCypher enables graph queries using declarative pattern matching.",
        memory_type=MemoryType.FINDING,
        confidence=0.9,
        source_ref="docs/cypher.md",
    )

    mem1 = ingest_engine.ingest_memory(input_data, test_workspace)
    assert mem1.id.startswith("mem_")

    # Re-ingesting the exact same content should deduplicate and return the existing memory
    mem2 = ingest_engine.ingest_memory(input_data, test_workspace)
    assert mem2.id == mem1.id
    assert mem2.confidence >= mem1.confidence


def test_provenance_and_evidence(db_client, test_workspace):
    ingest_engine = IngestionEngine(db_client)
    provenance = ProvenanceTracker(db_client)

    mem = ingest_engine.ingest_memory(
        MemorySaveInput(
            content="Matrix multiplication in FalkorDB is optimized with GraphBLAS.",
            memory_type=MemoryType.SEMANTIC,
            author_id="benchmarking-agent",
            evidence_content="Benchmark: GraphBLAS 10k traversals executed in 14ms",
            source_ref="benchmarks/graphblas_test.py",
        ),
        test_workspace,
    )

    tree = provenance.get_provenance(mem.id, test_workspace)
    assert tree["node_id"] == mem.id
    assert tree["author"]["id"] == "benchmarking-agent"
    assert len(tree["supporting_evidence"]) >= 1
    assert "GraphBLAS" in tree["supporting_evidence"][0]["content"]


def test_decision_ingestion_and_retrieval(db_client, test_workspace):
    ingest_engine = IngestionEngine(db_client)
    retrieve_engine = RetrievalEngine(db_client)

    dec = ingest_engine.ingest_decision(
        DecisionRecordInput(
            title="Use exponential backoff for transient API failures",
            rationale="Prevents server saturation during intermittent network blips.",
            alternatives_considered=["Immediate retry", "Circuit breaker only"],
            evidence_content="Test run: 100% recovery under simulated network drop",
            author_id="architect-agent",
        ),
        test_workspace,
    )

    packet = retrieve_engine.search(
        MemorySearchInput(query="retry backoff strategy"),
        workspace_id=test_workspace,
    )

    assert len(packet.decisions) >= 1
    found_dec = packet.decisions[0]
    assert found_dec["id"] == dec.id
    assert "exponential backoff" in found_dec["title"].lower()
    assert len(packet.evidence) >= 1


def test_update_and_feedback(db_client, test_workspace):
    ingest_engine = IngestionEngine(db_client)
    update_mgr = UpdateManager(db_client)

    mem = ingest_engine.ingest_memory(
        MemorySaveInput(
            content="Docker compose v2 is available as a CLI plugin.",
            memory_type=MemoryType.FINDING,
        ),
        test_workspace,
    )

    # Apply positive feedback
    updated = update_mgr.apply_feedback(
        memory_id=mem.id,
        workspace_id=test_workspace,
        rating=FeedbackRating.USEFUL,
    )
    assert updated.confidence >= mem.confidence

    # Apply stale feedback
    stale_mem = update_mgr.apply_feedback(
        memory_id=mem.id,
        workspace_id=test_workspace,
        rating=FeedbackRating.STALE,
    )
    assert stale_mem.status == MemoryStatus.STALE
