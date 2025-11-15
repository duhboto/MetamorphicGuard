"""
Tests for result caching functionality.
"""

from __future__ import annotations

import pytest

from metamorphic_guard.result_cache import ResultCache, clear_result_cache, get_result_cache
from metamorphic_guard.types import JSONDict


def test_result_cache_basic():
    """Test basic cache get/set operations."""
    cache = ResultCache(max_size=100)
    
    result1: JSONDict = {"success": True, "result": 42, "duration_ms": 10.0}
    cache.set("test.py", "solve", (1, 2, 3), result1)
    
    cached = cache.get("test.py", "solve", (1, 2, 3))
    assert cached is not None
    assert cached["success"] is True
    assert cached["result"] == 42
    
    # Different args should not be cached
    assert cache.get("test.py", "solve", (4, 5, 6)) is None


def test_result_cache_isolation():
    """Test that cache keys are properly isolated."""
    cache = ResultCache()
    
    result1: JSONDict = {"success": True, "result": "baseline"}
    result2: JSONDict = {"success": True, "result": "candidate"}
    
    cache.set("baseline.py", "solve", (1,), result1)
    cache.set("candidate.py", "solve", (1,), result2)
    
    # Same args, different files should be different
    assert cache.get("baseline.py", "solve", (1,))["result"] == "baseline"
    assert cache.get("candidate.py", "solve", (1,))["result"] == "candidate"


def test_result_cache_lru_eviction():
    """Test LRU eviction when cache is full."""
    cache = ResultCache(max_size=3)
    
    # Fill cache
    for i in range(3):
        cache.set("test.py", "solve", (i,), {"success": True, "value": i})
    
    # Access first item to mark it as recently used
    cache.get("test.py", "solve", (0,))
    
    # Add 4th item - should evict least recently used (item 1 or 2, not 0)
    cache.set("test.py", "solve", (3,), {"success": True, "value": 3})
    
    # Item 0 should still be cached (was accessed)
    assert cache.get("test.py", "solve", (0,)) is not None
    
    # One of items 1 or 2 should be evicted
    cached_1 = cache.get("test.py", "solve", (1,))
    cached_2 = cache.get("test.py", "solve", (2,))
    assert (cached_1 is None) or (cached_2 is None)


def test_result_cache_clear():
    """Test clearing the cache."""
    cache = ResultCache()
    
    cache.set("test.py", "solve", (1,), {"success": True})
    assert cache.get("test.py", "solve", (1,)) is not None
    
    cache.clear()
    assert cache.get("test.py", "solve", (1,)) is None
    assert cache.stats()["size"] == 0


def test_result_cache_stats():
    """Test cache statistics."""
    cache = ResultCache(max_size=100)
    
    stats = cache.stats()
    assert stats["size"] == 0
    assert stats["max_size"] == 100
    assert stats["utilization"] == 0.0
    
    cache.set("test.py", "solve", (1,), {"success": True})
    stats = cache.stats()
    assert stats["size"] == 1
    assert stats["utilization"] == 0.01


def test_global_cache():
    """Test global cache instance."""
    cache1 = get_result_cache()
    cache2 = get_result_cache()
    
    # Should be the same instance
    assert cache1 is cache2
    
    cache1.set("test.py", "solve", (1,), {"success": True})
    assert cache2.get("test.py", "solve", (1,)) is not None


def test_clear_global_cache():
    """Test clearing the global cache."""
    cache = get_result_cache()
    cache.set("test.py", "solve", (1,), {"success": True})
    
    clear_result_cache()
    assert cache.get("test.py", "solve", (1,)) is None


def test_result_cache_thread_safety():
    """Test that cache operations are thread-safe."""
    import threading
    
    cache = ResultCache(max_size=1000)
    results: list[bool] = []
    
    def worker(thread_id: int) -> None:
        for i in range(10):
            key = (thread_id * 100 + i,)
            result: JSONDict = {"success": True, "thread": thread_id, "value": i}
            cache.set("test.py", "solve", key, result)
            cached = cache.get("test.py", "solve", key)
            results.append(cached is not None and cached["thread"] == thread_id)
    
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All operations should succeed
    assert all(results)
    assert len(results) == 50


def test_result_cache_complex_args():
    """Test caching with complex argument types."""
    cache = ResultCache()
    
    # Test with list
    result1: JSONDict = {"success": True, "result": "list"}
    cache.set("test.py", "solve", ([1, 2, 3],), result1)
    assert cache.get("test.py", "solve", ([1, 2, 3],)) is not None
    
    # Test with dict
    result2: JSONDict = {"success": True, "result": "dict"}
    cache.set("test.py", "solve", ({"key": "value"},), result2)
    assert cache.get("test.py", "solve", ({"key": "value"},)) is not None
    
    # Test with nested structures
    result3: JSONDict = {"success": True, "result": "nested"}
    nested_args = ({"items": [1, 2, {"nested": True}]},)
    cache.set("test.py", "solve", nested_args, result3)
    assert cache.get("test.py", "solve", nested_args) is not None

