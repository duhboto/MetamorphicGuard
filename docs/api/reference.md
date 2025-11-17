# API Reference

Complete API documentation for Metamorphic Guard.

## Table of Contents

1. [Core API](#core-api)
2. [Task Specification](#task-specification)
3. [LLM Harness](#llm-harness)
4. [Configuration](#configuration)
5. [Monitors](#monitors)
6. [Queue Adapters](#queue-adapters)
7. [Utilities](#utilities)

## Core API

### `run()`

Execute a baseline vs candidate evaluation.

```python
from metamorphic_guard import run, TaskSpec, Implementation

result = run(
    task: TaskSpec,
    baseline: Implementation,
    candidate: Implementation,
    config: Optional[EvaluationConfig] = None,
    *,
    alert_webhooks: Optional[Sequence[str]] = None,
    alert_metadata: Optional[Mapping[str, JSONValue]] = None,
    dispatcher: Optional[Union[str, Dispatcher]] = None,
    queue_config: Optional[QueueConfig] = None,
    monitors: Optional[Sequence[Monitor]] = None,
    monitor_specs: Optional[Sequence[str]] = None,
    sandbox_plugins: Optional[bool] = None,
    logging_enabled: Optional[bool] = None,
    log_path: Optional[str | Path] = None,
    log_context: Optional[Mapping[str, JSONValue]] = None,
    metrics_enabled: Optional[bool] = None,
    metrics_port: Optional[int] = None,
    metrics_host: Optional[str] = None,
) -> EvaluationResult
```

**Parameters:**
- `task`: TaskSpec defining the evaluation task
- `baseline`: Implementation reference for baseline
- `candidate`: Implementation reference for candidate
- `config`: Optional EvaluationConfig for evaluation settings
- `alert_webhooks`: Optional list of webhook URLs for alerts
- `alert_metadata`: Optional metadata to include in alerts
- `dispatcher`: Dispatcher name or instance ("local", "queue", or custom)
- `queue_config`: Configuration for queue dispatcher
- `monitors`: Optional list of Monitor instances
- `monitor_specs`: Optional list of monitor spec strings
- `sandbox_plugins`: Whether to sandbox plugin monitors
- `logging_enabled`: Enable structured logging
- `log_path`: Path to log file
- `log_context`: Additional context for logs
- `metrics_enabled`: Enable Prometheus metrics
- `metrics_port`: Port for metrics server
- `metrics_host`: Host for metrics server

**Returns:**
- `EvaluationResult`: Result containing report and adoption decision

**Example:**
```python
from metamorphic_guard import run, TaskSpec, Implementation

task = TaskSpec(
    name="my_task",
    gen_inputs=lambda n, seed: [(i,) for i in range(n)],
    properties=[...],
    relations=[...],
    equivalence=lambda a, b: a == b,
)

result = run(
    task=task,
    baseline=Implementation.from_path("baseline.py"),
    candidate=Implementation.from_path("candidate.py"),
)

print(f"Adopt: {result.adopt}")
print(f"Reason: {result.reason}")
```

### `run_with_config()`

Execute evaluation using configuration file or dictionary.

```python
from metamorphic_guard import run_with_config

result = run_with_config(
    config: Union[EvaluatorConfig, str, Path, Mapping[str, JSONValue]],
    *,
    task: TaskSpec,
    alert_webhooks: Optional[Sequence[str]] = None,
    alert_metadata: Optional[Mapping[str, JSONValue]] = None,
    dispatcher: Optional[Union[str, Dispatcher]] = None,
    queue_config: Optional[QueueConfig] = None,
    monitors: Optional[Sequence[Monitor]] = None,
    monitor_specs: Optional[Sequence[str]] = None,
    sandbox_plugins: Optional[bool] = None,
    logging_enabled: Optional[bool] = None,
    log_path: Optional[str | Path] = None,
    log_context: Optional[Mapping[str, JSONValue]] = None,
    metrics_enabled: Optional[bool] = None,
    metrics_port: Optional[int] = None,
    metrics_host: Optional[str] = None,
) -> EvaluationResult
```

**Parameters:**
- `config`: Configuration as EvaluatorConfig, file path, or dict
- `task`: TaskSpec (required)
- Other parameters same as `run()`

**Example:**
```python
# From TOML file
result = run_with_config("guard.toml", task=my_task)

# From dict
config = {
    "metamorphic_guard": {
        "task": "my_task",
        "baseline": "baseline.py",
        "candidate": "candidate.py",
        "n": 1000,
    }
}
result = run_with_config(config, task=my_task)
```

### `run_eval()`

Low-level evaluation function (used internally by `run()`).

```python
from metamorphic_guard.harness import run_eval

result = run_eval(
    task_name: str,
    baseline_path: str,
    candidate_path: str,
    n: int = 400,
    seed: int = 42,
    timeout_s: float = 2.0,
    mem_mb: int = 512,
    alpha: float = 0.05,
    violation_cap: int = 25,
    parallel: int | None = None,
    min_delta: float = 0.02,
    bootstrap_samples: int = 1000,
    ci_method: str = "bootstrap",
    # ... many more parameters
) -> JSONDict
```

**See:** `metamorphic_guard.harness.run_eval` for full parameter list.

## Task Specification

### `TaskSpec`

User-facing task specification dataclass.

```python
@dataclass(frozen=True)
class TaskSpec:
    name: str
    gen_inputs: Callable[[int, int], List[Tuple[object, ...]]]
    properties: Sequence[Property]
    relations: Sequence[MetamorphicRelation]
    equivalence: Callable[[object, object], bool]
    fmt_in: Callable[[Tuple[object, ...]], str] = lambda args: str(args)
    fmt_out: Callable[[object], str] = lambda result: str(result)
    cluster_key: Optional[Callable[[Tuple[object, ...]], Hashable]] = None
    metrics: Sequence[Metric] = field(default_factory=tuple)
```

**Fields:**
- `name`: Unique task name
- `gen_inputs`: Function generating test inputs `(n, seed) -> List[Tuple]`
- `properties`: List of Property objects to check
- `relations`: List of MetamorphicRelation objects
- `equivalence`: Function comparing two outputs for equality
- `fmt_in`: Function formatting inputs for display
- `fmt_out`: Function formatting outputs for display
- `cluster_key`: Optional function for clustering test cases
- `metrics`: Optional list of Metric objects

**Methods:**
- `to_spec() -> Spec`: Convert to internal Spec representation

### `Property`

Property to verify on outputs.

```python
@dataclass(frozen=True)
class Property:
    check: Callable[[object, ...], bool]
    description: str
    mode: str = "required"  # "required" or "optional"
```

**Fields:**
- `check`: Function `(output, *args) -> bool`
- `description`: Human-readable description
- `mode`: "required" (must pass) or "optional" (informational)

### `MetamorphicRelation`

Metamorphic relation defining input transformations.

```python
@dataclass(frozen=True)
class MetamorphicRelation:
    name: str
    transform: Callable[..., Tuple[object, ...]]
    expect: str  # "equal", "similar", "proportional", etc.
    accepts_rng: bool = False
    category: Optional[str] = None
    description: Optional[str] = None
```

**Fields:**
- `name`: Unique relation name
- `transform`: Function transforming inputs `(*args, rng=None) -> Tuple`
- `expect`: Expected relationship ("equal", "similar", "proportional")
- `accepts_rng`: Whether transform accepts random number generator
- `category`: Optional category for grouping
- `description`: Optional description

### `Metric`

Metric to extract and aggregate from results.

```python
@dataclass(frozen=True)
class Metric:
    name: str
    extract: Callable[[object, Tuple[object, ...]], Optional[float]]
    kind: str  # "mean", "sum", "min", "max", "count"
    sample_rate: float = 1.0
```

**Fields:**
- `name`: Metric name
- `extract`: Function `(output, args) -> Optional[float]`
- `kind`: Aggregation kind ("mean", "sum", "min", "max", "count")
- `sample_rate`: Fraction of cases to sample (0.0-1.0)

### `Implementation`

Reference to an implementation (file or callable).

```python
@dataclass(frozen=True)
class Implementation:
    path: Optional[str] = None
    callable: Optional[Callable] = None
    dotted: Optional[str] = None

    @classmethod
    def from_path(cls, path: str) -> Implementation:
        """Create from file path."""
    
    @classmethod
    def from_callable(cls, func: Callable) -> Implementation:
        """Create from callable."""
    
    @classmethod
    def from_dotted(cls, dotted: str) -> Implementation:
        """Create from dotted path like 'module:function'."""
    
    def materialize(self) -> ContextManager[str]:
        """Materialize implementation, returning context manager."""
```

## LLM Harness

### `LLMHarness`

High-level wrapper for LLM model evaluation.

```python
from metamorphic_guard.llm_harness import LLMHarness

harness = LLMHarness(
    model: str = "gpt-3.5-turbo",
    provider: str = "openai",
    executor_config: Optional[ExecutorConfig] = None,
    max_tokens: int = 512,
    temperature: float = 0.0,
    seed: Optional[int] = None,
    baseline_model: Optional[str] = None,
    baseline_provider: Optional[str] = None,
    baseline_executor_config: Optional[ExecutorConfig] = None,
)
```

**Methods:**

#### `run()`

Run LLM evaluation.

```python
report = harness.run(
    case: LLMCaseInput,
    props: Optional[Sequence[Judge | LLMJudge]] = None,
    mrs: Optional[Sequence[Mutant | PromptMutant]] = None,
    n: int = 100,
    seed: int = 42,
    bootstrap: bool = True,
    baseline_model: Optional[str] = None,
    baseline_system: Optional[str] = None,
    **kwargs: JSONValue,
) -> EvaluationReport
```

**Parameters:**
- `case`: Input case (dict with "system"/"user", list of messages, or string)
- `props`: List of judges to evaluate outputs
- `mrs`: List of mutants to apply to inputs
- `n`: Number of test cases
- `seed`: Random seed
- `bootstrap`: Whether to compute bootstrap CIs
- `baseline_model`: Optional baseline model name
- `baseline_system`: Optional baseline system prompt
- `**kwargs`: Additional arguments passed to `run_eval`

**Returns:**
- `EvaluationReport`: Dictionary with evaluation results

## Configuration

### `EvaluationConfig`

Configuration dataclass for evaluations.

```python
@dataclass
class EvaluationConfig:
    task: str
    baseline: str
    candidate: str
    n: int = 400
    seed: int = 42
    timeout_s: float = 2.0
    mem_mb: int = 512
    alpha: float = 0.05
    min_delta: float = 0.02
    min_pass_rate: float = 0.80
    violation_cap: int = 25
    parallel: int = 1
    bootstrap_samples: int = 1000
    ci_method: str = "bootstrap"
    # ... many more fields
```

**See:** `metamorphic_guard.config.EvaluatorConfig` for complete field list.

### `PolicyConfig`

Policy configuration TypedDict.

```python
class PolicyConfig(TypedDict, total=False):
    gating: Dict[str, JSONValue]
    descriptor: Dict[str, JSONValue]
    name: str
```

### `QueueConfig`

Queue configuration TypedDict.

```python
class QueueConfig(TypedDict, total=False):
    backend: str  # "memory", "redis", "sqs", "rabbitmq", "kafka"
    url: str  # For Redis
    queue_url: str  # For SQS
    # ... backend-specific fields
```

## Monitors

### `Monitor`

Base class for monitors.

```python
class Monitor(ABC):
    @abstractmethod
    def start(self, context: MonitorContext) -> None:
        """Initialize monitor with evaluation context."""
    
    @abstractmethod
    def record(self, record: MonitorRecord) -> None:
        """Record a test case execution."""
    
    @abstractmethod
    def finalize(self) -> Dict[str, Any]:
        """Finalize and return monitor data."""
    
    @property
    @abstractmethod
    def identifier(self) -> str:
        """Return monitor identifier."""
```

### Built-in Monitors

- `LatencyMonitor`: Tracks execution latency
- `LLMCostMonitor`: Tracks LLM API costs
- `FairnessGapMonitor`: Tracks fairness across groups
- `ResourceMonitor`: Tracks resource usage
- `PerformanceProfiler`: Comprehensive performance profiling
- `CompositeMonitor`: Combines multiple monitors

## Queue Adapters

### `QueueAdapter`

Abstract base class for queue backends.

```python
class QueueAdapter(ABC):
    def publish_task(self, task: QueueTask) -> None:
        """Publish a task to the queue."""
    
    def consume_task(self, worker_id: str, timeout: float | None = None) -> Optional[QueueTask]:
        """Consume a task from the queue."""
    
    def publish_result(self, result: QueueResult) -> None:
        """Publish a result to the queue."""
    
    def consume_result(self, job_id: str, timeout: float | None = None) -> Optional[QueueResult]:
        """Consume a result from the queue."""
    
    def register_worker(self, worker_id: str) -> None:
        """Register or refresh worker heartbeat."""
    
    def worker_heartbeats(self) -> Dict[str, float]:
        """Return worker heartbeat timestamps."""
```

### Implementations

- `InMemoryQueueAdapter`: In-process queue
- `RedisQueueAdapter`: Redis-backed queue
- `SQSQueueAdapter`: AWS SQS queue
- `RabbitMQQueueAdapter`: RabbitMQ queue
- `KafkaQueueAdapter`: Apache Kafka queue

## Utilities

### Result Caching

```python
from metamorphic_guard.result_cache import get_result_cache, clear_result_cache

cache = get_result_cache(max_size=10000)
cached = cache.get(file_path, func_name, args)
cache.set(file_path, func_name, args, result)
stats = cache.stats()
clear_result_cache()
```

### Cost Estimation

Estimate LLM evaluation costs before running to avoid unexpected charges.

#### `estimate_llm_cost()`

Estimate cost for an LLM evaluation.

```python
from metamorphic_guard import estimate_llm_cost

estimate = estimate_llm_cost(
    executor_name="openai",
    executor_config={
        "api_key": "sk-...",
        "model": "gpt-4",
    },
    n=1000,  # Number of test cases
    system_prompt="You are a helpful assistant",
    user_prompts=["Example prompt 1", "Example prompt 2"],
    max_tokens=512,
    mutants=None,  # Optional list of mutants
    judges=None,  # Optional list of judges (may include LLM-as-judge)
)

print(f"Total cost: ${estimate['total_cost_usd']:.4f}")
print(f"  Baseline: ${estimate['baseline_cost_usd']:.4f}")
print(f"  Candidate: ${estimate['candidate_cost_usd']:.4f}")
print(f"  Judge: ${estimate['judge_cost_usd']:.4f}")
```

**Returns:**
- Dictionary with cost estimates and token counts

#### `estimate_and_check_budget()`

Estimate cost and check against budget limits.

```python
from metamorphic_guard import estimate_and_check_budget, BudgetAction

result = estimate_and_check_budget(
    executor_name="openai",
    executor_config={"api_key": "sk-...", "model": "gpt-4"},
    n=1000,
    budget_limit=50.0,  # Hard limit (raises BudgetExceededError if exceeded)
    warning_threshold=10.0,  # Warning threshold
    action=BudgetAction.WARN,  # Action on warning: ALLOW, WARN, or ABORT
    system_prompt="...",
    user_prompts=["..."],
    max_tokens=512,
)

if result["budget_check"]["action_taken"] == "abort":
    print("Budget exceeded! Aborting...")
```

**Returns:**
- Dictionary combining cost estimate and budget check results

**Raises:**
- `BudgetExceededError`: If estimated cost exceeds `budget_limit` and `action` is `ABORT`

#### `check_budget()`

Check estimated cost against budget limits.

```python
from metamorphic_guard import check_budget, BudgetAction

check_result = check_budget(
    estimated_cost=25.0,
    budget_limit=50.0,
    warning_threshold=10.0,
    action=BudgetAction.WARN,
)

if check_result["action_taken"] == "warn":
    print(f"⚠️  {check_result['message']}")
```

#### `BudgetAction`

Enum for budget action behavior:

- `ALLOW`: Allow evaluation regardless of budget
- `WARN`: Warn if budget threshold exceeded but continue
- `ABORT`: Abort evaluation if budget limit exceeded

### Model Registry

```python
from metamorphic_guard.model_registry import (
    get_model_metadata,
    register_model,
    list_models,
    is_valid_model,
)

metadata = get_model_metadata("gpt-4")
models = list_models(provider="openai")
is_valid = is_valid_model("gpt-4")
```

### Memory Optimization

```python
from metamorphic_guard.memory_optimization import (
    suggest_memory_optimizations,
    compact_results,
    stream_results,
)

suggestions = suggest_memory_optimizations(n=10000)
compact = compact_results(results)
for batch in stream_results(results, batch_size=100):
    process_batch(batch)
```

### Auto Scaling

```python
from metamorphic_guard.dispatch.auto_scaling import create_auto_scaler

scaler = create_auto_scaler(
    adapter,
    config={
        "enabled": True,
        "min_workers": 2,
        "max_workers": 50,
        "target_queue_depth": 10,
    },
)

recommended = scaler.get_recommended_workers(current_workers)
```

## Type Definitions

### `JSONDict`

Type alias for JSON-compatible dictionaries.

```python
JSONDict = Dict[str, JSONValue]
```

### `JSONValue`

Type alias for JSON-compatible values.

```python
JSONValue = Union[JSONPrimitive, JSONList, JSONDict]
```

### `EvaluationResult`

Result of an evaluation.

```python
@dataclass
class EvaluationResult:
    report: JSONDict
    adopt: bool
    reason: str
```

## Error Handling

### Exceptions

- `BudgetExceededError`: Raised when budget limit is exceeded
- `QueueSerializationError`: Raised when queue serialization fails
- `PolicyLoadError`: Raised when policy file cannot be loaded
- `PolicyParseError`: Raised when policy file is invalid

## See Also

- [Getting Started Guide](getting-started/quickstart.md)
- [Advanced Patterns](cookbook/advanced-patterns.md)
- [LLM Evaluation Guide](user-guide/llm-evaluation.md)

