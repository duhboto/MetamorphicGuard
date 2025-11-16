# Release Checklist

Use this checklist for each release to ensure quality and consistency.

## Pre-Release
- [ ] Version bumped in `pyproject.toml`
- [ ] `CHANGELOG.md` updated with new version and date
- [ ] All tests pass locally (`pytest -q`)
- [ ] Optional dependency validation script passes for profiles (base, llm, otel, queue, docs)
- [ ] Docs build locally if changed (mkdocs build)

## Tagging
- [ ] Create annotated tag `vX.Y.Z`
- [ ] Push tag to GitHub (`git push origin vX.Y.Z`)

## CI Validations (automatic)
- [ ] Tag matches `pyproject.toml` version
- [ ] Changelog contains `## [X.Y.Z]` entry
- [ ] Build passes (`python -m build`)
- [ ] Twine metadata check passes

## Publishing
- [ ] Publish job succeeded
- [ ] PyPI page shows new version

## Post-Release
- [ ] Create GitHub Release with highlights and changelog
- [ ] Update README badges if needed
- [ ] Open follow-up issues for any deferred items

## Rollback Plan
- [ ] Be prepared to yank the release on PyPI if critical issues found
- [ ] Document remediation steps in follow-up PR

