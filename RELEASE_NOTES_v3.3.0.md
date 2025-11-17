# Release v3.3.0

## CI/CD Improvements & Production Readiness

This release focuses on improving CI/CD reliability and ensuring our security scanning workflows run smoothly without resource constraints.

## What's New

### 🔧 CI/CD Fixes
- **Fixed security scan workflow** - Resolved disk space issues by using `pip-audit --requirement` instead of installing all dependencies
- **Updated GitHub Actions** - Migrated artifact upload actions from deprecated v3 to v4
- **Optimized dependency scanning** - Scans dependencies in separate groups (base, queue, otel, llm) for better efficiency

### 📋 Technical Details

**Security Scanning Improvements:**
- Security scans now use requirement files directly, avoiding installation of large ML dependencies (vLLM, PyTorch, CUDA libraries)
- Scans are performed in parallel across dependency groups for faster execution
- Added documentation about vLLM exclusion in CI environments

**GitHub Actions Updates:**
- `actions/upload-artifact@v4` (was v3)
- `actions/upload-pages-artifact@v4` (was v3)

## Installation

```bash
pip install metamorphic-guard==3.3.0
```

Or with optional dependencies:

```bash
# LLM support
pip install metamorphic-guard[llm]==3.3.0

# Queue backends
pip install metamorphic-guard[queue]==3.3.0

# All optional dependencies
pip install metamorphic-guard[all]==3.3.0
```

## Breaking Changes

**None** - This is a safe minor update with no breaking API changes.

## Full Changelog

See [CHANGELOG.md](https://github.com/duhboto/MetamorphicGuard/blob/main/CHANGELOG.md) for complete release history.

---

**Previous Release:** [v3.2.0](https://github.com/duhboto/MetamorphicGuard/releases/tag/v3.2.0) - Production Readiness Enhancements

