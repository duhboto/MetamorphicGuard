# LLM Extensions: Known Limitations & Workarounds

## Model Comparison Limitation

**Issue**: When comparing different LLM models (e.g., GPT-3.5 vs GPT-4), the `LLMHarness.run()` method uses a single `executor_config` for both baseline and candidate runs. This means both will use the same model unless you specify `baseline_model`.

**Workaround 1**: Use `baseline_model` parameter:
```python
h = LLMHarness(model="gpt-4", provider="openai", executor_config={...})
result = h.run(
    case={"user": "..."},
    baseline_model="gpt-3.5-turbo",  # Different model for baseline
)
```

**Workaround 2**: Use `run_eval` directly with separate configs:
```python
from metamorphic_guard.harness import run_eval

# Create separate configs
baseline_config = {"model": "gpt-3.5-turbo", "api_key": "..."}
candidate_config = {"model": "gpt-4", "api_key": "..."}

# Run baseline
baseline_result = run_eval(..., executor_config=baseline_config)

# Run candidate  
candidate_result = run_eval(..., executor_config=candidate_config)

# Compare manually
```

## Pricing Data

**Issue**: Pricing data in executors is approximate and may drift as providers update rates.

**Status**: ✅ Supply `pricing` overrides in `executor_config` (per-model `prompt` / `completion` prices). Example:
```toml
[metamorphic_guard.executor_config.pricing."gpt-4"]
prompt = 0.03
completion = 0.06
```
*or via CLI JSON*: `--executor-config '{"pricing":{"gpt-4":{"prompt":0.03,"completion":0.06}}}'`

**Recommendation**: Keep overrides in configuration so audits record the exact tariff used for cost analysis.

## Rate Limiting

**Status**: ✅ Built-in retry logic backs off automatically on retryable errors (429, 5xx). Configure behaviour via `executor_config` keys such as `max_retries`, `retry_backoff_base`, and `retry_jitter`.

**Tip**: Override `retry_statuses` / `retry_exceptions` when targeting custom providers or sandboxes.

## Model-Specific Limits

**Issue**: `max_tokens` validation uses conservative limits (128K for OpenAI, 4K for Anthropic) but actual limits vary by model.

**Status**: Validation prevents obviously invalid values. Model-specific validation would require a model registry.

**Workaround**: Check provider documentation for your specific model's limits.

## Cost Estimation

**Issue**: No cost estimation before running evaluations.

**Status**: Costs are tracked and reported after execution.

**Workaround**: Estimate manually: `n * avg_tokens_per_case * cost_per_token`

## Error Message Redaction

**Status**: ✅ Fixed - API keys are automatically redacted from error messages using the redaction system.

## Input Validation

**Status**: ✅ Fixed - All inputs are validated (prompts, models, temperature, max_tokens).

## API Exception Handling

**Status**: ✅ Fixed - Specific error codes for authentication, rate limits, invalid requests, server errors.

