# Pre-Release Review: Weak Points & Fixes

## Critical Issues Found

### 1. API Key Exposure Risk ⚠️ HIGH
**Issue**: Error messages from LLM executors may contain API keys if SDK includes them in exceptions.
**Location**: `metamorphic_guard/executors/openai.py`, `metamorphic_guard/executors/anthropic.py`
**Fix**: Apply redaction to error messages before returning them.

### 2. Missing Input Validation ⚠️ MEDIUM
**Issue**: No validation for:
- Empty prompts
- Invalid model names
- Temperature out of range (0-2 for OpenAI, 0-1 for Anthropic)
- Max tokens out of range
**Location**: LLM executors, LLMHarness
**Fix**: Add validation with clear error messages.

### 3. LLMHarness Design Issue ⚠️ MEDIUM (PARTIALLY FIXED)
**Issue**: Baseline and candidate model comparison requires separate executor configs.
**Location**: `metamorphic_guard/llm_harness.py`
**Status**: Added `baseline_model` and `baseline_system` parameters. Note: Full model comparison requires using `run_eval` directly with different executor_configs, as the harness uses a single config.
**Fix Applied**: Added parameters for baseline overrides, documented limitation.

### 4. Stale Pricing Data ⚠️ LOW
**Issue**: Hardcoded pricing may be outdated.
**Location**: Both executors
**Fix**: Document as approximate, add warning in docstrings.

### 5. Generic Exception Handling ⚠️ MEDIUM
**Issue**: Catching all exceptions hides specific API errors (rate limits, auth failures).
**Location**: LLM executors
**Fix**: Handle specific exception types with appropriate error codes.

### 6. Race Condition in Task Registry ⚠️ LOW
**Issue**: Task registry cleanup in LLMHarness could conflict with concurrent runs.
**Location**: `metamorphic_guard/llm_harness.py`
**Fix**: Use unique task names or lock registry access.

### 7. Missing Error Handling for API Failures ⚠️ MEDIUM
**Issue**: No handling for:
- Rate limit errors (429)
- Authentication errors (401)
- Invalid model errors (400)
- Network timeouts
**Location**: LLM executors
**Fix**: Add specific error handling with retry logic for transient errors.

### 8. No Cost Warnings ⚠️ LOW
**Issue**: No warnings about potential API costs before running evaluations.
**Fix**: Add cost estimation and warning in CLI/docs.

### 9. Missing Tests ⚠️ HIGH
**Issue**: No unit tests for:
- LLM executors
- LLM mutants
- LLM judges
- LLMHarness
**Fix**: Add comprehensive test suite.

### 10. Documentation Gaps ⚠️ LOW
**Issue**: Missing:
- API cost warnings
- Rate limit handling
- Error code reference
- Model compatibility matrix
**Fix**: Add to documentation.

## Recommended Fixes Before Release

### Priority 1 (Must Fix) - ✅ COMPLETED
1. ✅ Add API key redaction to error messages
2. ✅ Add input validation for prompts, models, parameters
3. ✅ Fix LLMHarness to support different baseline/candidate models (partial - added parameters)
4. ✅ Add specific error handling for API exceptions

### Priority 2 (Should Fix)
5. ✅ Add cost estimation and warnings
6. ✅ Improve error codes for different failure types
7. ✅ Add basic unit tests for LLM components

### Priority 3 (Nice to Have)
8. Document pricing as approximate
9. Add retry logic for transient errors
10. Add model compatibility documentation

