# Changelog

## [3.6.0] - 2025-11-20

### Major Roadmap Completion: Stability, DX, and Ops

This release marks the completion of the Stability, Developer Experience, and Operations roadmap.

### Added
- **Shadow Mode** (`metamorphic_guard.dispatch.ShadowDispatcher`): Safe production traffic sampling with built-in redaction, error suppression, and sampling rates.
- **Interactive Init Wizard** (`metamorphic-guard init --interactive`): Guided project scaffolding with templates for Generic, Ranking/Fairness, and LLM tasks.
- **New Templates**: Ready-to-use configurations for Ranking/Fairness (`templates/ranking.toml`) and Generic ML (`templates/generic.toml`).
- **Enhanced HTML Reporting**: Reports now include a "Custom Metrics" table and improved charts for fairness, resource usage, and performance.
- **JUnit XML Reporting**: Detailed JUnit reports (`--junit-xml`) with failure messages and properties for better CI/CD integration.
- **TrafficSource Abstraction**: Interface for plugging in custom traffic sources (e.g., Kafka, Logs) for Shadow Mode.

### Changed
- **Refactored Dispatch Architecture**: Resolved circular dependencies by splitting `dispatch` module into `base`, `local`, `queue`, and `shadow` submodules.
- **Performance Optimization**: Vectorized statistical bootstrap resampling using NumPy, significantly improving performance for large datasets.
- **Reproducibility**: `seed` is now consistently passed through the entire execution pipeline (including `ExecutionPlan` and `Dispatcher`), ensuring deterministic runs.
- **Sandbox Safety**: Added explicit tests and verification for sandbox memory limits.

### Notes
- **Stability**: The codebase has been refactored for better modularity and stability.
- **Developer Experience**: Getting started is now much easier with the interactive wizard and templates.
- **Operations**: Production deployments are safer and more observable with Shadow Mode and enhanced reporting.

## [3.5.0] - 2025-11-19

### Added
- **Interactive Demo Launcher** (`metamorphic-guard demo`): New CLI command to interactively browse and launch demo projects and tutorials.
- **LLM Guard Demo** (`llm_demo_project/`): New self-contained tutorial for evaluating AI models (LLM-as-a-Judge) with a built-in mock executor (free, no API keys required) and support for real OpenAI/Anthropic keys.
- **Comprehensive Demo Runner**: Enhanced `comprehensive_demo_project` scripts to run out-of-the-box without requiring package installation (falls back to source).

### Changed
- **CLI**: Added `demo` command to the main CLI group.
- **Docs**: Updated README to feature the new LLM Guard project and improved demo instructions.

### Notes
- No breaking API changes.
- Significant improvements to onboarding and demonstration capabilities.

## [3.3.5] - 2025-01-16

### Added
- **Queue Dispatcher Production Readiness Guide** (`docs/operations/queue-production-readiness.md`): Comprehensive production deployment guide with backend-specific recommendations (Redis/SQS/RabbitMQ/Kafka), deployment patterns, monitoring, operational runbooks, and performance benchmarks
- **Authoring High-Quality Metamorphic Relations Guide** (`docs/concepts/authoring-metamorphic-relations.md`): Complete guide with principles, design patterns, common pitfalls, quality checklists, and domain-specific guidance for creating effective MRs
- **Reliability Benchmarks** (`docs/operations/reliability-benchmarks.md`): Production reliability metrics substantiating claims: 99.9%+ uptime, >99.5% task completion, <0.01% message loss, <30s recovery, 100% data integrity
