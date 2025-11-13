# Changelog

# Changelog

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
