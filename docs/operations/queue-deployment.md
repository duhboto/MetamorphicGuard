# Queue Deployment (Redis)

This guide covers deploying the queue-backed dispatcher with Redis for distributed execution.

## Local docker-compose

Use `deploy/docker-compose.worker.yml` as a starting point. Ensure Redis is reachable by coordinator and workers.

Coordinator:

```bash
metamorphic-guard --dispatcher queue \
  --queue-config '{"backend":"redis","url":"redis://redis:6379/0"}' \
  --task top_k --baseline baseline.py --candidate candidate.py
```

Worker(s):

```bash
metamorphic-guard-worker --backend redis \
  --queue-config '{"url":"redis://redis:6379/0"}'
```

## Kubernetes (Helm)

The `deploy/helm/` charts show a reference layout. Recommended settings:

- Set resource requests/limits for coordinator and workers
- Configure Redis with persistence and network policies
- Expose worker environment:
  - `BACKEND=redis`
  - `QUEUE_URL=redis://redis:6379/0`

## Security Notes

- Restrict Redis to cluster-internal networks
- Enable AUTH for Redis in non-dev environments
- Limit worker privileges; do not mount host paths
- Pair with the Docker executor for sandbox isolation


