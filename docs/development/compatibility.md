# Compatibility Matrix

This document outlines compatibility information for Metamorphic Guard across Python versions, operating systems, and optional dependency combinations.

## Python Version Support

| Python Version | Status | Notes |
|----------------|--------|-------|
| 3.10 | ✅ Supported | Minimum required version |
| 3.11 | ✅ Supported | Recommended version |
| 3.12 | ✅ Supported | Fully tested |
| 3.13 | ⚠️ Experimental | May have compatibility issues with some dependencies |
| < 3.10 | ❌ Not Supported | `requires-python = ">=3.10"` |

## Operating System Support

| OS | Status | Notes |
|----|--------|-------|
| Linux (Ubuntu 20.04+) | ✅ Fully Supported | Primary development platform |
| Linux (Debian 11+) | ✅ Fully Supported | |
| Linux (RHEL/CentOS 8+) | ✅ Fully Supported | |
| macOS 11+ (Intel) | ✅ Fully Supported | |
| macOS 11+ (Apple Silicon) | ✅ Fully Supported | Native ARM64 support |
| Windows 10+ | ✅ Supported | Some queue backends may have limitations |
| Windows Server 2019+ | ✅ Supported | |

## Core Dependencies

The core package requires only:
- `click>=8.1` - CLI framework
- `pydantic>=2.0` - Data validation

These are compatible with Python 3.10+ on all supported platforms.

## Optional Dependency Compatibility

### LLM Profile (`[llm]`)

| Dependency | Python 3.10 | Python 3.11 | Python 3.12 | Notes |
|------------|-------------|-------------|-------------|-------|
| `openai>=1.0.0` | ✅ | ✅ | ✅ | |
| `anthropic>=0.18.0` | ✅ | ✅ | ✅ | |
| `vllm>=0.2.0` | ⚠️ | ✅ | ✅ | vLLM requires Python 3.11+ for full features |

**Platform Notes:**
- vLLM requires CUDA-capable GPU on Linux (not available on macOS/Windows)
- OpenAI and Anthropic work on all platforms

### Queue Profile (`[queue]`)

| Dependency | Python 3.10 | Python 3.11 | Python 3.12 | Linux | macOS | Windows |
|------------|-------------|-------------|-------------|-------|-------|---------|
| `redis>=5.0.0` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `boto3>=1.28.0` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `pika>=1.3.0` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `kafka-python>=2.0.0` | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |

**Platform Notes:**
- Kafka on Windows may require additional setup (native libraries)
- All other queue backends work identically across platforms

### OpenTelemetry Profile (`[otel]`)

| Dependency | Python 3.10 | Python 3.11 | Python 3.12 | Notes |
|------------|-------------|-------------|-------------|-------|
| `opentelemetry-api>=1.20.0` | ✅ | ✅ | ✅ | |
| `opentelemetry-sdk>=1.20.0` | ✅ | ✅ | ✅ | |
| `opentelemetry-exporter-otlp-proto-grpc>=1.20.0` | ✅ | ✅ | ✅ | |

**Platform Notes:**
- Full compatibility across all supported platforms

### Documentation Profile (`[docs]`)

| Dependency | Python 3.10 | Python 3.11 | Python 3.12 | Notes |
|------------|-------------|-------------|-------------|-------|
| `mkdocs>=1.5.0` | ✅ | ✅ | ✅ | |
| `mkdocs-material>=9.0.0` | ✅ | ✅ | ✅ | |
| `mkdocstrings[python]>=0.24.0` | ✅ | ✅ | ✅ | |

**Platform Notes:**
- Full compatibility across all supported platforms

## Dependency Combination Matrix

| Combination | Python 3.10 | Python 3.11 | Python 3.12 | Notes |
|-------------|-------------|-------------|-------------|-------|
| Core only | ✅ | ✅ | ✅ | |
| `[llm]` | ⚠️ | ✅ | ✅ | vLLM requires 3.11+ |
| `[queue]` | ✅ | ✅ | ✅ | |
| `[otel]` | ✅ | ✅ | ✅ | |
| `[llm,queue]` | ⚠️ | ✅ | ✅ | vLLM requires 3.11+ |
| `[llm,otel]` | ⚠️ | ✅ | ✅ | vLLM requires 3.11+ |
| `[queue,otel]` | ✅ | ✅ | ✅ | |
| `[all]` | ⚠️ | ✅ | ✅ | vLLM requires 3.11+ |

## Known Compatibility Issues

### Python 3.10 with vLLM

vLLM requires Python 3.11+ for full functionality. If you need vLLM support, use Python 3.11 or later.

**Workaround:** Install without vLLM:
```bash
pip install metamorphic-guard[llm]
# Then manually install only openai and anthropic
pip install openai anthropic
```

### Kafka on Windows

Kafka Python client may require additional native libraries on Windows. Consider using Redis or RabbitMQ instead for Windows deployments.

### Apple Silicon (M1/M2/M3) Macs

All dependencies are compatible with Apple Silicon. Some packages may install ARM64 wheels automatically.

## Testing Matrix

The following combinations are tested in CI:

| Python | OS | Profiles Tested |
|--------|----|-----------------|
| 3.10 | Ubuntu 22.04 | Core, queue, otel |
| 3.11 | Ubuntu 22.04 | All profiles |
| 3.11 | macOS 13 | All profiles |
| 3.12 | Ubuntu 22.04 | All profiles |
| 3.12 | Windows Server 2022 | Core, queue, otel |

## Version Compatibility

Metamorphic Guard follows semantic versioning:
- **Major versions (3.x)**: May include breaking API changes
- **Minor versions (x.1.x)**: New features, backward compatible
- **Patch versions (x.x.1)**: Bug fixes, backward compatible

### Backward Compatibility Policy

- Core API remains stable within major versions
- Optional dependency version requirements may increase in minor versions
- Deprecated features are removed in major versions only

## Getting Help

If you encounter compatibility issues:

1. Check this matrix for known issues
2. Review the [Installation Guide](../getting-started/installation.md)
3. Check [GitHub Issues](https://github.com/duhboto/MetamorphicGuard/issues) for similar reports
4. Open a new issue with:
   - Python version (`python --version`)
   - OS and version
   - Install profile used
   - Full error traceback

