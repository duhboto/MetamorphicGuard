# Metamorphic Guard Roadmap Status

## Completed Features ✅

### Performance & Pipeline
- [x] **Adaptive batching** - Queue dispatcher adjusts batch sizes based on worker latency
- [x] **Adaptive compression** - Gzip payloads when beneficial (configurable threshold)
- [x] **Queue telemetry** - Prometheus metrics for pending, inflight, requeued tasks
- [x] **Worker heartbeats** - Task leasing with automatic requeue on timeout
- [x] **Sandbox reuse** - Caching and optimization for repeated executions

### Observability
- [x] **Structured JSON logging** - Stream logs with `--log-json` or `METAMORPHIC_GUARD_LOG_JSON=1`
- [x] **File-based logging** - Persist logs with `--log-file`
- [x] **Prometheus metrics** - Counters and gauges for cases, queue state, workers
- [x] **Metrics HTTP endpoint** - Expose metrics on configurable port
- [x] **HTML reports with charts** - Chart.js visualizations for pass rates, fairness, resources
- [x] **Grafana dashboard** - JSON dashboard template available
- [x] **Failed-case artifacts** - Capture violations with retention policies (limit + TTL)

### Developer Experience
- [x] **CLI init wizard** - Interactive `metamorphic-guard init` for project setup
- [x] **Plugin scaffolding** - `metamorphic-guard scaffold-plugin` for monitors/dispatchers
- [x] **Plugin registry CLI** - `plugin list` and `plugin info` commands
- [x] **Cookbook documentation** - Distributed deployment, monitors, security hardening
- [x] **Pydantic config validation** - Type-safe configuration with environment overrides
- [x] **Policy versioning** - Track spec/monitor revisions across runs

### LLM/AI Extensions (NEW)
- [x] **Plugin system extension** - Executors, mutants, judges plugin groups
- [x] **OpenAI executor** - Full API integration with cost tracking
- [x] **Anthropic executor** - Claude model support with cost tracking
- [x] **LLM cost monitor** - Track tokens and costs with regression alerts
- [x] **Prompt mutants** - Paraphrase, negation flip, role swap, jailbreak probe, CoT toggle, instruction permutation
- [x] **Output judges** - Length, PII detection, rubric evaluation, citation checking
- [x] **LLMHarness wrapper** - High-level API for LLM evaluation
- [x] **LLM task specs** - Helper functions for LLM-specific specifications

### Security & Sandboxing
- [x] **Secret redaction** - Automatic redaction of sensitive data in outputs
- [x] **Structured error codes** - Better error reporting from sandbox
- [x] **Sandboxed plugins** - Process isolation for untrusted plugin code
- [x] **Docker executor** - Container-based isolation option

### Monitoring & Alerting
- [x] **Latency monitor** - Track p95 latency with regression alerts
- [x] **Success rate monitor** - Track pass rates over time
- [x] **Trend monitor** - Detect performance trends
- [x] **Fairness gap monitor** - Track disparities across sensitive groups
- [x] **Resource usage monitor** - Track CPU/memory with regression alerts
- [x] **Webhook notifications** - Send alerts to external systems

## In Progress / Planned 🔄

### Performance
- [ ] **Spec fingerprint caching** - Cache spec fingerprints/baseline hashes per run
- [ ] **Vectorized sandbox reruns** - Reuse warm processes for relations when arguments match

### Observability
- [ ] **Enhanced visualization** - More detailed dashboards for LLM-specific metrics
- [ ] **OpenTelemetry integration** - Export traces for distributed debugging

### Developer Experience
- [ ] **CI/CD templates** - Reusable GitHub Actions/GitLab CI workflows
- [ ] **MkDocs documentation site** - Centralized docs with search
- [ ] **Python SDK package** - Typed client library for embedding

### LLM/AI Extensions
- [ ] **Local vLLM executor** - Support for local model inference
- [ ] **pytest-metamorph plugin** - Native pytest integration
- [ ] **LLM-as-judge** - Use LLMs to evaluate outputs (for rubric judge)
- [ ] **RAG-specific guards** - Citation verification, attribution overlap
- [ ] **Agent trace** - Multi-tool agent debugging and replay

### Additional Tools (from original proposal)
- [ ] **mutant-bank** - Curated library of domain-specific metamorphic relations
- [ ] **rag-guards** - RAG-specific evaluation (groundedness, citations)
- [ ] **agent-trace** - Timeline recording and replay for multi-tool agents
- [ ] **policy-router** - Cost/latency/quality-aware model routing
- [ ] **promptgym** - Bayesian prompt tuning with MG integration
- [ ] **runledger** - Git-native experiment tracking
- [ ] **guardrails-plus** - Layered content filters with adversarial probes
- [ ] **telemetry-lite** - OpenTelemetry exporter for LLM apps

## Statistics

- **Total completed features**: ~40+
- **Plugin groups**: 5 (monitors, dispatchers, executors, mutants, judges)
- **Built-in monitors**: 6
- **LLM executors**: 2 (OpenAI, Anthropic)
- **LLM mutants**: 6
- **LLM judges**: 4
- **Documentation**: README, Cookbook, LLM usage guide, Planning docs

## Next Priorities

1. **Complete LLM ecosystem** - Local vLLM, pytest plugin, LLM-as-judge
2. **Performance optimizations** - Spec caching, vectorized reruns
3. **Enhanced observability** - OpenTelemetry, better LLM dashboards
4. **Developer tools** - CI templates, MkDocs site, SDK package

