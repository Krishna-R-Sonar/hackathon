"""
Unit tests for configuration validation and settings.
"""

import pytest
from graph_memory.config import Settings


def test_default_settings():
    s = Settings()
    assert s.falkordb_host in ("127.0.0.1", "localhost")
    assert s.falkordb_port == 6379
    assert s.falkordb_graph_name == "agent_memory"
    assert s.max_traversal_depth == 3
    assert s.max_retrieval_limit == 20
    assert s.mcp_server_name == "graph-agent-memory"


def test_custom_settings():
    s = Settings(
        falkordb_host="10.0.0.5",
        falkordb_port=6380,
        falkordb_graph_name="custom_graph",
        max_traversal_depth=2,
    )
    assert s.falkordb_host == "10.0.0.5"
    assert s.falkordb_port == 6380
    assert s.falkordb_graph_name == "custom_graph"
    assert s.max_traversal_depth == 2
