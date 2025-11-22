# Remote Executor Safety Guide

When scaling Metamorphic Guard using remote executors (e.g., Redis queue, Kubernetes workers), security and isolation become critical.

## Security Model

Metamorphic Guard executors run arbitrary Python code provided in test definitions. **Never connect executors to a public network or process untrusted input without strict sandboxing.**

### 1. Network Isolation
*   **Private VPC**: Ensure Redis/Queue backends and Workers run inside a private VPC.
*   **Firewall Rules**: Block all inbound connections to workers except from the Queue/Broker.
*   **No Public Ingress**: Workers should not accept incoming HTTP/TCP connections.

### 2. Secrets Management
*   **Environment Variables**: Do not bake secrets (API keys) into worker images. Inject them at runtime (e.g., Kubernetes Secrets).
*   **Redaction**: Use the `SecretRedactor` feature to scrub sensitive values from logs and reports.
    ```python
    from metamorphic_guard.redaction import SecretRedactor
    import re
    
    # Redact anything looking like an API key
    redactor = SecretRedactor([re.compile(r"sk-[a-zA-Z0-9]{48}")])
    ```

### 3. Container Hardening (Docker/K8s)
*   **Non-Root User**: Always run the worker process as a non-root user.
*   **Read-Only Root Filesystem**: Mount the root FS as read-only to prevent persistence.
*   **Resource Limits**: Set strict CPU and Memory requests/limits to prevent "noisy neighbor" denial of service.
    ```yaml
    resources:
      limits:
        memory: "1Gi"
        cpu: "1000m"
    ```
*   **No Privileged Mode**: Never run worker containers with `--privileged`.

### 4. Code Execution Policy
*   **Trusted Source**: Only run test definitions from trusted repositories (e.g., internal git).
*   **Review Process**: Require code review for changes to `Task` definitions and `RunCase` logic.
*   **Sandboxing**: Even within a container, use `sandbox=true` (subprocess isolation) for an extra layer of defense against memory leaks or crashes affecting the worker daemon.

## Data Privacy
*   **PII**: Avoid sending PII (Personally Identifiable Information) in test inputs.
*   **Data Retention**: Configure your Queue backend (Redis) with an eviction policy or TTL to ensure task payloads don't persist indefinitely.


