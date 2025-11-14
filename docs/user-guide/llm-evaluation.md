# LLM Evaluation

Metamorphic Guard provides comprehensive support for evaluating Large Language Models (LLMs).

## Quick Start

```python
from metamorphic_guard.llm_harness import LLMHarness
from metamorphic_guard.judges.builtin import LengthJudge
from metamorphic_guard.mutants.builtin import ParaphraseMutant

# Initialize harness
h = LLMHarness(
    model="gpt-3.5-turbo",
    provider="openai",
    executor_config={"api_key": "sk-..."}
)

# Define test case
case = {
    "system": "You are a helpful assistant",
    "user": "Summarize AI safety in 100 words"
}

# Define judges and mutants
props = [LengthJudge(max_chars=300)]
mrs = [ParaphraseMutant()]

# Run evaluation
report = h.run(case, props=props, mrs=mrs, n=100)
```

## Executors

### OpenAI

```python
from metamorphic_guard.executors.openai import OpenAIExecutor

executor = OpenAIExecutor(config={
    "api_key": "sk-...",
    "model": "gpt-4",
    "temperature": 0.0,
})
```

### Anthropic

```python
from metamorphic_guard.executors.anthropic import AnthropicExecutor

executor = AnthropicExecutor(config={
    "api_key": "sk-ant-...",
    "model": "claude-3-opus-20240229",
})
```

### vLLM (Local)

```python
from metamorphic_guard.executors.vllm import VLLMExecutor

executor = VLLMExecutor(config={
    "model_path": "meta-llama/Llama-2-7b-chat-hf",
    "tensor_parallel_size": 1,
})
```

## Judges

Judges evaluate LLM outputs:

- **LengthJudge**: Checks output length constraints
- **NoPIIJudge**: Detects personally identifiable information
- **RubricJudge**: Evaluates against structured rubrics
- **CitationJudge**: Checks for citations and attribution
- **LLMAsJudge**: Uses an LLM to evaluate outputs

## Mutants

Mutants transform prompts to test robustness:

- **ParaphraseMutant**: Paraphrases prompts
- **NegationFlipMutant**: Flips negations
- **RoleSwapMutant**: Swaps roles in prompts
- **JailbreakProbeMutant**: Tests jailbreak resistance
- **ChainOfThoughtToggleMutant**: Toggles CoT instructions

## Cost Estimation

Estimate costs before running:

```bash
metamorphic-guard evaluate \
  --task llm_task \
  --baseline baseline.py \
  --candidate candidate.py \
  --executor openai \
  --executor-config '{"model": "gpt-4"}' \
  --estimate-cost
```

## Model Comparison

Compare different models:

```python
h = LLMHarness(
    model="gpt-4",
    provider="openai",
    baseline_model="gpt-3.5-turbo",
    baseline_provider="openai",
)
```

## Bayesian Diagnostics

When `--ci-method bayesian` is selected, additional toggles are available:

```
metamorphic-guard evaluate \
  --ci-method bayesian \
  --bayesian-hierarchical \
  --bayesian-posterior-predictive \
  --bayesian-samples 8000
```

The JSON report exposes a `bayesian` section containing posterior predictive deltas and the probability that the candidate exceeds the baseline.

