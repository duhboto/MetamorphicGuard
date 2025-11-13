# Installation

## Standard Installation

Install Metamorphic Guard from PyPI:

```bash
pip install metamorphic-guard
```

## Development Installation

For development, clone the repository and install in editable mode:

```bash
git clone https://github.com/duhboto/MetamorphicGuard.git
cd MetamorphicGuard
pip install -e .
```

## Optional Dependencies

### LLM Support

For LLM evaluation features:

```bash
pip install metamorphic-guard[llm]
```

This installs:
- `openai>=1.0.0` - OpenAI API support
- `anthropic>=0.18.0` - Anthropic API support
- `vllm>=0.2.0` - Local vLLM inference

### OpenTelemetry

For distributed tracing:

```bash
pip install metamorphic-guard[otel]
```

### All Optional Dependencies

```bash
pip install metamorphic-guard[llm,otel]
```

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

