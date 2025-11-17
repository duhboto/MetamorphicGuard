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

Estimate costs before running evaluations to avoid unexpected charges.

### CLI Usage

```bash
metamorphic-guard evaluate \
  --task llm_task \
  --baseline baseline.py \
  --candidate candidate.py \
  --executor openai \
  --executor-config '{"model": "gpt-4"}' \
  --estimate-cost \
  --budget-limit 10.0 \
  --budget-warning 5.0 \
  --budget-action abort
```

Options:
- `--estimate-cost`: Show cost estimate before running
- `--budget-limit`: Hard budget limit (aborts if exceeded)
- `--budget-warning`: Warning threshold (warns if exceeded)
- `--budget-action`: Action on warning (`allow`, `warn`, `abort`)

### Programmatic API

```python
from metamorphic_guard import estimate_llm_cost, estimate_and_check_budget, BudgetAction

# Estimate cost for an evaluation
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
)

print(f"Estimated cost: ${estimate['total_cost_usd']:.4f}")
print(f"  Baseline: ${estimate['baseline_cost_usd']:.4f}")
print(f"  Candidate: ${estimate['candidate_cost_usd']:.4f}")

# Estimate and check budget
result = estimate_and_check_budget(
    executor_name="openai",
    executor_config={"api_key": "sk-...", "model": "gpt-4"},
    n=1000,
    budget_limit=10.0,
    warning_threshold=5.0,
    action=BudgetAction.ABORT,
    system_prompt="You are a helpful assistant",
    user_prompts=["Example prompt"],
    max_tokens=512,
)

if result["budget_check"]["action_taken"] == "abort":
    print("Budget exceeded! Aborting...")
    raise BudgetExceededError(...)
```

### Cost Estimation with Judges

If you use LLM-as-judge, include judge costs:

```python
from metamorphic_guard.judges.llm_as_judge import LLMAsJudge

judges = [LLMAsJudge(model="gpt-3.5-turbo", executor_config={"api_key": "sk-..."})]

estimate = estimate_llm_cost(
    executor_name="openai",
    executor_config={"api_key": "sk-...", "model": "gpt-4"},
    n=1000,
    judges=judges,  # Include judge costs
    user_prompts=["Example prompt"],
    max_tokens=512,
)

print(f"Judge cost: ${estimate['judge_cost_usd']:.4f}")
```

### Custom Pricing

Override default pricing:

```python
executor_config = {
    "api_key": "sk-...",
    "model": "gpt-4",
    "pricing": {
        "gpt-4": {
            "prompt": 0.03,  # $0.03 per 1K prompt tokens
            "completion": 0.06,  # $0.06 per 1K completion tokens
        }
    }
}

estimate = estimate_llm_cost(
    executor_name="openai",
    executor_config=executor_config,
    n=1000,
    user_prompts=["Example prompt"],
    max_tokens=512,
)
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

