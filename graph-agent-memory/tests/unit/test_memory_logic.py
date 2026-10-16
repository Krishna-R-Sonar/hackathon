"""
Unit tests for memory deduplication, hashing, keyword extraction, and freshness calculation.
"""

from datetime import datetime, timezone, timedelta
from graph_memory.memory.deduplicate import normalize_content, compute_content_hash
from graph_memory.memory.retrieve import extract_keywords, compute_freshness
from graph_memory.models import MemoryType


def test_normalize_content():
    raw = "   FalkorDB   Graph   Database!  \n\t "
    norm = normalize_content(raw)
    assert norm == "falkordb graph database!"


def test_content_hashing_determinism():
    h1 = compute_content_hash("Use Redis protocol", "ws_1", MemoryType.FINDING)
    h2 = compute_content_hash("  use  redis   protocol  ", "ws_1", MemoryType.FINDING)
    assert h1 == h2

    # Different workspace or type yields different hash
    h3 = compute_content_hash("Use Redis protocol", "ws_2", MemoryType.FINDING)
    assert h1 != h3


def test_keyword_extraction():
    text = "Why is the exponential backoff strategy effective for transient network failures?"
    kws = extract_keywords(text)
    assert "exponential" in kws
    assert "backoff" in kws
    assert "strategy" in kws
    assert "the" not in kws
    assert "is" not in kws


def test_freshness_decay():
    now_str = datetime.now(timezone.utc).isoformat()
    old_str = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()

    f_now = compute_freshness(now_str)
    f_old = compute_freshness(old_str)

    assert f_now > f_old
    assert f_now <= 1.0
    assert f_old >= 0.5
