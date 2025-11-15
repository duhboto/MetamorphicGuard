# Type Safety Audit: `Any` Type Usages

**Audit Date**: 2025-01-11  
**Total `Any` Usages**: 493 across 59 files  
**Goal**: Zero `Any` types in public API, >90% type coverage overall

## Priority Categories

### P0 - Public API (Must Fix First)
These affect the public API surface and should be fixed immediately to improve type safety for downstream users.

| File | Count | Key Locations |
|------|-------|---------------|
| `api.py` | 30 | TaskSpec.gen_inputs, TaskSpec.equivalence, Implementation.from_callable, Implementation.func |
| `llm_harness.py` | 6 | LLMHarness.run(), LLMHarness._execute() |
| **Total P0** | **36** | |

### P1 - Core Harness (High Priority)
These affect core evaluation logic and statistics.

| File | Count | Key Locations |
|------|-------|---------------|
| `harness.py` | 62 | _serialize_for_report(), _fingerprint_payload(), run_eval() |
| `harness/reporting.py` | 42 | evaluate_roles(), evaluate_results(), report generation |
| `harness/statistics.py` | 12 | Statistical computation functions |
| `harness/execution.py` | 14 | Execution logic |
| `harness/trust.py` | 4 | Trust score computation |
| `gate.py` | 5 | Adoption decision logic |
| **Total P1** | **139** | |

### P2 - Sandbox & Execution (Medium Priority)
Sandbox execution, executors, and dispatch logic.

| File | Count | Key Locations |
|------|-------|---------------|
| `sandbox.py` | 24 | run_in_sandbox(), _finalize_result(), executor configs |
| `dispatch.py` | 11 | Dispatcher.execute(), RunCase |
| `dispatch_queue.py` | 3 | QueueDispatcher.execute() |
| `executors/openai.py` | 6 | OpenAIExecutor.__call__(), error handling |
| `executors/anthropic.py` | 6 | AnthropicExecutor.__call__() |
| `executors/vllm.py` | 8 | VLLMExecutor.__call__(), kwargs |
| `executors/__init__.py` | 9 | Executor registry |
| **Total P2** | **67** | |

### P3 - CLI & Utilities (Lower Priority)
Command-line interface and utility functions.

| File | Count | Key Locations |
|------|-------|---------------|
| `cli/evaluate.py` | 2 | _maybe_float() |
| `cli/main.py` | 2 | CLI.__init__() |
| `cli/utils.py` | 9 | Utility functions |
| `cli/scaffold.py` | 4 | Plugin scaffolding |
| `util.py` | 6 | General utilities |
| `queue_serialization.py` | 3 | Serialization helpers |
| **Total P3** | **26** | |

### P4 - Plugins & Extensions (Lower Priority)
Plugin system, judges, mutants, monitors.

| File | Count | Key Locations |
|------|-------|---------------|
| `monitoring.py` | 26 | Monitor classes, records |
| `judges/__init__.py` | 11 | Judge base classes |
| `judges/structured.py` | 10 | Structured judges |
| `judges/rag_guards.py` | 13 | RAG guard judges |
| `judges/llm_as_judge.py` | 10 | LLM-as-judge |
| `judges/builtin.py` | 9 | Built-in judges |
| `mutants/__init__.py` | 4 | Mutant base classes |
| `mutants/builtin.py` | 4 | Built-in mutants |
| `mutants/advanced.py` | 6 | Advanced mutants |
| `plugins.py` | 8 | Plugin registry |
| `llm_specs.py` | 16 | LLM spec helpers |
| **Total P4** | **117** | |

### P5 - Supporting Modules (Lowest Priority)
Reporting, notifications, observability, and other supporting code.

| File | Count | Key Locations |
|------|-------|---------------|
| `reporting.py` | 23 | Report generation |
| `report_schema.py` | 10 | Report schema definitions |
| `notifications.py` | 7 | Webhook notifications |
| `observability.py` | 9 | Metrics and logging |
| `policy.py` | 12 | Policy parsing |
| `errors.py` | 4 | Error context (Dict[str, Any]) |
| `specs.py` | 8 | Spec definitions |
| `adaptive.py` | 7 | Adaptive testing |
| `agent_tracing.py` | 12 | Agent tracing |
| `cost_estimation.py` | 3 | Cost estimation |
| `redaction.py` | 4 | Secret redaction |
| `audit.py` | 7 | Audit logging |
| `stability_audit.py` | 4 | Stability audits |
| `shrink.py` | 10 | Input shrinking |
| `heartbeat_manager.py` | 3 | Heartbeat management |
| `queue_adapter.py` | 3 | Queue adapters |
| `mr/library.py` | 2 | MR library |
| `mr/prioritization.py` | 4 | MR prioritization |
| `rag_guards/__init__.py` | 4 | RAG guards |
| `mutant_bank/rag_mutants.py` | 3 | RAG mutants |
| `worker.py` | 2 | Worker process |
| `junit.py` | 2 | JUnit output |
| `logging.py` | 2 | Logging utilities |
| `telemetry.py` | 2 | Telemetry |
| `stability.py` | 2 | Stability checks |
| `sandbox_workspace.py` | 2 | Sandbox workspace |
| `harness/adaptive_execution.py` | 8 | Adaptive execution |
| **Total P5** | **148** | |

