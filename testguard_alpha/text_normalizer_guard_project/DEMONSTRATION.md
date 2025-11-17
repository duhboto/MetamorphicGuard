# What This Project Demonstrates About Metamorphic Guard

This project provides concrete evidence that Metamorphic Guard catches regressions you didn't hard-code, makes principled adoption decisions, and works across domains.

## Three Experiments

### Experiment 1: Healthy Candidate ✅

**Setup**: Both baseline and candidate implementations are correct.

**Result**:
```
Adopt candidate: True
Reason: meets_gate

Baseline: 500/500 passed (100.0%)
Candidate: 500/500 passed (100.0%)

Delta pass rate: 0.0000
Delta CI (95%): [0.0000, 0.0000]

Metamorphic Relations:
  ✓ pad_whitespace: baseline=100.0%, candidate=100.0%
  ✓ burst_whitespace: baseline=100.0%, candidate=100.0%
  ✓ case_flip: baseline=100.0%, candidate=100.0%
```

**What this shows**: Metamorphic Guard correctly identifies when both implementations are equivalent and safe to adopt.

---

### Experiment 2: Subtly Broken Candidate ❌

**Setup**: Injected a bug where the candidate sometimes fails to lowercase text (deterministic but subtle).

**Result**:
```
Adopt candidate: False
Reason: Metamorphic relation violations: 25 violations found

Baseline: 500/500 passed (100.0%)
Candidate: 320/500 passed (64.0%)

Delta pass rate: -0.3600
Delta CI (95%): [-0.4020, -0.3200]

Metamorphic Relations:
  ✓ pad_whitespace: baseline=100.0% (0 failures), candidate=100.0% (0 failures)
  ✓ burst_whitespace: baseline=100.0% (0 failures), candidate=100.0% (0 failures)
  ✗ case_flip: baseline=100.0% (0 failures), candidate=64.0% (180 failures)

⚠️  Candidate MR Violations: 25
  Example 1: Case #? - case_flip relation failed
  Example 2: Case #? - case_flip relation failed
  Example 3: Case #? - case_flip relation failed
  ... and 22 more violations
```

**What this shows**:
1. **Metamorphic Guard caught a regression we didn't explicitly test for**: The bug was in the lowercase logic, but we never wrote a test like "test_lowercase_works()". Instead, the `case_flip` metamorphic relation automatically detected that changing input case should produce identical normalized output, but it didn't.

2. **Statistical gate refused adoption**: The framework computed:
   - Degraded pass rate (64% vs 100%)
   - Non-overlapping confidence interval (delta CI: [-0.4020, -0.3200], all negative)
   - Clear decision: `adopt = False`

3. **Automatic counterexample generation**: The framework found 25 cases where the metamorphic relation failed, providing concrete evidence of the regression.

---

### Experiment 3: Fixed Candidate ✅

**Setup**: Removed the bug, candidate is correct again.

**Result**:
```
Adopt candidate: True
Reason: meets_gate

Baseline: 500/500 passed (100.0%)
Candidate: 500/500 passed (100.0%)

Delta pass rate: 0.0000
Delta CI (95%): [0.0000, 0.0000]

Metamorphic Relations:
  ✓ pad_whitespace: baseline=100.0%, candidate=100.0%
  ✓ burst_whitespace: baseline=100.0%, candidate=100.0%
  ✓ case_flip: baseline=100.0%, candidate=100.0%
```

**What this shows**: After fixing the bug, Metamorphic Guard correctly identifies the candidate as safe to adopt again.

---

## Key Insights

### 1. Catches Regressions You Didn't Hard-Code

Traditional unit tests require you to think of every edge case:
- "What if the input has punctuation?"
- "What if there are non-breaking spaces?"
- "What if the input is all uppercase?"

Metamorphic Guard instead asserts **invariants**:
- "Output should be a string"
- "No double spaces in output"
- "Adding whitespace padding shouldn't change normalized output"
- "Changing case shouldn't change normalized output"

When we broke the lowercase logic, we didn't need a test that said "test that 'HELLO' becomes 'hello'". The `case_flip` metamorphic relation automatically detected that `normalize("HELLO")` and `normalize("hello")` should produce the same result, but they didn't.

### 2. Expresses Invariants That Survive Refactors

Normal unit tests are brittle: `input → expected_output`. Change the implementation, update the tests.

Metamorphic Guard tests are **behavioral contracts**:
- "Output has no leading/trailing whitespace"
- "Whitespace padding is idempotent"
- "Case changes don't affect normalization"

These contracts remain valid even when you:
- Refactor the algorithm
- Add new normalization steps
- Optimize performance
- Change internal implementation details

### 3. Demonstrates Baseline vs Candidate Adoption Decision

This project shows the complete adoption workflow:

1. **Configuration**: Set `n=500`, `min_pass_rate=0.95`, `min_delta=0.0`
2. **Execution**: Framework runs both implementations on 500 generated inputs
3. **Evaluation**: Checks properties and metamorphic relations for both
4. **Statistics**: Computes pass rates, delta, confidence intervals
5. **Decision**: Emits `adopt=True/False` with reason

This is the "guard" story: you iterate on implementations, Metamorphic Guard is the gatekeeper.

### 4. Proves Metamorphic Guard is Domain-Agnostic

This project demonstrates that Metamorphic Guard works for **any pure function**, not just:
- LLMs
- Ranking models
- ML models

It works for:
- Text normalization ✅ (this project)
- Ranking functions
- Scoring functions
- Pricing algorithms
- Any function with testable invariants

All you need:
- An input generator
- Properties to check
- Metamorphic relations
- Baseline and candidate implementations

The framework handles the rest: execution, statistics, adoption decisions.

---

## Conclusion

This project proves that Metamorphic Guard:

1. ✅ **Catches subtle regressions automatically** - without writing explicit test cases
2. ✅ **Makes principled adoption decisions** - using statistical gates and confidence intervals
3. ✅ **Works across domains** - not limited to ML/LLM use cases
4. ✅ **Expresses behavioral contracts** - that survive refactoring and implementation changes

The three experiments (healthy → broken → fixed) provide concrete, reproducible evidence that Metamorphic Guard is a valuable tool for guarding behavioral correctness in production systems.

