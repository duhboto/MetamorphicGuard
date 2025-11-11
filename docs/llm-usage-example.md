# LLM Evaluation with Metamorphic Guard

## Overview

Metamorphic Guard now supports LLM evaluation through plugin-based executors, mutants, and judges. This allows you to test LLM models for robustness, correctness, and safety.

## Quick Start

### 1. Install LLM Dependencies

```bash
pip install metamorphic-guard[llm]
# Or install openai separately:
pip install openai
```

### 2. Using LLMHarness (Recommended)

```python
from metamorphic_guard.llm_harness import LLMHarness
from metamorphic_guard.judges.builtin import LengthJudge, NoPIIJudge
from metamorphic_guard.mutants.builtin import ParaphraseMutant

# Initialize harness
h = LLMHarness(
    model="gpt-3.5-turbo",
    provider="openai",
    executor_config={"api_key": "sk-..."},  # Or set OPENAI_API_KEY env var
    max_tokens=512,
    temperature=0.0,
)

# Define test case
case = {
    "system": "You are a helpful assistant",
    "user": "Summarize AI safety in 3 sentences"
}

# Define judges (output evaluation)
judges = [
    LengthJudge(max_chars=300),
    NoPIIJudge(),
]

# Define mutants (input transformations)
mutants = [ParaphraseMutant()]

# Run evaluation
report = h.run(
    case=case,
    props=judges,
    mrs=mutants,
    n=100,
    seed=42,
)

print(f"Adopt: {report['decision']['adopt']}")
print(f"Pass rate: {report['candidate']['pass_rate']}")
```

### 3. Direct Evaluation with run_eval

```python
from metamorphic_guard.harness import run_eval

# Configure OpenAI executor
executor_config = {
    "api_key": "sk-...",  # Or set OPENAI_API_KEY env var
    "model": "gpt-3.5-turbo",
    "max_tokens": 512,
    "temperature": 0.0,
    "seed": 42,
}

# Run evaluation
result = run_eval(
    task_name="llm_chat",
    baseline_path="system_prompt_baseline.txt",
    candidate_path="system_prompt_candidate.txt",
    executor="openai",
    executor_config=executor_config,
    n=100,
    monitors=["llm_cost"],  # Track token usage and costs
)
```

### 3. Using Mutants

```python
from metamorphic_guard.mutants.builtin import ParaphraseMutant, NegationFlipMutant

# Mutants can be used as metamorphic relations
# They transform inputs to test robustness
mutant = ParaphraseMutant()
transformed = mutant.transform("Summarize this document", rng=random.Random(42))
```

### 4. Using Judges

```python
from metamorphic_guard.judges.builtin import LengthJudge, NoPIIJudge

# Judges evaluate LLM outputs
judge = LengthJudge(max_chars=300)
result = judge.evaluate(
    output="This is a long response...",
    input_data="Summarize this",
)
# Returns: {"pass": bool, "score": float, "reason": str, "details": dict}
```

## Plugin System

### Executors

Executors handle LLM API calls. Built-in:
- `openai`: OpenAI API (requires `openai` package)

To create a custom executor:

```python
from metamorphic_guard.executors import LLMExecutor

class CustomExecutor(LLMExecutor):
    PLUGIN_METADATA = {
        "name": "Custom LLM Executor",
        "description": "My custom executor",
    }
    
    def _call_llm(self, prompt: str, **kwargs):
        # Your implementation
        pass
```

Register in `pyproject.toml`:
```toml
[project.entry-points."metamorphic_guard.executors"]
custom = "my_package.executors:CustomExecutor"
```

### Mutants

Mutants transform prompts to test robustness. Built-in:
- `paraphrase`: Paraphrase prompts
- `negation_flip`: Flip negation
- `role_swap`: Swap system/user roles

### Judges

Judges evaluate LLM outputs. Built-in:
- `length`: Check output length constraints
- `no_pii`: Detect PII in outputs

## Integration with Existing Framework

The LLM features integrate seamlessly with Metamorphic Guard's existing infrastructure:

- **Executors** work with the sandbox system
- **Mutants** can be used as metamorphic relations
- **Judges** can be used as property checks
- **Monitors** track LLM-specific metrics (tokens, cost, latency)
  - Use `llm_cost` monitor to track token usage and costs
  - Alerts on cost regressions (default: 1.5x threshold)
- **Distributed execution** via queue dispatcher handles rate limits
- **Statistical analysis** with bootstrap confidence intervals
- **Adoption gating** with data-driven decisions

## Advanced Features

### Anthropic Executor

```python
h = LLMHarness(
    model="claude-3-5-sonnet-20241022",
    provider="anthropic",
    executor_config={"api_key": "sk-ant-..."},  # Or set ANTHROPIC_API_KEY
)
```

### Advanced Mutants

```python
from metamorphic_guard.mutants.advanced import (
    JailbreakProbeMutant,
    ChainOfThoughtToggleMutant,
    InstructionPermutationMutant,
)

mutants = [
    JailbreakProbeMutant(intensity=0.3),  # Test safety boundaries
    ChainOfThoughtToggleMutant(),  # Toggle reasoning instructions
    InstructionPermutationMutant(),  # Reorder instructions
]
```

### Structured Judges

```python
from metamorphic_guard.judges.structured import RubricJudge, CitationJudge

rubric = {
    "criteria": [
        {"name": "completeness", "weight": 0.3},
        {"name": "accuracy", "weight": 0.4},
        {"name": "clarity", "weight": 0.3},
    ],
    "threshold": 0.7,
}

judges = [
    RubricJudge(rubric=rubric),
    CitationJudge(require_citations=True, min_citations=2),
]
```

## Next Steps

- Local vLLM executor support
- pytest-metamorph plugin
- More sophisticated rubric evaluation (LLM-as-judge)
- RAG-specific guards

