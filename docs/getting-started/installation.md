# Installation

## Standard Installation

Install Metamorphic Guard from PyPI:

```bash
pip install metamorphic-guard
```

This installs the core package with only essential dependencies (`click`, `pydantic`).

## Development Installation

For development, clone the repository and install in editable mode:

```bash
git clone https://github.com/duhboto/MetamorphicGuard.git
cd MetamorphicGuard
pip install -e ".[dev]"
```

This installs development dependencies including `pytest`, `mypy`, `hypothesis`, and test coverage tools.

## Install Profiles

Metamorphic Guard provides several optional dependency groups for different use cases:

### LLM Support (`llm`)

For LLM evaluation features with OpenAI, Anthropic, or local vLLM:

```bash
pip install metamorphic-guard[llm]
```

**Includes:**
- `openai>=1.0.0` - OpenAI API support
- `anthropic>=0.18.0` - Anthropic API support
- `vllm>=0.2.0` - Local vLLM inference

### Queue Backends (`queue`)

For distributed evaluation using queue-based task distribution:

```bash
pip install metamorphic-guard[queue]
```

**Includes:**
- `redis>=5.0.0` - Redis queue backend
- `boto3>=1.28.0` - AWS SQS queue backend
- `pika>=1.3.0` - RabbitMQ queue backend
- `kafka-python>=2.0.0` - Kafka queue backend

### OpenTelemetry (`otel`)

For distributed tracing and observability:

```bash
pip install metamorphic-guard[otel]
```

**Includes:**
- `opentelemetry-api>=1.20.0`
- `opentelemetry-sdk>=1.20.0`
- `opentelemetry-exporter-otlp-proto-grpc>=1.20.0`

### Documentation (`docs`)

For building documentation locally:

```bash
pip install metamorphic-guard[docs]
```

**Includes:**
- `mkdocs>=1.5.0`
- `mkdocs-material>=9.0.0`
- `mkdocstrings[python]>=0.24.0`
- `pymdown-extensions>=10.0.0`

### All Optional Dependencies (`all`)

Install all optional dependencies at once:

```bash
pip install metamorphic-guard[all]
```

This is equivalent to `pip install metamorphic-guard[llm,otel,queue,docs]`.

### Combining Profiles

You can combine multiple profiles:

```bash
# LLM + Queue backends
pip install metamorphic-guard[llm,queue]

# LLM + OpenTelemetry
pip install metamorphic-guard[llm,otel]

# Development with LLM support
pip install -e ".[dev,llm]"
```

## Using Lock Files (Reproducible Installs)

For reproducible installations, use the provided requirements lock files:

```bash
# Base installation
pip install -r requirements-base.txt

# With LLM support
pip install -r requirements-llm.txt

# With queue backends
pip install -r requirements-queue.txt

# All optional dependencies
pip install -r requirements-all.txt

# Development
pip install -r requirements-dev.txt
```

Lock files are generated using `pip-compile` and include all transitive dependencies with pinned versions.

## One-off Usage (pipx)

For one-time evaluations without installing:

```bash
pipx run metamorphic-guard evaluate \
  --task demo \
  --baseline baseline.py \
  --candidate candidate.py
```

## Verification

Verify your installation:

```bash
metamorphic-guard --version
```

You should see the version number printed.

