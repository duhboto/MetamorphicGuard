# Architecture & Execution System

This document describes Metamorphic Guard's architecture, standardized interfaces, and execution system behavior.

## Core Components

Metamorphic Guard follows a modular architecture with swappable components:

### 1. Task Specification (`Spec`)

**Interface**: `metamorphic_guard.specs.Spec`

Defines the task being evaluated:
- **Input Generation**: `gen_inputs(n: int, seed: int) -> List[Tuple[Any, ...]]`
- **Properties**: List of `Property` objects (hard/soft invariants)
- **Metamorphic Relations**: List of `MetamorphicRelation` objects
- **Equivalence**: Function to compare outputs
- **Formatters**: Input/output formatting functions
- **Cluster Key**: Optional function for grouping related test cases
- **Metrics**: Optional list of `Metric` descriptors that extract continuous/cost objectives from each successful run

**Example**:
```python
from metamorphic_guard import Spec, Property, MetamorphicRelation, Metric

spec = Spec(
    gen_inputs=lambda n, seed: [(i,) for i in range(n)],
    properties=[Property(check=lambda out, x: out > 0, description="Positive")],
    relations=[MetamorphicRelation(name="double", transform=lambda x: (x * 2,))],
    equivalence=lambda a, b: a == b,
    metrics=[
        Metric(name="mean_gain", extract=lambda out, args: out - args[0], kind="mean"),
        Metric(name="total_cost", extract=lambda out, args: args[0] * 0.01, kind="sum", higher_is_better=False),
    ],
)
```

**Swappability**: Implement custom `Spec` instances or register via `@task("name")` decorator.

---

### 2. Dispatcher (`Dispatcher`)

**Interface**: `metamorphic_guard.dispatch.Dispatcher`

Abstract base class for executing test cases:

```python
class Dispatcher(ABC):
    @abstractmethod
    def execute(
        self,
        *,
        test_inputs: Sequence[Tuple[Any, ...]],
        run_case: RunCase,
        role: str,
        monitors: Sequence[Monitor] | None = None,
        call_spec: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute run_case against all inputs."""
```

**Implementations**:
- `LocalDispatcher`: Thread-based local execution
- `QueueDispatcher`: Queue-backed distributed execution (experimental)

**Swappability**: Implement custom dispatchers or register via plugin system.

**Example**:
```python
from metamorphic_guard.dispatch import Dispatcher, LocalDispatcher

dispatcher = LocalDispatcher(workers=4)
results = dispatcher.execute(
    test_inputs=[(1,), (2,), (3,)],
    run_case=lambda idx, args: {"success": True, "result": args[0] * 2},
    role="candidate",
)
```

---

### 3. Statistical Engine

**Interface**: Functions in `metamorphic_guard.harness`

Computes confidence intervals and power estimates:
- `_compute_delta_ci()`: Confidence intervals for pass-rate delta
- `_estimate_power()`: Statistical power analysis
- Methods: `bootstrap`, `bootstrap-cluster`, `newcombe`, `wilson`

**Swappability**: Extend by adding new CI methods or power estimators.

---

### 4. Adoption Gate (`decide_adopt`)

**Interface**: `metamorphic_guard.gate.decide_adopt`

Makes adoption decisions based on evaluation results:

```python
def decide_adopt(
    result: Dict[str, Any],
    improve_delta: float = 0.02,
    min_pass_rate: float = 0.80,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Returns {'adopt': bool, 'reason': str}"""
```

**Swappability**: Implement custom gate logic or use policy-as-code.

---

### 5. Report (`Report`)

**Interface**: `metamorphic_guard.report_schema.Report`

Pydantic model for evaluation reports:
- Baseline/candidate metrics
- Continuous metric summaries declared via `Spec.metrics` (means, sums, paired deltas, ratios)
- Decision and reasoning
- Confidence intervals
- Violations
- Provenance metadata (library/build info, sandbox configuration fingerprints, executor settings)
- Stability runs (if enabled)

**Swappability**: Extend `Report` model or add custom report generators.

---

#### Metric Aggregation

`Spec.metrics` allows continuous/paired objectives to be computed alongside pass/fail counts.  
Each `Metric` defines:

- `extract(output, args) -> float`: derived value for a successful run.
- `kind`: `"mean"` or `"sum"` aggregation strategy.
- `higher_is_better`: signals whether positive deltas are desirable.
- Optional performance knobs:
  - `memoize=True` or `memoize_key="shared_id"` caches expensive extractors across multiple metrics (e.g., mean + sum of the same signal) so the underlying sandbox result is parsed once per case.
  - `sample_rate=<0..1>` evaluates metrics on a deterministic subsample (seeded by `metric.seed` or the harness seed) to reduce extractor cost on large suites. Missing counts are tracked to signal down-sampled summaries.

`run_eval` serialises metric summaries under `result["metrics"]`, including paired deltas and ratios when both baseline and candidate emit values. This enables downstream dashboards to reason about cost, latency, fairness gaps, or arbitrary performance scores without leaving the harness.

#### Sandbox Provenance

Every report now embeds sandbox metadata (`provenance.sandbox`):

- Executor name and resource limits (`timeout_s`, `mem_mb`)
- Sanitized call specs for baseline/candidate (path, entrypoint, executor overrides)
- SHA-256 fingerprints of call-spec payloads and executor configuration

