"""
Scalability enhancements for large-scale evaluations (100k+ test cases).

Provides chunked input generation, progress persistence, checkpointing,
and incremental result processing.
"""

from __future__ import annotations

import json
import os
import pickle
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from .types import JSONDict


class ChunkedInputGenerator:
    """
    Generates test inputs in chunks to avoid loading all inputs into memory.
    
    Useful for very large test suites (100k+ cases) where generating all
    inputs upfront would consume too much memory.
    """

    def __init__(
        self,
        gen_inputs_fn: Callable[[int, int], List[Tuple[Any, ...]]],
        total_n: int,
        seed: int,
        chunk_size: int = 10000,
    ) -> None:
        """
        Initialize chunked input generator.

        Args:
            gen_inputs_fn: Function that generates n inputs given (n, seed)
            total_n: Total number of test cases
            seed: Random seed
            chunk_size: Number of inputs to generate per chunk
        """
        self.gen_inputs_fn = gen_inputs_fn
        self.total_n = total_n
        self.seed = seed
        self.chunk_size = chunk_size
        self.current_chunk = 0
        self.current_chunk_inputs: Optional[List[Tuple[Any, ...]]] = None

    def __iter__(self) -> Iterator[Tuple[Any, ...]]:
        """Iterate over all inputs, generating chunks as needed."""
        remaining = self.total_n
        current_seed = self.seed
        chunk_idx = 0

        while remaining > 0:
            chunk_n = min(self.chunk_size, remaining)
            chunk_inputs = self.gen_inputs_fn(chunk_n, current_seed)

            for inp in chunk_inputs:
                yield inp

            remaining -= chunk_n
            current_seed += chunk_n  # Advance seed for next chunk
            chunk_idx += 1

    def get_chunk(self, chunk_index: int) -> List[Tuple[Any, ...]]:
        """
        Get a specific chunk of inputs.

        Args:
            chunk_index: Zero-based chunk index

        Returns:
            List of inputs for this chunk
        """
        chunk_start = chunk_index * self.chunk_size
        chunk_n = min(self.chunk_size, self.total_n - chunk_start)
        chunk_seed = self.seed + chunk_start

        return self.gen_inputs_fn(chunk_n, chunk_seed)

    def num_chunks(self) -> int:
        """Get total number of chunks."""
        return (self.total_n + self.chunk_size - 1) // self.chunk_size


