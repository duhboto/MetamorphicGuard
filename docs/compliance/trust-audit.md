# Trust Scoring Audit Guide

This guide explains how to assess trust-related dimensions such as citation correctness, hallucination risk, and rubric-based quality using judges and monitors.

## Objectives
- Quantify trust signals (citations, rubric adherence, self-consistency)
- Detect regressions in factuality and attribution
- Provide reproducible evidence for reviewers

## Components
- Judges: `CitationJudge`, `RubricJudge`, `LLMAsJudge`
- Monitors: `trust_score` (if enabled), `llm_cost`, `latency`

## Example: Rubric and Citation Evaluation

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --monitor llm_cost \
  --n 200 \
  --html-report reports/trust_audit.html
```

For LLM tasks, include judges and rubric in your task/spec implementation or config.

## Evidence to Capture
- HTML report with judge summaries
- JSON report including judge outputs and pass/fail signals
- Example cases with rubric scores and citation checks

## Pass/Fail Criteria
- No degradation in rubric-based final score
- No increase in citation correctness failures
- Consistent or improved self-consistency across runs

## PR Template Snippet

```
### Trust Audit Summary
- Rubric final score (baseline → candidate): 0.78 → 0.82  (Δ +0.04)
- Citation correctness failures: 2 → 1 (Δ -1)
- Decision: ✅ Adopt
- Report: reports/trust_audit.html
```

## CI Integration (GitHub Actions)

```yaml
- name: Trust audit
  run: |
    metamorphic-guard evaluate \
      --config metamorphic.toml \
      --n 200 \
      --html-report reports/trust_audit.html
- name: Upload trust audit
  uses: actions/upload-artifact@v4
  with:
    name: trust-audit
    path: reports/trust_audit.html
```

## Reviewer Checklist
- [ ] Rubric/judge outputs included in report
- [ ] No increase in hallucination or citation failures
- [ ] Decision aligns with policy thresholds
- [ ] Follow-ups filed for any regressions

