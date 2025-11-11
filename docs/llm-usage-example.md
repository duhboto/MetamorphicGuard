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

### 2. Basic LLM Evaluation

```python
from metamorphic_guard.harness import run_eval
from metamorphic_guard.executors.openai import OpenAIExecutor

# Configure OpenAI executor
executor_config = {
    "api_key": "sk-...",  # Or set OPENAI_API_KEY env var
    "model": "gpt-3.5-turbo",
    "max_tokens": 512,
    "temperature": 0.0,  # Deterministic
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
- **Distributed execution** via queue dispatcher handles rate limits

## Next Steps

- Add Anthropic executor
- Implement more sophisticated mutants (jailbreak probes, chain-of-thought)
- Add structured judges (rubric JSON, citation checks)
- Create LLMHarness wrapper for easier API
- Add pytest-metamorph plugin

