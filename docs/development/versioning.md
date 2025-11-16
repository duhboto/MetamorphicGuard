# Versioning Policy

This document describes the versioning strategy and backward compatibility guarantees for Metamorphic Guard.

## Semantic Versioning

Metamorphic Guard follows **Semantic Versioning (SemVer)**:

- MAJOR: Incompatible API changes
- MINOR: Backward-compatible feature additions
- PATCH: Backward-compatible bug fixes

Examples:
- 3.0.0 → 4.0.0: breaking changes
- 3.0.0 → 3.1.0: new features, no breaking changes
- 3.0.0 → 3.0.1: bug fixes only

## Compatibility Guarantees

Within a MAJOR series (e.g., 3.x):
- Public APIs documented in `docs/api/` remain backward compatible
- CLI commands and core options remain stable
- Configuration schemas preserve existing keys; new keys are optional
- Backward-compatibility shims are deprecated before removal

## Deprecation Policy

- Deprecations are announced in the CHANGELOG
- Deprecated APIs are marked in docs and code (warnings when practical)
- Minimum deprecation window: one MINOR release before removal

## Supported Python Versions

See `docs/development/compatibility.md` for the current Python support matrix.

## Release Types

- Feature Release: increments MINOR, may introduce deprecations
- Patch Release: increments PATCH, no new features, no deprecations
- Security Release: increments PATCH, may be shipped out-of-band

## Breaking Changes

Breaking changes are only allowed in MAJOR releases and must:
- Be documented in `CHANGELOG.md`
- Include migration notes
- Avoid breaking serialized data formats whenever possible

## Library and CLI

Both the Python API and CLI are covered by this policy. Internal/private modules (prefix `_`) are not included in compatibility guarantees.
