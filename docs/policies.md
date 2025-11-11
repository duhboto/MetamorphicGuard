# Policy Files

Metamorphic Guard supports **policy-as-code** so guard rails are versioned alongside application changes. Policies describe thresholds (minimum delta, pass-rate floor, significance level, etc.) and live under `policies/`. Load them via:

```bash
metamorphic-guard evaluate \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --policy policies/policy-v1.toml
```

## File Format

Policies can be authored in **TOML** or **YAML** (the loader autodetects based on file suffix). Each policy contains metadata plus a `gating` section:

```toml
name = "policy-v1"
description = "Baseline guardrail policy ensuring minimum lift and pass rate."

[gating]
min_delta = 0.02
min_pass_rate = 0.80
alpha = 0.05
power_target = 0.8
violation_cap = 25
```

Supported gating keys:

| Key | Description |
| --- | --- |
| `min_delta` | Minimum Δ pass-rate lower bound required to adopt |
| `min_pass_rate` | Minimum candidate pass-rate |
| `alpha` | Confidence interval significance level |
| `power_target` | Target power used to recommend a sample size |
| `violation_cap` | Maximum number of recorded violations |

Unknown keys are preserved in the `policy.raw` payload so teams can extend the schema. When the optional [`jsonschema`](https://pypi.org/project/jsonschema/) package is installed, policies are validated against `policies/policy.schema.json` at load time.

## Bundled Policies

- `policies/policy-v1.toml` – baseline guard rails for most releases.
- `policies/policy-strict.toml` – stricter thresholds for high-risk deployments.

Copy and adapt these files for your org. Embed the policy version in your config (`policy_version = "policy-2025"`) so runs and reports carry clear provenance.