These fingerprints make it possible to attest which runtime configuration produced a report, even after secrets or transient settings are redacted.

---

## Execution System

### Worker Liveness & Heartbeats

**Queue Dispatcher** (`QueueDispatcher`) uses heartbeats to track worker health:

1. **Registration**: Workers call `adapter.register_worker(worker_id)` periodically
2. **Heartbeat Tracking**: Adapter stores `{worker_id: timestamp}` mapping
3. **Timeout Detection**: Dispatcher checks heartbeat age against `heartbeat_timeout` (default: 45s)
4. **Requeue Logic**: Tasks assigned to stale workers are requeued

**Configuration**:
```python
queue_config = {
    "heartbeat_timeout": 45.0,  # Seconds before worker considered stale
    "enable_requeue": True,     # Requeue tasks from stale workers
}
```

**Local Dispatcher** (`LocalDispatcher`) doesn't use heartbeats; workers are threads managed by `ThreadPoolExecutor`.

---

### Shutdown & Signal Handling

**Graceful Shutdown**:

1. **Shutdown Signal**: `adapter.signal_shutdown()` sends `__shutdown__` tasks to all workers
2. **Worker Cleanup**: Workers check for `__shutdown__` and exit cleanly
3. **Thread Joining**: Dispatcher waits up to 1s for threads to finish

**Ctrl-C (SIGINT) Behavior**:

- **Local Dispatcher**: Python's default SIGINT handling applies; threads may be interrupted mid-execution
- **Queue Dispatcher**: Shutdown signal is sent, but in-flight tasks may complete before workers exit
- **Recommendation**: Use `--timeout-s` to bound individual test execution time

**Best Practices**:
- Set reasonable `--timeout-s` per test case
- Use `--stability N` to detect flakiness from interrupted runs
- Monitor worker heartbeats in distributed setups

---

### Queue Adapter Interface

**In-Memory Adapter** (`InMemoryQueueAdapter`):
- Thread-safe using dedicated locks (`_result_lock`, `_assignment_lock`, `_heartbeat_lock`)
- Locks are **not held** during blocking I/O (`Queue.get`/`Queue.put`)
- Supports `reset()` for test isolation

**Redis Adapter** (`RedisQueueAdapter`):
- Uses Redis for distributed coordination
- Heartbeats stored in Redis hash: `{worker_key: {worker_id: timestamp}}`
- Shutdown flag stored as Redis key with TTL

**Key Operations**:
- `consume_task(worker_id, timeout)`: Blocking task retrieval
- `publish_result(result)`: Non-blocking result submission
- `register_worker(worker_id)`: Update heartbeat timestamp
- `worker_heartbeats()`: Get all worker timestamps
- `signal_shutdown()`: Broadcast shutdown to workers

---

## Component Swapping

### Custom Dispatcher

```python
from metamorphic_guard.dispatch import Dispatcher

class MyDispatcher(Dispatcher):
    def __init__(self, workers: int = 1):
        super().__init__(workers, kind="my_dispatcher")
    
    def execute(self, *, test_inputs, run_case, role, monitors=None, call_spec=None):
        # Custom execution logic
        results = []
        for idx, args in enumerate(test_inputs):
            results.append(run_case(idx, args))
        return results
```

### Custom Gate Logic

```python
from metamorphic_guard.gate import decide_adopt

def my_custom_gate(result: Dict[str, Any]) -> Dict[str, Any]:
    # Custom decision logic
    if result["candidate"]["pass_rate"] > 0.95:
        return {"adopt": True, "reason": "excellent_pass_rate"}
    return {"adopt": False, "reason": "insufficient_pass_rate"}

# Use in harness
result["decision"] = my_custom_gate(result)
```

### Custom Report Generator

```python
from metamorphic_guard.report_schema import Report

def generate_custom_report(result: Dict[str, Any]) -> str:
    report = Report(**result)
    # Custom formatting
    return f"Custom format: {report.decision.adopt}"
```

---

## Performance Considerations

### Local Dispatcher
- **Overhead**: Minimal (thread creation)
- **Scalability**: Limited by CPU cores
- **Use Case**: Small to medium test suites (< 10k cases)

### Queue Dispatcher
- **Overhead**: Network latency + serialization
- **Scalability**: Horizontal (add workers)
- **Use Case**: Large test suites or distributed execution

### Recommendations
- Start with `LocalDispatcher` (default)
- Use `QueueDispatcher` for:
  - Test suites > 10k cases
  - Long-running tests (> 10s per case)
  - Distributed execution across machines

---

## Error Handling

### Worker Failures
- **Local**: Exception propagates to dispatcher; other threads continue
- **Queue**: Stale heartbeat detection triggers requeue; other workers continue

### Timeout Handling
- Per-test timeouts enforced by sandbox executor
- Global timeout in `QueueDispatcher.execute()` prevents indefinite hangs
- Timeout violations recorded as execution failures

### Resource Limits
- Memory limits enforced per test case via `--mem-mb`
- CPU limits via executor configuration (Docker, etc.)

---

## See Also

- [MR Library](mr-library.md) - Metamorphic relation catalog
- [Policy Documentation](policies.md) - Policy-as-code configuration
- [GitHub Actions](github-actions.md) - CI/CD integration

