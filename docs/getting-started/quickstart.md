# Quick Start

This guide will walk you through your first Metamorphic Guard evaluation.

## Step 1: Create Baseline and Candidate Implementations

Create two Python files:

**baseline.py:**
```python
def solve(L, k):
    return sorted(L)[:min(len(L), k)]
```

**candidate.py:**
```python
def solve(L, k):
    return sorted(L, reverse=True)[-min(len(L), k):][::-1]
```

Both implementations solve the "top-k" problem, but use different algorithms.

## Step 2: Run Evaluation

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --n 400
```

## Step 3: Review Results

The command will output a summary:

```
Candidate     candidate.py
Adopt?        ✅ Yes
Reason        meets_gate
Δ Pass Rate   0.0125
Δ 95% CI      [0.0040, 0.0210]
```

A detailed JSON report is saved to `reports/` directory.

## Next Steps

- Learn about [Task Specifications](concepts/task-specifications.md)
- Explore [LLM Evaluation](user-guide/llm-evaluation.md)
- Check out [Examples](examples/basic.md)

