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

## Responsible Disclosure

If you discover a security issue, please open a private security advisory or contact the maintainers. Avoid filing public issues containing exploit details.


