"""
Integration tests for FalkorDB repositories: node CRUD, optimistic concurrency,
relationship creation, traversal, and workspace isolation.
"""

import pytest
import uuid
from graph_memory.db import get_db
from graph_memory.models import (
    MemoryModel,
    DecisionModel,
    EvidenceModel,
    EntityModel,
    SessionModel,
    MemoryType,
    MemoryStatus,
    DecisionStatus,
    EntityType,
    SessionStatus,
)
from graph_memory.repositories.nodes import (
    NodeRepository,
    ConcurrentModificationError,
    NodeNotFoundError,
)
from graph_memory.repositories.relationships import RelationshipRepository


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
    ws_id = f"test_ws_{uuid.uuid4().hex[:8]}"
    node_repo = NodeRepository(db_client)
    node_repo.ensure_workspace(ws_id, name=f"Test Workspace {ws_id}")
    yield ws_id
    # Cleanup after test
    db_client.query("MATCH (n) WHERE n.workspace_id = $ws DETACH DELETE n", {"ws": ws_id})
    db_client.query("MATCH (w:Workspace {id: $ws}) DETACH DELETE w", {"ws": ws_id})


def test_node_save_and_get(db_client, test_workspace):
    node_repo = NodeRepository(db_client)
    mem_id = f"mem_{uuid.uuid4().hex[:8]}"
    mem = MemoryModel(
        id=mem_id,
        workspace_id=test_workspace,
        content="FalkorDB uses sparse adjacency matrices for graph computation.",
        memory_type=MemoryType.FINDING,
        status=MemoryStatus.ACTIVE,
        confidence=0.95,
    )
    saved = node_repo.save_memory(mem)
    assert saved.id == mem_id
    assert saved.version == 1

    fetched = node_repo.get_memory(mem_id, test_workspace)
    assert fetched is not None
    assert fetched.content == mem.content
    assert fetched.confidence == 0.95


def test_optimistic_concurrency_control(db_client, test_workspace):
    node_repo = NodeRepository(db_client)
    mem_id = f"mem_{uuid.uuid4().hex[:8]}"
    mem = MemoryModel(
        id=mem_id,
        workspace_id=test_workspace,
        content="Initial claim about system throughput.",
        memory_type=MemoryType.OBSERVATION,
    )
    node_repo.save_memory(mem)

    # Valid update with expected_version = 1 -> bumps to version 2
    updated = node_repo.update_memory(
        memory_id=mem_id,
        workspace_id=test_workspace,
        expected_version=1,
        updates={"content": "Updated claim with verified benchmarks.", "confidence": 0.98},
    )
    assert updated.version == 2
    assert updated.content == "Updated claim with verified benchmarks."

    # Concurrent update with stale expected_version = 1 MUST fail
    with pytest.raises(ConcurrentModificationError):
        node_repo.update_memory(
            memory_id=mem_id,
            workspace_id=test_workspace,
            expected_version=1,
            updates={"content": "Conflicting overwrite attempt."},
        )


def test_session_handoff_and_optimistic_updates(db_client, test_workspace):
    node_repo = NodeRepository(db_client)
    session = SessionModel(
        id=f"sess_{uuid.uuid4().hex[:8]}",
        workspace_id=test_workspace,
        agent_id="handoff-agent",
        changed_files=["src/service.py"],
        verified_findings=["Service uses bounded retries."],
        test_outcomes="4 passed",
        blockers="None",
        next_steps="Add integration coverage.",
    )
    saved = node_repo.save_session(session)
    saved.status = SessionStatus.CHECKPOINTED
    updated = node_repo.update_session(saved, expected_version=saved.version)
    assert updated.version == saved.version + 1

    handoff = node_repo.get_latest_handoff(test_workspace)
    assert handoff is not None
    assert handoff.id == session.id
    assert handoff.changed_files == ["src/service.py"]
    assert handoff.next_steps == "Add integration coverage."

    with pytest.raises(ConcurrentModificationError):
        node_repo.update_session(saved, expected_version=saved.version)


def test_workspace_isolation(db_client):
    node_repo = NodeRepository(db_client)
    ws_a = f"ws_a_{uuid.uuid4().hex[:8]}"
    ws_b = f"ws_b_{uuid.uuid4().hex[:8]}"
    node_repo.ensure_workspace(ws_a)
    node_repo.ensure_workspace(ws_b)

    mem_id = f"mem_secret_{uuid.uuid4().hex[:8]}"
    mem = MemoryModel(
        id=mem_id,
        workspace_id=ws_a,
        content="Confidential architectural decision for Workspace A.",
    )
    node_repo.save_memory(mem)

    # Lookup within ws_a succeeds
    assert node_repo.get_memory(mem_id, ws_a) is not None

    # Lookup within ws_b MUST return None (strict tenant isolation)
    assert node_repo.get_memory(mem_id, ws_b) is None

    # Cleanup
    db_client.query("MATCH (n) WHERE n.workspace_id IN [$a, $b] DETACH DELETE n", {"a": ws_a, "b": ws_b})
    db_client.query("MATCH (w:Workspace) WHERE w.id IN [$a, $b] DETACH DELETE w", {"a": ws_a, "b": ws_b})


def test_relationships_and_traversal(db_client, test_workspace):
    node_repo = NodeRepository(db_client)
    rel_repo = RelationshipRepository(db_client)

    mem_id = f"mem_{uuid.uuid4().hex[:8]}"
    ent_id = f"entity:file_{uuid.uuid4().hex[:8]}"
    dec_id = f"dec_{uuid.uuid4().hex[:8]}"

    node_repo.save_memory(MemoryModel(id=mem_id, workspace_id=test_workspace, content="Memory node"))
    node_repo.save_entity(EntityModel(id=ent_id, workspace_id=test_workspace, name="test_file.py"))
    node_repo.save_decision(DecisionModel(
        id=dec_id,
        workspace_id=test_workspace,
        title="Dec title",
        rationale="Dec rationale",
    ))

    # Link: Memory -> Entity -> Decision
    rel_repo.create_relationship(mem_id, "RELATES_TO", ent_id, workspace_id=test_workspace)
    rel_repo.create_relationship(ent_id, "IMPLEMENTS", dec_id, workspace_id=test_workspace)

    # 1-hop related nodes from Memory
    related = rel_repo.get_related_nodes(mem_id, test_workspace)
    assert len(related) >= 1
    assert any(r["id"] == ent_id for r in related)

    # 2-hop traversal from Memory should reach Decision
    traversed = rel_repo.traverse(mem_id, test_workspace, max_depth=2)
    traversed_ids = [t["id"] for t in traversed]
    assert ent_id in traversed_ids
    assert dec_id in traversed_ids
