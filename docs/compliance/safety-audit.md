# Safety Monitor Audit Guide

This guide describes how to run a safety audit using Metamorphic Guard's safety monitors and document the results.

## Objectives
- Validate that candidate changes do not degrade safety (toxicity, PII leakage, jailbreak susceptibility)
- Produce reproducible evidence for reviewers and governance teams

## Monitors

Enable any combination of built-in safety monitors:
- `toxicity` – heuristics or model-based toxicity detection
- `pii` – flags potential PII in outputs
- `jailbreak_probe` – probes jailbreak susceptibility (if enabled)

Example CLI (using built-in demo task):

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline examples/top_k_baseline.py \
  --candidate examples/top_k_improved.py \
  --monitor toxicity \
  --monitor pii \
  --n 200 \
  --report-dir reports \
  --html-report reports/safety_audit.html
```

If using LLM tasks, add `--preset llm` or a config with an executor.

## Recommended Configuration Keys

Add to your TOML `metamorphic.toml`:

```toml
[reporting]
html_report = "reports/safety_audit.html"

[monitors]
# Enable via CLI or config depending on your workflow
# monitors = ["toxicity", "pii"]
```

## Evidence to Capture
- HTML report with monitor summaries
- JSON report for machine-readable evidence
- Any flagged violations with examples (redacted if necessary)

## Example Findings Table (copy into PR description)

| Monitor | Baseline alerts | Candidate alerts | Delta | Notes |
| --- | ---: | ---: | ---: | --- |
| toxicity | 0 | 1 | +1 | One output contained borderline offensive phrasing |
| pii | 0 | 0 | 0 | No PII detected |

## Pass/Fail Criteria
- No increase in high-severity safety alerts
- If alerts occur, must be justified (test-case changes, improved detection), or fixed before merge

## Storing Artifacts
- Store `reports/*.json` and `*.html` as build artifacts
- Link `safety_audit.html` from the PR

## CI Integration Snippet (GitHub Actions)

```yaml
- name: Safety audit
  run: |
    metamorphic-guard evaluate \
      --config metamorphic.toml \
      --monitor toxicity \
      --monitor pii \
      --n 200 \
      --html-report reports/safety_audit.html
- name: Upload safety audit
  uses: actions/upload-artifact@v4
  with:
    name: safety-audit
    path: reports/safety_audit.html
```

## Reviewer Checklist
- [ ] HTML report attached and readable
- [ ] No new high-severity safety alerts
- [ ] Violations discussed with mitigation or follow-up issue
- [ ] Policy gate decision aligns with organizational thresholds

