# Performance Guidance

This guide provides recommendations for configuring Metamorphic Guard for optimal performance and resource usage across different task categories.

## Task Categories & Resource Profiles

### 1. Lightweight Logic (Local)
*   **Examples**: String manipulation, basic math, data validation.
*   **Bottleneck**: CPU (single core speed), Python interpreter overhead.
*   **Recommendations**:
    *   **Workers**: Set to `CPU count - 1`.
    *   **Batch Size**: High (100-1000 cases per batch) to reduce serialization overhead.
    *   **Executor**: `local` or `process`.
    *   **Queue**: `memory` (fastest) or `redis` (if distributing across machines).

### 2. Heavy Computation / ML Inference (Local/GPU)
*   **Examples**: Local LLM inference, image processing, complex simulations.
*   **Bottleneck**: GPU/CPU compute, Memory.
*   **Recommendations**:
    *   **Workers**: Limit based on available VRAM/RAM. Often 1-2 per GPU.
    *   **Batch Size**: Small (1-10 cases) to prevent timeouts and allow granular scheduling.
    *   **Timeout**: Increase `global_timeout` and `task_timeout` significantly.
    *   **Sandbox**: Use `docker` with resource limits (`mem_mb`) to prevent OOM crashes.

### 3. I/O Bound / Remote API Calls
*   **Examples**: Calling OpenAI/Anthropic APIs, database queries.
*   **Bottleneck**: Network latency, Rate limits.
*   **Recommendations**:
    *   **Workers**: Can be much higher than CPU count (e.g., 20-50 threads).
    *   **Executor**: `thread` (for low overhead I/O).
    *   **Batch Size**: Moderate (10-50).
    *   **Rate Limiting**: Critical. Use `TokenBucketRateLimiter` or similar middleware to respect API quotas.
    *   **Bootstrap Sampling**: Can be expensive with large `n`. Use `n=50-100` for quick checks, `n=400+` for final release gates.

## Bootstrap Sampling Performance
Bootstrap sampling is CPU-intensive, especially with large `n` and `samples` (default 5000).
*   **Complexity**: O(n * samples).
*   **Optimization**:
    *   The system uses vectorized NumPy operations.
    *   For `n > 1000`, consider reducing `samples` to 1000-2000 for faster feedback loop.
    *   Use `fast_bootstrap=True` (if available) for approximate checks.

## Queue Dispatcher Tuning
*   **Heartbeat Timeout**: Default 45s. Lower this (e.g., 10s) for high-throughput environments to detect failures faster.
*   **Lease Seconds**: Should be at least `avg_task_duration * batch_size * 1.5`.
*   **Backpressure**: The dispatcher will warn if `queue_pending` > `workers * batch_size * 2`. If you see this, add more workers or reduce `n`.

## Profiling
Enable the `PerformanceProfiler` monitor to get detailed breakdown of:
*   Latency (p50, p95, p99)
*   Cost (for LLMs)
*   Success rates
*   Throughput (cases/sec)

```toml
# Example config
[monitors]
list = ["profiler"]
```


