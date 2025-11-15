# Advanced Patterns and Use Cases

This guide covers advanced patterns for using Metamorphic Guard in production environments.

## Table of Contents

1. [Large-Scale Evaluations](#large-scale-evaluations)
2. [Multi-Model Comparisons](#multi-model-comparisons)
3. [Cost-Optimized LLM Evaluation](#cost-optimized-llm-evaluation)
4. [Custom Metamorphic Relations](#custom-metamorphic-relations)
5. [Performance Tuning](#performance-tuning)
6. [Distributed Execution Patterns](#distributed-execution-patterns)

## Large-Scale Evaluations

### Handling 10k+ Test Cases

For large test suites, use distributed execution with result caching:

```python
from metamorphic_guard import run_eval
from metamorphic_guard.result_cache import get_result_cache, clear_result_cache

# Clear cache if needed
clear_result_cache()

# Use queue dispatcher for distributed execution
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    n=10000,
    parallel=None,  # Auto-detect optimal worker count
    dispatcher="queue",
    queue_config={
        "backend": "redis",
        "url": "redis://localhost:6379/0",
        "adaptive_batching": True,
        "max_batch_size": 32,
        "enable_requeue": True,
        "max_requeue_attempts": 3,
    },
    # Enable result caching
    executor_config={"enable_cache": True},
)

# Check cache statistics
cache = get_result_cache()
print(f"Cache utilization: {cache.stats()['utilization']:.2%}")
```

### Memory Management for Large Suites

Use memory optimization utilities for very large evaluations:

```python
from metamorphic_guard.memory_optimization import (
    suggest_memory_optimizations,
    compact_results,
    stream_results,
)

# Check memory recommendations
suggestions = suggest_memory_optimizations(n=50000, estimated_result_size=2048)
print(suggestions)

# Compact results after evaluation
result = run_eval(...)
baseline_results = compact_results(result["baseline"]["results"])
candidate_results = compact_results(result["candidate"]["results"])
```

## Multi-Model Comparisons

### Comparing Multiple Candidates

Compare a baseline against multiple candidates efficiently:

```python
from metamorphic_guard import run_eval
from pathlib import Path

baseline_path = "baseline.py"
candidates = {
    "candidate_v1": "candidate_v1.py",
    "candidate_v2": "candidate_v2.py",
    "candidate_v3": "candidate_v3.py",
}

results = {}
for name, path in candidates.items():
    result = run_eval(
        task_name="my_task",
        baseline_path=baseline_path,
        candidate_path=path,
        n=1000,
        report_dir=Path("reports") / name,
    )
    results[name] = result

# Find best candidate
best = max(results.items(), key=lambda x: x[1]["delta_pass_rate"])
print(f"Best candidate: {best[0]} with Δ={best[1]['delta_pass_rate']:.4f}")
```

### A/B Testing with Statistical Significance

Run multiple evaluations and compare with proper statistical correction:

```python
from metamorphic_guard import run_eval
from metamorphic_guard.multiple_comparisons import apply_fwer_correction

# Run evaluations
results = []
for candidate in candidates:
    result = run_eval(
        task_name="my_task",
        baseline_path="baseline.py",
        candidate_path=candidate,
        n=2000,
        alpha=0.05,
        relation_correction="fwer",  # Family-wise error rate correction
    )
    results.append(result)

# Apply correction for multiple comparisons
corrected = apply_fwer_correction(results, alpha=0.05, method="bonferroni")
```

## Cost-Optimized LLM Evaluation

### Pre-Run Cost Estimation

Estimate costs before running expensive LLM evaluations:

```python
from metamorphic_guard.cost_estimation import estimate_and_check_budget, BudgetAction
from metamorphic_guard.model_registry import get_model_metadata

# Get model pricing
model_info = get_model_metadata("gpt-4")
print(f"Model: {model_info.name}")
print(f"Input: ${model_info.pricing.input_per_1k_tokens:.4f}/1k tokens")
print(f"Output: ${model_info.pricing.output_per_1k_tokens:.4f}/1k tokens")

# Estimate cost
estimate = estimate_and_check_budget(
    executor_name="openai",
    executor_config={"model": "gpt-4"},
    n=1000,
    budget_limit=50.0,  # Hard limit
    warning_threshold=10.0,  # Warning threshold
    action=BudgetAction.WARN,
    system_prompt="You are a helpful assistant.",
    user_prompts=["Example prompt 1", "Example prompt 2"],
    max_tokens=512,
)

print(f"Estimated cost: ${estimate['estimated_cost_usd']:.2f}")
print(f"Budget check: {estimate['budget_check']['status']}")
```

### Budget-Aware Evaluation

Run evaluations with budget controls:

```bash
metamorphic-guard evaluate \
  --task llm_task \
  --baseline baseline.py \
  --candidate candidate.py \
  --executor openai \
  --executor-config '{"model":"gpt-4"}' \
  --estimate-cost \
  --budget-limit 50.0 \
  --budget-warning 10.0 \
  --budget-action warn \
  --n 1000
```

## Custom Metamorphic Relations

### Creating Domain-Specific Relations

Define custom metamorphic relations for your domain:

```python
from metamorphic_guard.specs import MetamorphicRelation
import random

def add_noise_relation(input_data, rng=None):
    """Add small noise to input, output should be similar."""
    if rng is None:
        rng = random.Random()
    
    # Add 1% noise
    if isinstance(input_data, (list, tuple)):
        return tuple(x * (1 + rng.uniform(-0.01, 0.01)) for x in input_data)
    return input_data * (1 + rng.uniform(-0.01, 0.01))

def scale_invariance(input_data, rng=None):
    """Scale input by factor, output should scale proportionally."""
    if rng is None:
        rng = random.Random()
    
    scale = rng.uniform(0.5, 2.0)
    if isinstance(input_data, (list, tuple)):
        return tuple(x * scale for x in input_data)
    return input_data * scale

# Use in task spec
from metamorphic_guard.specs import task, Spec, Property

@task("my_domain_task")
def my_task_spec() -> Spec:
    return Spec(
        gen_inputs=lambda n, seed: [(i * 0.1,) for i in range(n)],
        properties=[
            Property(
                check=lambda out, x: out > 0,
                description="Output is positive"
            )
        ],
        relations=[
            MetamorphicRelation(
                name="add_noise",
                transform=add_noise_relation,
                expect="similar",  # Use similarity check
                accepts_rng=True,
                category="robustness",
                description="Output should be stable to small input perturbations"
            ),
            MetamorphicRelation(
                name="scale_invariance",
                transform=scale_invariance,
                expect="proportional",
                accepts_rng=True,
                category="invariance",
                description="Output should scale proportionally with input"
            )
        ],
        equivalence=lambda a, b: abs(a - b) < 0.001,
    )
```

## Performance Tuning

### Optimizing Worker Pools

Tune parallel execution for your workload:

```python
import os

# Auto-detect optimal workers
cpu_count = os.cpu_count() or 4

# For I/O-bound tasks (sandbox execution)
workers_io = cpu_count * 2

# For CPU-bound tasks
workers_cpu = cpu_count

result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    parallel=workers_io,  # Or use None for auto-detection
    dispatcher="local",
)
```

### Adaptive Batching Configuration

Configure adaptive batching for optimal throughput:

```python
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    dispatcher="queue",
    queue_config={
        "backend": "redis",
        "adaptive_batching": True,
        "initial_batch_size": 4,
        "min_batch_size": 1,
        "max_batch_size": 32,
        "adjustment_window": 10,
        "adaptive_fast_threshold_ms": 50.0,
        "adaptive_slow_threshold_ms": 500.0,
        "inflight_factor": 2,
    },
)
```

### Result Caching Strategy

Enable caching for repeated evaluations:

```python
from metamorphic_guard.result_cache import get_result_cache

# Configure cache size
cache = get_result_cache(max_size=50000)

# Run evaluation with caching enabled (default)
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    # Caching is enabled by default for non-LLM executors
)

# Check cache hit rate
stats = cache.stats()
print(f"Cache size: {stats['size']}/{stats['max_size']}")
print(f"Utilization: {stats['utilization']:.2%}")
```

## Distributed Execution Patterns

### Multi-Region Deployment

Deploy workers across regions with SQS:

```python
# US East region
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    dispatcher="queue",
    queue_config={
        "backend": "sqs",
        "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/my-queue",
        "region_name": "us-east-1",
        "visibility_timeout": 60,
        "max_receive_count": 3,
    },
)

# EU West region
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    dispatcher="queue",
    queue_config={
        "backend": "sqs",
        "queue_url": "https://sqs.eu-west-1.amazonaws.com/123456789/my-queue",
        "region_name": "eu-west-1",
    },
)
```

### Auto-Scaling Worker Pools

Use auto-scaling for dynamic workloads:

```python
from metamorphic_guard.dispatch.auto_scaling import create_auto_scaler
from metamorphic_guard.queue_adapter import RedisQueueAdapter

adapter = RedisQueueAdapter({"url": "redis://localhost:6379/0"})

# Create auto-scaler
scaler = create_auto_scaler(
    adapter,
    config={
        "enabled": True,
        "min_workers": 2,
        "max_workers": 50,
        "target_queue_depth": 10,
        "scale_up_threshold": 20,
        "scale_down_threshold": 5,
        "scale_up_factor": 1.5,
        "scale_down_factor": 0.8,
        "cooldown_seconds": 30.0,
    },
)

# Monitor and scale
current_workers = 10
queue_depth = adapter.pending_count()
recommended = scaler.get_recommended_workers(current_workers)
print(f"Recommended workers: {recommended} (current: {current_workers})")
```

### Fault-Tolerant Execution

Configure for high reliability:

```python
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    dispatcher="queue",
    queue_config={
        "backend": "redis",
        "enable_requeue": True,
        "max_requeue_attempts": 3,
        "heartbeat_timeout": 45.0,
        "circuit_breaker_threshold": 3,
        "lease_seconds": 30.0,
    },
)
```

## Advanced Monitoring

### Custom Performance Profiling

Use the performance profiler for detailed analysis:

```python
from metamorphic_guard.profiling import PerformanceProfiler

# Enable profiler
result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    monitors=[PerformanceProfiler()],
)

# Export profiling data
from metamorphic_guard.cli.profile import export_profile
from pathlib import Path

report_path = Path("reports/report_123.json")
export_profile(report_path, format="json", output=Path("profile.json"))
export_profile(report_path, format="csv", output=Path("profile.csv"))
```

### Composite Monitoring

Combine multiple monitors:

```python
from metamorphic_guard.monitoring import create_composite_monitor
from metamorphic_guard.monitors import LatencyMonitor, LLMCostMonitor

# Create composite monitor
composite = create_composite_monitor([
    LatencyMonitor(percentile=0.99),
    LLMCostMonitor(),
])

result = run_eval(
    task_name="my_task",
    baseline_path="baseline.py",
    candidate_path="candidate.py",
    monitors=[composite],
)
```

## Best Practices

1. **Start Small**: Begin with small test suites (n=100-400) and scale up
2. **Use Caching**: Enable result caching for repeated evaluations
3. **Monitor Costs**: Always estimate costs before large LLM evaluations
4. **Configure Timeouts**: Set appropriate timeouts for your workload
5. **Enable Requeeue**: Use requeue for distributed execution reliability
6. **Track Metrics**: Enable Prometheus metrics for observability
7. **Use Policies**: Define policies as code for consistent gating
8. **Version Control**: Track policy versions and report provenance

