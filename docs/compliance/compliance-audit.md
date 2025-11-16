# Compliance Audit Guide

This guide outlines how to document compliance checks (e.g., GDPR, HIPAA, financial) within Metamorphic Guard evaluations and produce auditable artifacts.

## Objectives
- Validate outputs against compliance rules
- Capture machine-readable evidence
- Provide human-readable summaries for auditors

## Compliance Rules

Implement or enable rules using the `ComplianceRule` API (see `metamorphic_guard.compliance`). Example rules:
- GDPR: No PII leakage, right-to-be-forgotten support indicators
- HIPAA: No protected health information (PHI)
- Financial: No account numbers or sensitive financial data

## Example CLI

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --monitor llm_cost \
  --n 200 \
  --html-report reports/compliance_audit.html
```

If your task/spec integrates `check_compliance()` in post-processing, results will appear in the report under Monitors.

## Evidence to Capture
- JSON report (compliance findings under `monitors` or result sections)
- HTML report (human-readable summary)
- Violations list with case indices and sanitized snippets

## Pass/Fail Criteria
- Zero high-severity compliance violations
- Documented mitigation for medium severity findings, or block merge

## PR Template Snippet

```
### Compliance Audit Summary
- GDPR violations: 0
- HIPAA violations: 0
- Financial violations: 0
- Decision: ✅ Proceed
- Report: reports/compliance_audit.html
```

## CI Integration (GitHub Actions)

```yaml
- name: Compliance audit
  run: |
    metamorphic-guard evaluate \
      --config metamorphic.toml \
      --n 200 \
      --html-report reports/compliance_audit.html
- name: Upload compliance audit
  uses: actions/upload-artifact@v4
  with:
    name: compliance-audit
    path: reports/compliance_audit.html
```

## Reviewer Checklist
- [ ] Compliance findings included and reviewed
- [ ] No high-severity violations
- [ ] Medium/low findings have mitigation or follow-up tickets
- [ ] Artifacts stored with run metadata for auditability
