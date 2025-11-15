"""
Memory optimization utilities for large-scale evaluations.
"""

from __future__ import annotations

import gc
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from .types import JSONDict


def stream_results(
    results: Sequence[JSONDict],
    batch_size: int = 100,
    *,
    processor: Optional[Callable[[List[JSONDict]], None]] = None,
) -> Iterator[List[JSONDict]]:
    """
    Stream results in batches to reduce memory footprint.
    
    Args:
        results: Sequence of result dictionaries
        batch_size: Number of results to yield per batch
        processor: Optional function to process each batch (for side effects)
    
    Yields:
        Batches of results
    """
    for i in range(0, len(results), batch_size):
        batch = list(results[i : i + batch_size])
        if processor:
            processor(batch)
        yield batch


def compact_result(result: JSONDict) -> JSONDict:
    """
    Compact a result dictionary by removing unnecessary fields.
    
    Removes verbose fields that may not be needed for final analysis,
    keeping only essential metrics.
    
    Args:
        result: Full result dictionary
    
    Returns:
        Compacted result dictionary
    """
    # Keep essential fields
    essential = {
        "success": result.get("success", False),
        "duration_ms": result.get("duration_ms", 0.0),
    }
    
    # Keep result if present
    if "result" in result:
        essential["result"] = result["result"]
    
    # Keep error information if present
    if "error" in result:
        essential["error"] = result["error"]
    
    # Keep LLM-specific metrics if present (these are usually small)
    for key in ("tokens_total", "tokens_prompt", "tokens_completion", "cost_usd"):
        if key in result:
            essential[key] = result[key]
    
    # Remove verbose fields that can be large
    # (stdout, stderr can be very large for some executors)
    # These are typically only needed for debugging
    
    return essential


def compact_results(results: Sequence[JSONDict], *, in_place: bool = False) -> List[JSONDict]:
    """
    Compact a sequence of results to reduce memory usage.
    
    Args:
        results: Sequence of result dictionaries
        in_place: If True, modify results in place (if mutable)
    
    Returns:
        List of compacted results
    """
    if in_place and isinstance(results, list):
        for i, result in enumerate(results):
            results[i] = compact_result(result)
        return results
    
    return [compact_result(result) for result in results]


def suggest_memory_optimizations(
    n: int,
    estimated_result_size: int = 1024,  # bytes per result
    available_memory_mb: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Suggest memory optimization strategies based on test suite size.
    
    Args:
        n: Number of test cases
        estimated_result_size: Estimated size per result in bytes
        available_memory_mb: Available memory in MB (None to auto-detect)
    
    Returns:
        Dictionary with optimization suggestions
    """
    import psutil
    
    if available_memory_mb is None:
        try:
            available_memory_mb = psutil.virtual_memory().available // (1024 * 1024)
        except Exception:
            available_memory_mb = 1024  # Default assumption
    
    total_estimated_mb = (n * estimated_result_size) / (1024 * 1024)
    memory_ratio = total_estimated_mb / available_memory_mb if available_memory_mb > 0 else 1.0
    
    suggestions: Dict[str, Any] = {
        "estimated_memory_mb": total_estimated_mb,
        "available_memory_mb": available_memory_mb,
        "memory_pressure": memory_ratio,
        "recommendations": [],
    }
    
    if memory_ratio > 0.5:
        suggestions["recommendations"].append("Enable result compaction")
        suggestions["recommendations"].append("Use streaming processing")
        suggestions["recommendations"].append("Consider reducing violation_cap")
    
    if memory_ratio > 0.8:
        suggestions["recommendations"].append("Use queue dispatcher for distributed execution")
        suggestions["recommendations"].append("Process results in batches")
    
    if n > 10000:
        suggestions["recommendations"].append("Consider adaptive testing to reduce sample size")
        suggestions["recommendations"].append("Enable result caching to avoid redundant executions")
    
    return suggestions

