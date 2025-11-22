# Quick Start Templates

Copy-paste these templates to get up and running quickly.

## 1. CLI Evaluation (Simple)
Run a basic comparison between two Python scripts.

```bash
# run_eval.sh
metaguard eval \
  --task "text-summarization" \
  --baseline ./src/baseline.py \
  --candidate ./src/candidate.py \
  --policy ./policies/policy-fast.toml \
  --output-dir ./reports/
```

**requirements:**
- `baseline.py` and `candidate.py` must implement a `run(input)` function.

---

## 2. Python API (Advanced)
Integrate into your existing test suite.

```python
import pytest
from metamorphic_guard.harness import run_eval

def test_model_improvement():
    result = run_eval(
        task_name="ranking_v2",
        baseline_path="src/ranker_v1.py",
        candidate_path="src/ranker_v2.py",
        n=400,
        policy_override={
            "gate": {
                "method": "bootstrap",
                "threshold": 0.0
            }
        }
    )
    
    assert result["decision"]["adopt"], f"Model rejected: {result['decision']['reason']}"
    print(f"Success! Improvement: {result['delta_pass_rate']:.2%}")
```

---

## 3. Github Actions (CI Integration)
Add this to `.github/workflows/metaguard.yml`.

```yaml
name: Metamorphic Guard Gate

on: [pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"
          
      - name: Install Dependencies
        run: pip install metamorphic-guard
        
      - name: Run Evaluation
        run: |
          metaguard eval \
            --baseline src/baseline.py \
            --candidate src/candidate.py \
            --policy policies/policy-safe.toml \
            --fail-on-rejection
            
      - name: Archive Report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: metaguard-report
          path: reports/
```


