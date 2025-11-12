# Governance & Auditability

Metamorphic Guard is designed for governance-sensitive use cases where auditability and reproducibility are critical. This document describes features and practices for producing hardened, auditable artifacts.

## Provenance & Traceability

Every evaluation report includes a `provenance` section with:

- **Library Version**: Exact version of Metamorphic Guard used
- **Git SHA**: Commit hash of the codebase (if in a git repository)
- **Git Dirty Status**: Whether uncommitted changes were present
- **Python Version**: Runtime Python version
- **Platform**: Operating system and architecture
- **Hostname**: Machine where evaluation ran
- **MR IDs**: List of metamorphic relation identifiers
- **Spec Fingerprint**: Hash-based fingerprint of task specification
- **Sandbox**: Executor name, resource limits, sanitized call specs, and SHA256 fingerprints of executor configuration
- **Sandbox Executions**: Runtime metadata returned by the sandbox (image digests, seccomp/capability flags, run state)

This enables:
- **Reproducibility**: Replay exact evaluations with same environment
- **Auditability**: Prove which code and configuration were used
- **Compliance**: Meet regulatory requirements for ML model validation

Inspect differences between reports with:

```bash
metamorphic-guard provenance-diff reports/report_old.json reports/report_new.json
metamorphic-guard regression-guard reports/report_main.json reports/report_pr.json \
  --metric-threshold value_mean:delta.difference=0.1 \
  --require-provenance-match
```

## Report Integrity

### JSON Schema Validation

Reports conform to versioned JSON Schemas (`schemas/report.schema.json`):

```bash
# Validate a report
ajv validate -s schemas/report.schema.json -d report.json
```

### Fingerprinting

Reports include fingerprints for:
- **Spec Fingerprint**: Hash of generator, properties, relations, formatters
- **Baseline Hash**: SHA256 of baseline implementation file
- **Candidate Hash**: SHA256 of candidate implementation file
- **Sandbox Call Specs**: SHA256 of the sanitized baseline/candidate call specifications
- **Executor Config**: SHA256 of sanitized executor configuration payload

These enable detection of:
- Specification changes between runs
- Implementation file modifications
- Configuration drift

## Signed Artifacts

### Option 1: GPG Signing

Sign reports with GPG for authenticity:

```bash
# Generate GPG key (if needed)
gpg --gen-key

# Sign report
gpg --armor --detach-sig report.json

# Verify signature
gpg --verify report.json.asc report.json
```

### Option 2: Cryptographic Hashes

Generate and store hashes for integrity verification:

```bash
# Generate SHA256 hash
sha256sum report.json > report.json.sha256

# Verify hash
sha256sum -c report.json.sha256
```

### Option 3: Timestamping

Use RFC 3161 timestamping services for non-repudiation:

```bash
# Example with OpenSSL (requires timestamping service)
openssl ts -query -data report.json -cert | \
  curl -H "Content-Type: application/timestamp-query" \
  --data-binary @- https://freetsa.org/tsr > report.json.tsr
```

## Reproducible Bundles

The `bundle` command creates self-contained, reproducible evaluation packages:

```bash
metamorphic-guard bundle report.json \
  --baseline baseline.py \
  --candidate candidate.py \
  --output evaluation-bundle.tgz
```

Bundles include:
- Evaluation report (JSON)
- Baseline and candidate implementations
- Test case inputs (`_cases.json`)
- Configuration and policy files
- Provenance metadata

**Use Cases**:
- Archive evaluations for compliance
- Share evaluations with auditors
- Reproduce evaluations in different environments

## Policy as Code

Policy files (`.toml`) provide versioned, auditable gate thresholds:

```toml
[gating]
min_delta = 0.05
min_pass_rate = 0.90
alpha = 0.01
power_target = 0.95
```

**Benefits**:
- Policy changes are tracked in version control
- Policy version embedded in reports
- Audit trail of gate threshold changes
- Team-wide consistency

## Stability Audits

Run stability audits to detect flakiness:

```bash
metamorphic-guard stability-audit \
  --task top_k \
  --baseline baseline.py \
  --candidate candidate.py \
  --num-seeds 20 \
  --output audit.json
```

**Governance Value**:
- Detect non-deterministic behavior
- Ensure consistent decisions across runs
- Identify insufficient sample sizes
- Validate statistical robustness

## Best Practices for Governance

### 1. Version Control

- Commit policy files to version control
- Tag releases with policy versions
- Document policy changes in commit messages

### 2. Artifact Storage

- Store reports in immutable storage (S3 versioning, Git LFS)
- Generate checksums for all artifacts
- Maintain retention policies

### 3. Access Control

- Restrict write access to policy files
- Require approvals for policy changes
- Log access to evaluation reports

### 4. Audit Logging

- Log all evaluation runs
- Track policy file changes
- Record who approved policy modifications

### 5. Reproducibility

- Use explicit seeds (`--seed`)
- Save test case inputs (`_cases.json`)
- Document environment (Python version, platform)
- Use reproducible bundles for audits

## Compliance Use Cases

### Model Validation (Financial Services)

- **Requirement**: Prove model improvements before deployment
- **Solution**: Use policy-as-code with strict thresholds, signed reports
- **Evidence**: Reports with provenance, policy version, statistical guarantees

### Fairness Audits (Hiring/Credit)

- **Requirement**: Demonstrate fairness across protected groups
- **Solution**: Fairness MRs with parity checks, group-level reporting
- **Evidence**: Coverage reports showing fairness category pass rates

### Algorithm Certification (Healthcare)

- **Requirement**: Validate algorithm correctness before clinical use
- **Solution**: Comprehensive MR coverage, stability audits, signed artifacts
- **Evidence**: Reproducible bundles with full provenance

## Example Governance Workflow

```bash
# 1. Define policy
cat > policies/strict.toml << EOF
[gating]
min_delta = 0.05
min_pass_rate = 0.95
alpha = 0.01
EOF

# 2. Run evaluation with policy
metamorphic-guard evaluate \
  --task my_task \
  --baseline baseline.py \
  --candidate candidate.py \
  --policy policies/strict.toml \
  --policy-version "strict-v1.0" \
  --stability 5 \
  --html-report report.html \
  --junit-report junit.xml

# 3. Create reproducible bundle
metamorphic-guard bundle report.json \
  --baseline baseline.py \
  --candidate candidate.py \
  --output audit-bundle.tgz

# 4. Sign artifacts
gpg --armor --detach-sig report.json
sha256sum report.json > report.json.sha256

# 5. Store in immutable storage
aws s3 cp report.json s3://audit-bucket/reports/ --storage-class GLACIER
aws s3 cp audit-bundle.tgz s3://audit-bucket/bundles/
```

## See Also

- [Architecture Documentation](architecture.md) - Component interfaces
- [Policy Documentation](policies.md) - Policy-as-code guide
- [MR Library](mr-library.md) - Metamorphic relation catalog