class ProgressTracker:
    """Tracks progress of large-scale evaluations with persistence."""

    def __init__(self, checkpoint_dir: Path, job_id: str) -> None:
        """
        Initialize progress tracker.

        Args:
            checkpoint_dir: Directory to store checkpoint files
            job_id: Unique job identifier
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.job_id = job_id
        self.checkpoint_file = self.checkpoint_dir / f"checkpoint_{job_id}.json"
        self.results_file = self.checkpoint_dir / f"results_{job_id}.pkl"

        self.total_cases = 0
        self.completed_cases = 0
        self.failed_cases = 0
        self.start_time = time.time()
        self.last_update_time = time.time()

    def initialize(self, total_cases: int) -> None:
        """Initialize progress tracking."""
        self.total_cases = total_cases
        self.completed_cases = 0
        self.failed_cases = 0
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.save_checkpoint()

    def update(self, completed: int, failed: int = 0) -> None:
        """Update progress."""
        self.completed_cases += completed
        self.failed_cases += failed
        self.last_update_time = time.time()

        # Save checkpoint every 1000 cases or every 60 seconds
        if (
            self.completed_cases % 1000 == 0
            or time.time() - self.last_update_time > 60
        ):
            self.save_checkpoint()

    def save_checkpoint(self) -> None:
        """Save progress checkpoint."""
        checkpoint_data = {
            "job_id": self.job_id,
            "total_cases": self.total_cases,
            "completed_cases": self.completed_cases,
            "failed_cases": self.failed_cases,
            "start_time": self.start_time,
            "last_update_time": self.last_update_time,
            "progress_percent": (
                (self.completed_cases / self.total_cases * 100)
                if self.total_cases > 0
                else 0.0
            ),
        }

        with open(self.checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

    def load_checkpoint(self) -> Optional[JSONDict]:
        """Load progress checkpoint if it exists."""
        if not self.checkpoint_file.exists():
            return None

        with open(self.checkpoint_file, "r") as f:
            return json.load(f)

    def get_progress(self) -> JSONDict:
        """Get current progress information."""
        elapsed = time.time() - self.start_time
        remaining_cases = self.total_cases - self.completed_cases

        if self.completed_cases > 0:
            avg_time_per_case = elapsed / self.completed_cases
            estimated_remaining = avg_time_per_case * remaining_cases
        else:
            estimated_remaining = None

        return {
            "total_cases": self.total_cases,
            "completed_cases": self.completed_cases,
            "failed_cases": self.failed_cases,
            "progress_percent": (
                (self.completed_cases / self.total_cases * 100)
                if self.total_cases > 0
                else 0.0
            ),
            "elapsed_seconds": elapsed,
            "estimated_remaining_seconds": estimated_remaining,
            "cases_per_second": (
                self.completed_cases / elapsed if elapsed > 0 else 0.0
            ),
        }

    def save_results(self, results: List[JSONDict]) -> None:
        """Save results to disk."""
        with open(self.results_file, "wb") as f:
            pickle.dump(results, f)

    def load_results(self) -> Optional[List[JSONDict]]:
        """Load results from disk if they exist."""
        if not self.results_file.exists():
            return None

        with open(self.results_file, "rb") as f:
            return pickle.load(f)


class IncrementalResultProcessor:
    """
    Processes results incrementally to reduce memory footprint.
    
    Instead of accumulating all results in memory, processes them
    in batches and optionally writes to disk.
    """

    def __init__(
        self,
        batch_size: int = 1000,
        output_file: Optional[Path] = None,
        compact: bool = True,
    ) -> None:
        """
        Initialize incremental result processor.

        Args:
            batch_size: Number of results to accumulate before processing
            output_file: Optional file to write results to (JSONL format)
            compact: Whether to compact results before writing
        """
        self.batch_size = batch_size
        self.output_file = output_file
        self.compact = compact

        self.buffer: List[JSONDict] = []
        self.total_processed = 0

        if self.output_file:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            # Open in append mode to support resuming
            self.file_handle = open(self.output_file, "a")
        else:
            self.file_handle = None

    def add_result(self, result: JSONDict) -> None:
        """Add a result to the processor."""
        self.buffer.append(result)

        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """Flush buffered results."""
        if not self.buffer:
            return

        if self.compact:
            from .memory_optimization import compact_results

            processed = compact_results(self.buffer)
        else:
            processed = self.buffer

        if self.file_handle:
            for result in processed:
                self.file_handle.write(json.dumps(result) + "\n")
            self.file_handle.flush()

        self.total_processed += len(self.buffer)
        self.buffer.clear()

    def close(self) -> List[JSONDict]:
        """Close processor and return any remaining buffered results."""
        self.flush()

        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None

        return self.buffer.copy()

    def __enter__(self) -> IncrementalResultProcessor:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


def estimate_memory_requirements(
    n: int,
    input_size_bytes: int = 256,
    result_size_bytes: int = 1024,
    batch_size: int = 1000,
) -> Dict[str, Any]:
    """
    Estimate memory requirements for a large-scale evaluation.

    Args:
        n: Number of test cases
        input_size_bytes: Estimated size per input in bytes
        result_size_bytes: Estimated size per result in bytes
        batch_size: Batch size for processing

    Returns:
        Dictionary with memory estimates and recommendations
    """
    # Memory for inputs (if not chunked)
    input_memory_mb = (n * input_size_bytes) / (1024 * 1024)

    # Memory for results (if not incremental)
    result_memory_mb = (n * result_size_bytes) / (1024 * 1024)

    # Memory for batch processing
    batch_memory_mb = (batch_size * (input_size_bytes + result_size_bytes)) / (1024 * 1024)

    total_memory_mb = input_memory_mb + result_memory_mb

    recommendations = []

    if input_memory_mb > 1000:
        recommendations.append("Use ChunkedInputGenerator to avoid loading all inputs")
        recommendations.append("Generate inputs on-demand or in chunks")

    if result_memory_mb > 1000:
        recommendations.append("Use IncrementalResultProcessor to process results incrementally")
        recommendations.append("Enable result compaction")
        recommendations.append("Write results to disk as they're generated")

    if total_memory_mb > 2000:
        recommendations.append("Use distributed execution with queue backend")
        recommendations.append("Consider adaptive testing to reduce sample size")

    return {
        "n": n,
        "input_memory_mb": input_memory_mb,
        "result_memory_mb": result_memory_mb,
        "batch_memory_mb": batch_memory_mb,
        "total_memory_mb": total_memory_mb,
        "recommendations": recommendations,
        "chunked_input_needed": input_memory_mb > 1000,
        "incremental_processing_needed": result_memory_mb > 1000,
    }


def create_scalable_config(
    n: int,
    available_memory_mb: Optional[int] = None,
    checkpoint_dir: Optional[Path] = None,
) -> JSONDict:
    """
    Create a configuration optimized for large-scale evaluations.

    Args:
        n: Number of test cases
        available_memory_mb: Available memory in MB (None to auto-detect)
        checkpoint_dir: Directory for checkpoints (None to disable)

    Returns:
        Configuration dictionary with scalability optimizations
    """
    import psutil

    if available_memory_mb is None:
        try:
            available_memory_mb = psutil.virtual_memory().available // (1024 * 1024)
        except Exception:
            available_memory_mb = 2048  # Default assumption

    memory_estimate = estimate_memory_requirements(n)

    config: JSONDict = {
        "use_chunked_inputs": memory_estimate["chunked_input_needed"],
        "use_incremental_processing": memory_estimate["incremental_processing_needed"],
        "checkpoint_enabled": checkpoint_dir is not None,
    }

    if checkpoint_dir:
        config["checkpoint_dir"] = str(checkpoint_dir)

    # Queue configuration for distributed execution
    if n > 10000:
        config["dispatcher"] = "queue"
        config["queue_config"] = {
            "backend": "redis",  # or "sqs", "rabbitmq", "kafka"
            "adaptive_batching": True,
            "initial_batch_size": 10,
            "max_batch_size": 100,
            "enable_requeue": True,
            "max_requeue_attempts": 3,
        }

    # Memory optimizations
    if memory_estimate["incremental_processing_needed"]:
        config["result_compaction"] = True
        config["batch_size"] = 1000

    # Adaptive testing for very large suites
    if n > 50000:
        config["adaptive_testing"] = True
        config["early_stopping"] = True

    return config

