# Scalability Guide: Supporting 100k+ Test Cases

This guide explains how to configure and use Metamorphic Guard for very large-scale evaluations with 100k+ test cases.

## Table of Contents

1. [Overview](#overview)
2. [Memory Management](#memory-management)
3. [Chunked Input Generation](#chunked-input-generation)
4. [Incremental Result Processing](#incremental-result-processing)
5. [Progress Tracking and Checkpointing](#progress-tracking-and-checkpointing)
6. [Distributed Execution](#distributed-execution)
7. [Configuration Examples](#configuration-examples)
8. [Performance Tuning](#performance-tuning)

## Overview

For evaluations with 100k+ test cases, several optimizations are needed:

- **Chunked Input Generation**: Generate inputs in chunks to avoid loading all inputs into memory
- **Incremental Result Processing**: Process results in batches and write to disk incrementally
- **Progress Persistence**: Save progress checkpoints to enable resuming
- **Distributed Execution**: Use queue backends (Redis, SQS, RabbitMQ, Kafka) for horizontal scaling
- **Memory Optimization**: Compact results, stream processing, batch operations

## Memory Management

### Estimating Memory Requirements

```python
from metamorphic_guard.scalability import estimate_memory_requirements

estimate = estimate_memory_requirements(
    n=100000,
    input_size_bytes=256,
    result_size_bytes=1024,
)

print(f"Total memory needed: {estimate['total_memory_mb']:.2f} MB")
print(f"Recommendations: {estimate['recommendations']}")
```

### Auto-Configuration

```python
from metamorphic_guard.scalability import create_scalable_config

config = create_scalable_config(
    n=100000,
    checkpoint_dir=Path("checkpoints"),
)

# Use config in run_eval
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=100000,
    **config,
)
```

## Chunked Input Generation

For very large test suites, generate inputs in chunks:

```python
from metamorphic_guard.scalability import ChunkedInputGenerator
from metamorphic_guard.specs import Spec

spec = get_task_spec("my_task")

# Create chunked generator
chunked_gen = ChunkedInputGenerator(
    gen_inputs_fn=spec.gen_inputs,
    total_n=100000,
    seed=42,
    chunk_size=10000,  # Generate 10k inputs per chunk
)

# Use in evaluation
# Note: This requires custom integration with run_eval
# For now, use explicit_inputs parameter when available
inputs = list(chunked_gen)
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    explicit_inputs=inputs,
)
```

## Incremental Result Processing

Process results incrementally to reduce memory footprint:

```python
from metamorphic_guard.scalability import IncrementalResultProcessor
from pathlib import Path

# Create processor
with IncrementalResultProcessor(
    batch_size=1000,
    output_file=Path("results.jsonl"),
    compact=True,
) as processor:
    # Process results as they arrive
    for result in results_stream:
        processor.add_result(result)

# Results are written to disk incrementally
```

## Progress Tracking and Checkpointing

Track progress and enable resuming:

```python
from metamorphic_guard.scalability import ProgressTracker
from pathlib import Path

tracker = ProgressTracker(
    checkpoint_dir=Path("checkpoints"),
    job_id="eval_100k",
)

# Initialize
tracker.initialize(total_cases=100000)

# Update progress
tracker.update(completed=1000, failed=5)

# Get progress info
progress = tracker.get_progress()
print(f"Progress: {progress['progress_percent']:.2f}%")
print(f"Estimated remaining: {progress['estimated_remaining_seconds']:.0f} seconds")

# Save results
tracker.save_results(results)

# Load checkpoint (for resuming)
checkpoint = tracker.load_checkpoint()
if checkpoint:
    print(f"Resuming from {checkpoint['completed_cases']} cases")
```

## Distributed Execution

For 100k+ test cases, use distributed execution:

### Redis Backend

```python
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=100000,
    dispatcher="queue",
    queue_config={
        "backend": "redis",
        "url": "redis://localhost:6379/0",
        "adaptive_batching": True,
        "initial_batch_size": 10,
        "max_batch_size": 100,
        "enable_requeue": True,
        "max_requeue_attempts": 3,
    },
    parallel=None,  # Auto-detect optimal worker count
)
```

### AWS SQS Backend

```python
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=100000,
    dispatcher="queue",
    queue_config={
        "backend": "sqs",
        "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/my-queue",
        "region": "us-east-1",
        "adaptive_batching": True,
        "max_batch_size": 10,  # SQS limit
    },
)
```

### RabbitMQ Backend

```python
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=100000,
    dispatcher="queue",
    queue_config={
        "backend": "rabbitmq",
        "url": "amqp://user:pass@localhost:5672/",
        "exchange": "metamorphic_guard",
        "adaptive_batching": True,
        "max_batch_size": 50,
    },
)
```

### Kafka Backend

```python
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=100000,
    dispatcher="queue",
    queue_config={
        "backend": "kafka",
        "bootstrap_servers": "localhost:9092",
        "topic": "metamorphic_guard_tasks",
        "adaptive_batching": True,
        "max_batch_size": 100,
    },
)
```

## Configuration Examples

### Example 1: 50k Test Cases (Moderate Scale)

```python
from metamorphic_guard import run_eval
from pathlib import Path

result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=50000,
    dispatcher="queue",
    queue_config={
        "backend": "redis",
        "url": "redis://localhost:6379/0",
        "adaptive_batching": True,
        "initial_batch_size": 10,
        "max_batch_size": 50,
    },
    executor_config={"enable_cache": True},  # Enable result caching
)
```

### Example 2: 100k Test Cases (Large Scale)

```python
from metamorphic_guard import run_eval
from metamorphic_guard.scalability import create_scalable_config, ProgressTracker
from pathlib import Path

# Create scalable configuration
config = create_scalable_config(
    n=100000,
    checkpoint_dir=Path("checkpoints"),
)

# Create progress tracker
tracker = ProgressTracker(
    checkpoint_dir=Path("checkpoints"),
    job_id="eval_100k",
)
tracker.initialize(total_cases=100000)

# Run evaluation
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=100000,
    **config,
)

# Update progress
tracker.update(completed=100000)
```

### Example 3: 500k Test Cases (Very Large Scale)

```python
from metamorphic_guard import run_eval
from metamorphic_guard.scalability import (
    create_scalable_config,
    ChunkedInputGenerator,
    IncrementalResultProcessor,
    ProgressTracker,
)
from pathlib import Path

# Create scalable configuration
config = create_scalable_config(
    n=500000,
    checkpoint_dir=Path("checkpoints"),
)

# Use chunked input generation
spec = get_task_spec("my_task")
chunked_gen = ChunkedInputGenerator(
    gen_inputs_fn=spec.gen_inputs,
    total_n=500000,
    seed=42,
    chunk_size=10000,
)

# Process results incrementally
with IncrementalResultProcessor(
    batch_size=1000,
    output_file=Path("results.jsonl"),
    compact=True,
) as processor:
    # Run evaluation with distributed execution
    result = run_eval(
        task_name="my_task",
        baseline_path="baseline.py",
        candidate_path="candidate.py",
        n=500000,
        dispatcher="queue",
        queue_config={
            "backend": "sqs",  # Use SQS for AWS scale
            "queue_url": "https://sqs.us-east-1.amazonaws.com/...",
            "region": "us-east-1",
            "adaptive_batching": True,
            "max_batch_size": 10,
        },
        **config,
    )
```

## Performance Tuning

### Batch Size Optimization

- **Small batches (1-10)**: Better for slow, variable-duration tasks
- **Medium batches (10-50)**: Good balance for most workloads
- **Large batches (50-100)**: Better for fast, consistent-duration tasks

### Worker Count

- **Local execution**: `CPU count` for CPU-bound, `CPU count * 2` for I/O-bound
- **Distributed execution**: Start with 10-20 workers, scale based on queue depth

### Memory Optimization

```python
from metamorphic_guard.memory_optimization import (
    suggest_memory_optimizations,
    compact_results,
)

# Get recommendations
suggestions = suggest_memory_optimizations(
    n=100000,
    estimated_result_size=1024,
)

# Compact results after evaluation
result = run_eval(...)
baseline_results = compact_results(result["baseline"]["results"])
candidate_results = compact_results(result["candidate"]["results"])
```

### Adaptive Testing

For very large suites, use adaptive testing to reduce effective sample size:

```python
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=100000,
    adaptive_testing=True,
    early_stopping=True,
    # Early stopping will reduce actual test cases if decision is clear
)
```

## Monitoring Large-Scale Evaluations

### Progress Monitoring

```python
from metamorphic_guard.scalability import ProgressTracker

tracker = ProgressTracker(
    checkpoint_dir=Path("checkpoints"),
    job_id="eval_100k",
)

# Check progress
progress = tracker.get_progress()
print(f"Progress: {progress['progress_percent']:.2f}%")
print(f"Throughput: {progress['cases_per_second']:.2f} cases/sec")
print(f"Estimated remaining: {progress['estimated_remaining_seconds']:.0f} seconds")
```

### Queue Monitoring

Monitor queue depth and worker utilization:

```python
from metamorphic_guard.dispatch.auto_scaling import create_auto_scaler

# Create auto-scaler
scaler = create_auto_scaler(
    adapter=queue_adapter,
    config={
        "enabled": True,
        "min_workers": 10,
        "max_workers": 100,
        "target_queue_depth": 10,
    },
)

# Get recommended worker count
recommended = scaler.get_recommended_workers(current_workers=20)
print(f"Recommended workers: {recommended}")
```

## Best Practices

1. **Start Small**: Test with 1k-10k cases first to validate configuration
2. **Enable Checkpointing**: Always enable checkpoints for long-running evaluations
3. **Monitor Memory**: Use memory estimation tools before running
4. **Use Distributed Execution**: For 10k+ cases, use queue backends
5. **Enable Result Caching**: Reduce redundant executions
6. **Compact Results**: Remove unnecessary fields to save memory
7. **Stream Processing**: Process results incrementally when possible
8. **Adaptive Testing**: Use early stopping for very large suites

## Troubleshooting

### Out of Memory Errors

- Enable chunked input generation
- Use incremental result processing
- Reduce batch size
- Enable result compaction
- Use distributed execution

### Slow Performance

- Increase batch size (if tasks are fast)
- Increase worker count
- Use faster queue backend (Redis > SQS for latency)
- Enable adaptive batching
- Enable result caching

### Queue Backlog

- Increase worker count
- Use auto-scaling
- Increase batch size
- Check queue backend performance
- Verify workers are processing tasks

---

**Last Updated**: 2025-01-13

