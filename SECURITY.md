# Security Guidance for Metamorphic Guard

Metamorphic Guard executes baseline and candidate implementations in a sandbox to reduce risk during evaluation. The built-in `local` executor provides application-level isolation but does not offer kernel-level security boundaries.

## Recommended Defaults

- For any untrusted or semi-trusted code, prefer the Docker executor:
  - `--executor docker`
  - `--executor-config '{"image":"python:3.11-slim","read_only":true,"cap_drop":["ALL"],"tmpfs":["/tmp"],"security_opt":["no-new-privileges:true"]}'`
- Plugin monitors are sandboxed by default. Keep sandboxing enabled unless you trust the plugin code.
- Set resource limits (`mem_mb`, per-case `timeout_s`) and keep `violation_cap` reasonable.

## Local Executor Caveats

The `local` executor enforces:
- Network denial via stubs
- Blocking subprocess creation and native FFI
- Disabling user site-packages
- Per-test CPU time/memory limits

It does not provide:
- Kernel-level isolation
- Filesystem namespace isolation beyond process controls

Do not use `local` for untrusted code on shared hosts. The library will log a warning by default; set `METAMORPHIC_GUARD_SUPPRESS_SECURITY_WARNING=1` to silence it.

## Docker Hardening Tips

- Read-only root filesystem
- Drop capabilities (`--cap-drop ALL`)
- Seccomp/AppArmor profiles
- `--security-opt no-new-privileges:true`
- User namespaces
- Minimal base images (e.g., `python:3.11-slim`)

## Automated Security Scanning

Metamorphic Guard uses automated security scanning to identify and remediate vulnerabilities:

### Dependency Vulnerability Scanning

- **Dependabot**: Automated dependency updates are enabled via `.github/dependabot.yml`
  - Weekly scans run every Monday at 09:00 UTC
  - Pull requests are automatically created for security updates
  - Updates are grouped by type (production vs. dev dependencies)
- **CI Security Scan**: Every push and PR triggers a security scan job (`security-scan` in CI)
  - Uses `pip-audit` to scan for known vulnerabilities
  - CI fails on critical severity vulnerabilities
  - Medium/high severity vulnerabilities are reported but non-blocking
  - Vulnerability reports are uploaded as CI artifacts

### Vulnerability Response Process

1. **Automated Detection**: Vulnerabilities are automatically detected via:
   - Dependabot security updates (creates PR)
   - CI security scan (reports in CI artifacts)
   - GitHub Security Advisories (alerts repository maintainers)

2. **Severity Classification**:
   - **Critical**: Immediate action required, CI fails, security patch released
   - **High**: Priority fix, assessed within 48 hours
   - **Medium**: Scheduled fix, assessed within 1 week
   - **Low**: Included in next regular release cycle

3. **Remediation**:
   - **Critical/High**: Security patch released ASAP (may skip normal release process)
   - **Medium/Low**: Included in next planned release
   - If upstream fix unavailable, consider:
     - Pin to last known-good version
     - Document workaround if available
     - Remove vulnerable dependency if feasible

4. **Communication**:
   - Critical vulnerabilities: Security advisory published on GitHub
   - All vulnerabilities: Documented in CHANGELOG.md
   - Users: Notified via security advisory if user data at risk

### Reporting Security Issues

If you discover a security issue, please:

1. **Do NOT** create a public issue
2. **Do** open a private security advisory at: https://github.com/duhboto/MetamorphicGuard/security/advisories/new
3. **Do** include:
   - Description of the vulnerability
   - Steps to reproduce (if applicable)
   - Potential impact
   - Suggested remediation (if known)

### Security Best Practices for Users

- **Keep dependencies updated**: Use `pip install --upgrade metamorphic-guard` regularly
- **Monitor advisories**: Subscribe to GitHub security advisories for this repository
- **Use Docker executor**: For untrusted code, always use `--executor docker` with hardened config
- **Set resource limits**: Use `--timeout-s` and `--mem-mb` to limit execution resources
- **Review reports**: Check evaluation reports for unexpected behavior or errors
- **Use sandboxing**: Keep plugin sandboxing enabled unless you trust the plugin code

## Responsible Disclosure

If you discover a security issue, please open a private security advisory or contact the maintainers. Avoid filing public issues containing exploit details.

We appreciate responsible disclosure and will work with reporters to address issues promptly.


