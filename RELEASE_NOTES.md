# Release Notes v3.6.0

Metamorphic Guard v3.6.0 is a major feature release introducing comprehensive support for LLM and RAG evaluation, distributed execution, and enhanced governance.

## Key Highlights

### 🤖 LLM & RAG Evaluation
- **LLM-as-a-Judge**: Extensible judge framework using LLMs (GPT-4, etc.) to evaluate outputs against rubrics.
- **RAG Guards**: Specialized metamorphic relations for Retrieval-Augmented Generation:
  - `add_irrelevant_context`: Tests robustness to noise.
  - `remove_relevant_context`: Tests faithfulness and hallucination.
  - `shuffle_context`: Tests position invariance ("lost in the middle").
- **Cost Tracking**: Integrated token usage and cost monitoring for LLM providers.

### 🚀 Distributed & Robust Execution
- **Kubernetes & Ray Support**: Native executors for running evaluations as K8s Jobs or on Ray clusters.
- **Docker Hardening**: Enhanced sandbox with resource caps (`ulimits`), image digest pinning, and secure secret handling.
- **Adaptive Engine**: Statistical engine that dynamically adjusts sample sizes based on interim power analysis, with early stopping support.

### 📊 Developer Experience & Governance
- **HTML Dashboards**: Rich visualization of pass rates, fairness gaps, and performance profiles.
- **Report Catalog**: New `mg catalog` command to index and browse evaluation history.
- **CI/CD Blueprints**: Ready-to-use GitHub Actions and GitLab CI templates for automated gate checks.
- **Structured Logging**: OTLP-compatible telemetry and structured JSON logs for full decision provenance.

### 🛠️ Configuration
- **Policy Schemas**: Versioned, strictly validated policy configuration (v1/v2) with automatic migration.
- **Metric Rate Limiting**: intelligent throttling for high-throughput monitoring.

## Upgrade Guide

Existing users can upgrade via pip:
```bash
pip install --upgrade metamorphic-guard
```

See the new [RAG Evaluation Tutorial](docs/tutorials/rag-evaluation.md) to get started with the new capabilities.

