# Changelog

## [3.3.0] - 2025-01-16

### CI/CD Improvements
- Fixed security scan workflow to avoid disk space issues
- Updated security scanning to use `pip-audit --requirement` instead of installing packages
- Scans dependencies in separate groups (base, queue, otel, llm) for better efficiency
- Added note about vLLM exclusion in CI due to large PyTorch/CUDA dependencies
- Updated GitHub Actions artifact upload actions from v3 to v4 (deprecation fix)

### Notes
- No breaking API changes. Safe minor update.
- CI/CD improvements ensure reliable automated security scanning

## [3.2.0] - 2025-01-16

### Production Readiness Enhancements

#### Security
- Added Dependabot configuration for automated dependency updates
- Added security scanning CI job with `pip-audit` for vulnerability detection
- Updated SECURITY.md with comprehensive vulnerability response process
- Automated security scanning for both base and optional dependencies

#### Queue Dispatcher Stabilization
- Removed "experimental" labels from queue dispatcher in README
- Added comprehensive queue backend tests (SQS, RabbitMQ, Kafka)
- Created queue dispatcher production readiness audit document
- Updated queue dispatch documentation with production guidance

#### Operational Documentation
- Added comprehensive operational runbook (`docs/operations/runbook.md`)
- Added production deployment guide with Kubernetes configurations
- Added Prometheus alerting rules (`docs/grafana/alerting-rules.yml`)
- Enhanced Prometheus documentation with alerting setup instructions

#### Cost Estimation
- Fixed budget action logic (ALLOW action now properly handles exceeded budgets)
- Enhanced cost estimation API with better error handling
- Added comprehensive edge case tests for cost estimation

#### Testing
- Added queue backend test suite (skipped when optional dependencies unavailable)
- Added cost estimation edge case tests
- All tests passing (472 passed, 15 skipped)

### Documentation
- Updated API reference with cost estimation functions
- Enhanced LLM evaluation guide with cost estimation examples
- Removed roadmap and development phase planning documents from release

### Notes
- No breaking API changes. Safe minor update.
- Production-ready with comprehensive operational guides and monitoring

## [3.1.2] - 2025-11-16

### CI/CD Fixes
- Fixed duplicate workflow definitions in `test.yml` and `docs.yml` that caused workflow validation failures.
- Removed duplicate `name`, `on`, `permissions`, and `jobs` sections that blocked CI runs.

## [3.1.1] - 2025-11-16

### Build/Packaging
- Fix editable install on CI by constraining package discovery to `metamorphic_guard*` and `pytest_metamorphic*`.
- Switch `project.license` to SPDX string (`MIT`) and configure `license-files` to address setuptools deprecations.

## [3.1.0] - 2025-11-16

### Enhancements
- Added replay command to reports for easy reproduction (`report.replay.cli`).
- Introduced bounded benchmark test to guard performance budgets in CI.
- Added observability documentation with Prometheus scrape example.
- Added SECURITY.md and `templates/docker-executor.toml` with hardened defaults.
- Updated GitHub Actions docs to be test-gated; added docs deploy workflow (MkDocs → GH Pages).

### CI/CD
- Gated publishing on tests and mypy; unified versioning to static `pyproject.toml`.
- Added entry point resolution test to catch broken plugins/scripts before release.

### Notes
- No breaking API changes. Safe minor update.

## [3.0.1] - 2025-01-15

### Bug Fixes
- Fixed test failures in LLM harness integration tests by properly mocking `openai` module and `OpenAIExecutor.__init__`
- Fixed `test_queue_requeues_stalled_worker` by correcting monkeypatch target to patch where function is actually used
- All tests now properly handle executor instantiation in `run_in_sandbox` with mocked dependencies

### Maintenance
- Removed temporary markdown files (completion summaries, old roadmaps) from repository

## [3.0.0] - 2025-01-13

### Major Release: Complete Product with All Roadmap Features

This is a major release completing all planned roadmap phases and recommendations. Metamorphic Guard is now a complete, production-ready product.

#### Core Features
- ✅ Complete type safety migration (>90% type coverage, zero `Any` in public API)
- ✅ Comprehensive test coverage (>80% for LLM modules, 384 tests passing)
- ✅ Full documentation (>90% coverage, API reference, guides, case studies)

#### Advanced Features
- ✅ Adaptive testing (smart sampling, MR prioritization, early stopping, budget-aware execution)
- ✅ Multi-objective optimization (Pareto frontiers, trade-off analysis, recommendation engine)
- ✅ Trust & Safety (trust scoring, safety monitors, compliance checks, enhanced audit trails)

#### Scalability
- ✅ Support for 100k+ test cases (chunked input generation, incremental processing, progress tracking)
- ✅ Distributed execution (Redis, SQS, RabbitMQ, Kafka backends)
- ✅ Auto-scaling worker pools and load balancing
- ✅ Memory optimization utilities

#### Enterprise Features
- ✅ SSO support (OAuth2, SAML, OIDC)
- ✅ Role-based access control (RBAC)
- ✅ Enhanced audit logging with user tracking
- ✅ Risk monitoring system

#### Developer Experience
- ✅ Model comparison API (native support for comparing multiple models)
- ✅ Cost estimation and budget controls
- ✅ Performance profiling and monitoring
- ✅ VS Code extension enhancements
- ✅ Debugging and profiling tools
- ✅ Plugin marketplace structure

#### New Modules
- `metamorphic_guard/model_comparison.py` - Native model comparison
- `metamorphic_guard/scalability.py` - 100k+ test case support
- `metamorphic_guard/enterprise/` - SSO, RBAC, audit logging
- `metamorphic_guard/risk_monitoring.py` - Risk assessment and monitoring
- `metamorphic_guard/adaptive_sampling.py` - Adaptive testing
- `metamorphic_guard/multi_objective.py` - Multi-objective optimization
- `metamorphic_guard/trust_scoring.py` - Trust scoring for RAG
- `metamorphic_guard/safety_monitors.py` - Safety monitoring suite
- `metamorphic_guard/compliance.py` - Compliance validation

#### Documentation
- ✅ Comprehensive API reference
- ✅ Advanced patterns cookbook
- ✅ Case studies
- ✅ Academic validation methodology
- ✅ Scalability guide
- ✅ Risk assessment documentation

#### Breaking Changes
- None - all changes are backward compatible

#### Migration Guide
- No migration required - this release is fully backward compatible

## [2.2.0] - 2025-11-13
- Renamed the CLI/API gating option from `improve_delta` to `min_delta` with backwards-compatible warnings.
- Fixed LLMHarness executor routing and added regression coverage to prevent model mix-ups.
- Added configurable OpenAI/Anthropic pricing overrides and built-in retry/backoff logic with Prometheus counters.
- Aggregated LLM metrics (cost, tokens, latency, retries) in JSON & HTML reports.
- Enhanced documentation and tests for the new LLM telemetry and executor configuration options.

## [1.0.1] - 2025-11-02
- Initial public release
- Added ranking guard and demo projects
- Published to PyPI and automated CI/CD

## [1.0.0] - 2025-10-23
- Internal sandbox and testing framework foundation
