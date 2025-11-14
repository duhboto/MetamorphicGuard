# Architecture

This document describes the core architecture of Metamorphic Guard.

## Core Components

### Task Specification

A task specification (`Spec`) defines:
- Input generation (`gen_inputs`)
- Properties to check (`properties`)
- Metamorphic relations (`relations`)
- Equivalence function (`equivalence`)

### Dispatcher

The dispatcher manages test execution:
- **LocalDispatcher**: Thread/process pool for local execution
- **QueueDispatcher**: Queue-based for distributed execution

**Implementation notes**
- `sandbox.py` now delegates to `sandbox_workspace.py` and `sandbox_limits.py` for workspace management and resource capping.
- Queue serialization utilities live in `queue_serialization.py`; adapters in `queue_adapter.py`.

### Statistical Engine

Computes:
- Bootstrap confidence intervals
- Power estimates
- Paired statistical tests

### Adoption Gate

Decides whether to adopt a candidate based on:
- Pass rate differences
- Confidence intervals
- Policy thresholds

### Report Generator

Creates JSON and HTML reports with:
- Statistical summaries
- Violation details
- Decision rationale

## Execution System

### Worker Liveness

Workers send heartbeats to indicate they're alive. Tasks are automatically requeued if a worker times out.

### Shutdown

Graceful shutdown:
1. Stop accepting new tasks
2. Wait for in-flight tasks to complete
3. Clean up resources

### Queue Adapter Interface

Queue adapters implement:
- `publish(task)` - Enqueue a task
- `consume()` - Dequeue a task
- `ack(task_id)` - Acknowledge completion

## Plugin System

Metamorphic Guard uses entry points for plugins:

- `metamorphic_guard.executors` - Execution backends
- `metamorphic_guard.judges` - Output evaluators
- `metamorphic_guard.mutants` - Input transformers
- `metamorphic_guard.monitors` - Metrics collectors

See [Plugin Development](plugin-development.md) for details.