## Summary by Priority

| Priority | Count | Percentage |
|----------|-------|------------|
| P0 (Public API) | 36 | 7.3% |
| P1 (Core Harness) | 139 | 28.2% |
| P2 (Sandbox & Execution) | 67 | 13.6% |
| P3 (CLI & Utilities) | 26 | 5.3% |
| P4 (Plugins & Extensions) | 117 | 23.7% |
| P5 (Supporting Modules) | 148 | 30.0% |
| **Total** | **493** | **100%** |

## Common Patterns

### Pattern 1: Callable Types
**Location**: `api.py`, `specs.py`, `dispatch.py`
**Issue**: `Callable[..., Any]` used instead of typed callables
**Fix**: Use `TypeVar` with generic constraints

```python
# Before
gen_inputs: Callable[[int, int], List[Tuple[Any, ...]]]
equivalence: Callable[[Any, Any], bool]

# After
from typing import TypeVar, Generic
T = TypeVar('T')
gen_inputs: Callable[[int, int], List[Tuple[T, ...]]]
equivalence: Callable[[T, T], bool]
```

### Pattern 2: Dict[str, Any] for JSON-like Data
**Location**: `errors.py`, `policy.py`, `harness.py`
**Issue**: Using `Dict[str, Any]` for flexible dictionaries
**Fix**: Use Pydantic models or TypedDict

```python
# Before
details: Dict[str, Any]

# After
from typing import TypedDict
class ErrorDetails(TypedDict, total=False):
    error_code: str
    stack_trace: str
    metadata: Dict[str, str]
details: ErrorDetails
```

### Pattern 3: Result Serialization
**Location**: `harness.py`, `sandbox.py`
**Issue**: `_serialize_for_report(value: Any)` for arbitrary values
**Fix**: Use Union of known types

```python
# Before
def _serialize_for_report(value: Any) -> Any:

# After
from typing import Union, List, Dict
Serializable = Union[str, int, float, bool, None, List['Serializable'], Dict[str, 'Serializable']]
def _serialize_for_report(value: Serializable) -> Serializable:
```

### Pattern 4: Executor Configs
**Location**: `executors/*.py`, `sandbox.py`
**Issue**: `executor_config: Optional[Dict[str, Any]]`
**Fix**: Define TypedDict for each executor

```python
# Before
executor_config: Optional[Dict[str, Any]] = None

# After
from typing import TypedDict
class OpenAIExecutorConfig(TypedDict, total=False):
    api_key: str
    model: str
    temperature: float
executor_config: Optional[OpenAIExecutorConfig] = None
```

### Pattern 5: Monitor Records
**Location**: `monitoring.py`, `harness/reporting.py`
**Issue**: `MonitorRecord` uses `Dict[str, Any]` for flexible data
**Fix**: Use TypedDict or Pydantic models per monitor type

## Implementation Plan

### Phase 1.1.2: Replace `Any` in Public API (P0)
1. **api.py** (30 usages)
   - TaskSpec.gen_inputs: Use TypeVar for input type
   - TaskSpec.equivalence: Use TypeVar for output type
   - Implementation.func: Use Protocol for callable interface
   - Implementation.from_callable: Type the callable parameter

2. **llm_harness.py** (6 usages)
   - LLMHarness.run(): Define typed return schema
   - LLMHarness._execute(): Type executor results

### Phase 1.1.3: Replace `Any` in Core Harness (P1)
1. **harness.py** (62 usages)
   - _serialize_for_report(): Use recursive Serializable type
   - _fingerprint_payload(): Use Hashable union type
   - run_eval(): Define typed result schema

2. **harness/reporting.py** (42 usages)
   - evaluate_roles(): Type result dictionaries
   - evaluate_results(): Type metric aggregations

3. **harness/statistics.py** (12 usages)
   - Statistical functions: Use numeric type unions
   - CI computation: Type bootstrap results

### Phase 1.1.4: Replace `Any` in CLI (P3)
1. **cli/main.py** (2 usages)
   - CLI.__init__(): Use Click's types

2. **cli/evaluate.py** (2 usages)
   - _maybe_float(): Use Union[str, int, float]

### Phase 1.1.5: Replace `Any` in Executors (P2)
1. **executors/openai.py** (6 usages)
   - Define OpenAIExecutorConfig TypedDict
   - Type response models

2. **executors/anthropic.py** (6 usages)
   - Define AnthropicExecutorConfig TypedDict
   - Type response models

3. **executors/vllm.py** (8 usages)
   - Define VLLMExecutorConfig TypedDict
   - Type kwargs

4. **sandbox.py** (24 usages)
   - _finalize_result(): Type result schema
   - Executor configs: Use TypedDict

## Success Criteria

- [ ] Zero `Any` types in `api.py` and `llm_harness.py` (public API)
- [ ] >90% type coverage overall (measured by mypy --strict)
- [ ] All public functions have complete type annotations
- [ ] CI fails on type errors (mypy --strict in CI)
- [ ] Type stubs created for external dependencies

## Notes

- Some `Any` usages may be necessary for runtime flexibility (e.g., JSON deserialization)
- Document any intentionally retained `Any` types with comments explaining why
- Prioritize public API first, then core harness, then supporting modules
- Use `# type: ignore` sparingly and always with a comment explaining why



