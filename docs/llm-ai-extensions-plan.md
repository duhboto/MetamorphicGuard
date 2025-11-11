# LLM & AI Extensions Roadmap

## Alignment Analysis

These proposals align well with Metamorphic Guard's architecture:

### ✅ **Existing Foundation**
- **Plugin System**: Entry point discovery for monitors/dispatchers → can extend to LLM adapters, judges, mutants
- **Sandbox Execution**: Isolated execution environment → perfect for LLM API calls with cost/latency tracking
- **Statistical Framework**: Bootstrap CIs, pass-rate deltas → directly applicable to LLM evaluation
- **Monitoring System**: Latency, success rate, fairness monitors → can add LLM-specific metrics (tokens, cost, judge scores)
- **Observability**: Prometheus metrics, structured logging → ready for LLM telemetry
- **Distributed Execution**: Queue dispatcher → can handle LLM API rate limits and parallel evaluation

### 🎯 **Natural Extensions**

## Priority 1: Core LLM Integration (Starter Pack A)

### `metamorph-llm` Plugin Suite

**Integration Points:**
- **LLM Adapters** → New plugin group: `metamorphic_guard.executors` (extends sandbox system)
- **Prompt Mutants** → New plugin group: `metamorphic_guard.mutants` (extends relations system)
- **Judges** → New plugin group: `metamorphic_guard.judges` (extends property checking)
- **Cost/Latency Tracking** → Extends existing `ResourceUsageMonitor` and `LatencyMonitor`

**Architecture:**
```python
# New executor type for LLM calls
class LLMExecutor(Executor):
    """Executor that calls LLM APIs instead of Python code."""
    def run(self, prompt: str, **kwargs) -> LLMResult:
        # Handles OpenAI/Anthropic/local vLLM
        # Tracks tokens, cost, latency
        pass

# Mutants as metamorphic relations
class PromptMutant(MetamorphicRelation):
    """Transforms prompts to test robustness."""
    def transform(self, prompt: str) -> str:
        # paraphrase, role-swap, jailbreak, etc.
        pass

# Judges as property checkers
class LLMJudge(Property):
    """Structured evaluation of LLM outputs."""
    def check(self, output: str, **kwargs) -> bool:
        # rubric JSON, citation checks, etc.
        pass
```

**Implementation Plan:**
1. Extend `sandbox.py` to support `executor="llm"` with provider config
2. Add `metamorphic_guard.mutants` plugin group for prompt transformations
3. Add `metamorphic_guard.judges` plugin group for LLM output evaluation
4. Extend monitors to track LLM-specific metrics (tokens, cost per request)
5. Add `LLMHarness` wrapper that integrates with existing `run_eval`

### `pytest-metamorph` Plugin

**Integration Points:**
- Uses existing `run_eval` function
- Leverages existing HTML report generation
- Integrates with existing artifact storage

**Architecture:**
```python
# Pytest plugin that wraps MG
@pytest.fixture
def mg_eval():
    return run_eval  # Direct integration

@pytest.mark.metamorph(
    task="llm_chat",
    baseline="models/baseline.py",
    candidate="models/candidate.py"
)
def test_model_quality():
    # Runs MG evaluation, emits pytest results
    pass
```

## Priority 2: Domain-Specific Tools

### `mutant-bank` Library

**Integration:**
- Can be installed as optional dependency
- Mutants register as `metamorphic_guard.mutants` plugins
- Versioned packs with break rates stored in metadata

### `rag-guards` 

**Integration:**
- Judges register as `metamorphic_guard.judges` plugins
- Trust scores become monitor metrics
- Can use existing `FairnessGapMonitor` pattern for citation/attribution checks

### `agent-trace`

**Integration:**
- Extends existing artifact storage (`write_failed_artifacts`)
- Timeline recording can be a monitor that captures tool calls
- Replay functionality can integrate with sandbox executor

## Priority 3: Infrastructure Tools

### `policy-router`

**Integration:**
- Consumes MG metrics (from Prometheus or JSON reports)
- Uses existing `decide_adopt` gate logic
- Can be a dispatcher plugin that routes to different executors

### `promptgym`

**Integration:**
- Uses `run_eval` for each prompt variant
- Adoption decisions use existing gate logic
- Exports MG-compatible reports

### `runledger` & `telemetry-lite`

**Integration:**
- Extends existing observability (`observability.py`)
- Can export to OpenTelemetry format
- Git-native storage complements existing artifact system

## Implementation Strategy

### Phase 1: Core LLM Support (Weeks 1-2)
1. Add LLM executor to sandbox system
2. Create `metamorph-llm` package structure
3. Implement basic OpenAI/Anthropic adapters
4. Add token/cost tracking to monitors

### Phase 2: Mutants & Judges (Weeks 3-4)
1. Add `mutants` plugin group
2. Implement core prompt mutants (paraphrase, negation, jailbreak)
3. Add `judges` plugin group
4. Implement structured eval judges (rubric, citation)

### Phase 3: Pytest Integration (Week 5)
1. Create `pytest-metamorph` package
2. Add pytest markers and fixtures
3. Integrate with existing HTML reports

### Phase 4: Domain Tools (Weeks 6-8)
1. `mutant-bank` as standalone library
2. `rag-guards` with MG integration
3. `agent-trace` for multi-tool debugging

## File Structure Proposal

```
metamorphic_guard/
├── executors/          # New: LLM, RAG executors
│   ├── __init__.py
│   ├── llm.py         # LLM executor base
│   └── providers/        # OpenAI, Anthropic, local
├── mutants/            # New: Prompt mutation system
│   ├── __init__.py
│   ├── base.py
│   └── builtin.py     # paraphrase, negation, etc.
├── judges/             # New: LLM output evaluation
│   ├── __init__.py
│   ├── base.py
│   └── builtin.py     # rubric, citation, etc.
└── ... (existing files)

metamorph_llm/          # New package
├── __init__.py
├── harness.py          # LLMHarness wrapper
└── examples/

pytest_metamorph/       # New package
├── __init__.py
├── plugin.py           # Pytest integration
└── fixtures.py
```

## Next Steps

1. ✅ Create feature branch
2. Extend plugin system to support executors, mutants, judges
3. Implement LLM executor in sandbox
4. Create `metamorph-llm` package skeleton
5. Add first LLM provider (OpenAI)
6. Implement first mutant (paraphrase)
7. Implement first judge (length check)

