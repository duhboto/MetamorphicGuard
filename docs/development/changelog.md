# Changelog Process

This document explains how we maintain `CHANGELOG.md` and the expected sections for each release.

## Format

Each release entry uses this structure:

```
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Behavior changes (backward compatible)

### Fixed
- Bug fixes

### Deprecated
- APIs scheduled for removal (include target removal version)

### Removed
- Items removed in this release (only in MAJOR releases)

### Security
- Security-related changes
```

## Rules
- All user-facing changes must be documented
- Use clear, concise bullets
- Link PRs/issues when helpful
- Keep unreleased changes under `## [Unreleased]`

## Release Checklist (Changelog-specific)
- [ ] New version header added
- [ ] Sections populated (even if empty)
- [ ] Dates are correct (UTC)
- [ ] Version matches `pyproject.toml`
- [ ] Commit the updated changelog

