"""
Result caching for identical inputs to avoid redundant executions.
"""

from __future__ import annotations

import hashlib
import pickle
import threading
from typing import Any, Dict, Optional, Tuple

from .types import JSONDict


class ResultCache:
    """
    Thread-safe cache for execution results.
    
    Caches results keyed by input arguments and implementation path,
    allowing reuse of results for identical inputs across different
    evaluation runs or between baseline and candidate when they're identical.
    """
    
    def __init__(self, max_size: int = 10000) -> None:
        """
        Initialize result cache.
        
        Args:
            max_size: Maximum number of entries to cache (LRU eviction)
        """
        self._cache: Dict[str, JSONDict] = {}
        self._lock = threading.RLock()
        self._max_size = max_size
        self._access_order: list[str] = []  # For LRU tracking
    
    def _make_key(self, file_path: str, func_name: str, args: Tuple[Any, ...]) -> str:
        """Create a cache key from execution parameters."""
        # Use pickle to handle complex types, then hash
        key_data = (file_path, func_name, args)
        try:
            pickled = pickle.dumps(key_data, protocol=pickle.HIGHEST_PROTOCOL)
            return hashlib.sha256(pickled).hexdigest()
        except (pickle.PickleError, TypeError):
            # Fallback for non-picklable args
            key_str = f"{file_path}:{func_name}:{repr(args)}"
            return hashlib.sha256(key_str.encode("utf-8")).hexdigest()
    
    def get(
        self,
        file_path: str,
        func_name: str,
        args: Tuple[Any, ...],
    ) -> Optional[JSONDict]:
        """
        Get cached result if available.
        
        Args:
            file_path: Path to implementation file
            func_name: Function name to call
            args: Input arguments
        
        Returns:
            Cached result dict or None if not found
        """
        key = self._make_key(file_path, func_name, args)
        
        with self._lock:
            if key in self._cache:
                # Update access order for LRU
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key].copy()  # Return copy to prevent mutation
        
        return None
    
    def set(
        self,
        file_path: str,
        func_name: str,
        args: Tuple[Any, ...],
        result: JSONDict,
    ) -> None:
        """
        Cache a result.
        
        Args:
            file_path: Path to implementation file
            func_name: Function name to call
            args: Input arguments
            result: Result dictionary to cache
        """
        key = self._make_key(file_path, func_name, args)
        
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                if self._access_order:
                    oldest_key = self._access_order.pop(0)
                    self._cache.pop(oldest_key, None)
            
            # Store result (copy to prevent mutation)
            self._cache[key] = result.copy()
            
            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
    
    def clear(self) -> None:
        """Clear all cached results."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "utilization": len(self._cache) / self._max_size if self._max_size > 0 else 0.0,
            }


# Global cache instance
_global_cache: Optional[ResultCache] = None
_cache_lock = threading.Lock()


def get_result_cache(max_size: int = 10000) -> ResultCache:
    """
    Get or create the global result cache.
    
    Args:
        max_size: Maximum cache size (only used on first call)
    
    Returns:
        Global ResultCache instance
    """
    global _global_cache
    
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = ResultCache(max_size=max_size)
    
    return _global_cache


def clear_result_cache() -> None:
    """Clear the global result cache."""
    global _global_cache
    with _cache_lock:
        if _global_cache is not None:
            _global_cache.clear()

