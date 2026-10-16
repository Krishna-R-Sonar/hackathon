"""
Unit tests for domain models, validation rules, and secret detection.
"""

import pytest
from graph_memory.models import (
    MemoryModel,
    DecisionModel,
    EvidenceModel,
    ConversationMessageModel,
    SessionEndInput,
    MemoryType,
    MemoryStatus,
    DecisionStatus,
    check_for_secrets,
)


def test_memory_model_validation():
    mem = MemoryModel(
        id="mem_123",
        workspace_id="test_ws",
        content="Discovered database indexes optimize lookup performance.",
        memory_type=MemoryType.FINDING,
        status=MemoryStatus.ACTIVE,
        confidence=0.9,
    )
    assert mem.id == "mem_123"
    assert mem.version == 1
    assert mem.confidence == 0.9


def test_decision_model_validation():
    dec = DecisionModel(
        id="dec_456",
        workspace_id="test_ws",
        title="Use exponential backoff",
        rationale="Prevents thundering herd problems during outages.",
        alternatives_considered=["Immediate retry", "Fixed 1s delay"],
        status=DecisionStatus.ACCEPTED,
    )
    assert dec.id == "dec_456"
    assert len(dec.alternatives_considered) == 2


def test_secret_detection_rejects_api_keys():
    with pytest.raises(ValueError, match="Security rejection"):
        MemoryModel(
            id="mem_bad",
            workspace_id="test_ws",
            content="Configured OpenAI client with key sk-1234567890abcdef1234567890abcdef",
        )


def test_secret_detection_rejects_github_tokens():
    with pytest.raises(ValueError, match="Security rejection"):
        DecisionModel(
            id="dec_bad",
            workspace_id="test_ws",
            title="Update token",
            rationale="Updated deployment using token ghp_1234567890abcdef1234567890abcdef",
        )


def test_secret_detection_rejects_private_keys():
    with pytest.raises(ValueError, match="Security rejection"):
        EvidenceModel(
            id="evi_bad",
            workspace_id="test_ws",
            content="-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...",
        )


def test_conversation_message_rejects_secrets():
    with pytest.raises(ValueError, match="Security rejection"):
        ConversationMessageModel(
            id="msg_test",
            workspace_id="test_ws",
            session_id="sess_test",
            role="assistant",
            content="Use this password: 'notarealpassword123'",
        )


def test_conversation_message_normalizes_content():
    message = ConversationMessageModel(
        id="msg_test",
        workspace_id="test_ws",
        session_id="sess_test",
        role="assistant",
        content="  answer  ",
    )
    assert message.content == "answer"


def test_conversation_message_rejects_empty_content():
    with pytest.raises(ValueError):
        ConversationMessageModel(
            id="msg_test",
            workspace_id="test_ws",
            session_id="sess_test",
            role="assistant",
            content="   ",
        )


def test_session_end_summary_rejects_secrets():
    with pytest.raises(ValueError, match="Security rejection"):
        SessionEndInput(
            session_id="sess_test",
            summary="Deploy password: 'notarealpassword123'",
        )
