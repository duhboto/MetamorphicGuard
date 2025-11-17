# Production Deployment Guide

Comprehensive guide for deploying Metamorphic Guard in production environments.

## Prerequisites

- Kubernetes cluster (1.20+) or Docker Compose
- Queue backend (Redis, SQS, RabbitMQ, or Kafka)
- Monitoring infrastructure (Prometheus + Grafana)
- Container registry access
- Network access to queue backend

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Coordinator │────▶│   Queue     │◀────│   Workers   │
│  (1 pod)    │     │   Backend   │     │ (N pods)    │
└─────────────┘     └─────────────┘     └─────────────┘
       │                    │                   │
       └────────────────────┴───────────────────┘
                            │
                   ┌────────▼────────┐
                   │   Prometheus    │
                   │    + Grafana    │
                   └─────────────────┘
```

## Deployment Steps

### 1. Queue Backend Setup

#### Redis (Recommended for most deployments)

```bash
# Using Helm
helm install redis bitnami/redis \
  --set auth.enabled=true \
  --set auth.password=${REDIS_PASSWORD} \
  --set persistence.enabled=true

# Get connection details
REDIS_HOST=$(kubectl get svc redis -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
REDIS_PORT=6379
```

#### AWS SQS

```bash
# Create queue
aws sqs create-queue \
  --queue-name metamorphic-guard-tasks \
  --attributes VisibilityTimeout=60

# Get queue URL
QUEUE_URL=$(aws sqs get-queue-url --queue-name metamorphic-guard-tasks --query QueueUrl --output text)
```

#### RabbitMQ

```yaml
# docker-compose.yml
rabbitmq:
  image: rabbitmq:3-management
  environment:
    RABBITMQ_DEFAULT_USER: admin
    RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
  ports:
    - "5672:5672"
    - "15672:15672"
```

### 2. Build Container Image

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install package
COPY . .
RUN pip install -e .

# Expose metrics port
EXPOSE 9090

# Default command (override in deployment)
CMD ["metamorphic-guard", "worker"]
```

```bash
# Build and push
docker build -t my-registry/metamorphic-guard:latest .
docker push my-registry/metamorphic-guard:latest
```

### 3. Kubernetes Deployment

#### Coordinator Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metamorphic-guard-coordinator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: metamorphic-guard
      component: coordinator
  template:
    metadata:
      labels:
        app: metamorphic-guard
        component: coordinator
    spec:
      containers:
      - name: coordinator
        image: my-registry/metamorphic-guard:latest
        command:
        - metamorphic-guard
        - evaluate
        - --task
        - ${TASK_NAME}
        - --baseline
        - ${BASELINE_PATH}
        - --candidate
        - ${CANDIDATE_PATH}
        - --dispatcher
        - queue
        - --queue-config
        - '{"backend":"redis","url":"redis://redis:6379/0"}'
        - --metrics
        - --metrics-port
        - "9090"
        env:
        - name: METAMORPHIC_GUARD_PROMETHEUS
          value: "1"
        ports:
        - containerPort: 9090
          name: metrics
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: metamorphic-guard-coordinator
spec:
  selector:
    app: metamorphic-guard
    component: coordinator
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
```

#### Worker Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metamorphic-guard-worker
spec:
  replicas: 10  # Start with 10 workers, scale as needed
  selector:
    matchLabels:
      app: metamorphic-guard
      component: worker
  template:
    metadata:
      labels:
        app: metamorphic-guard
        component: worker
    spec:
      containers:
      - name: worker
        image: my-registry/metamorphic-guard:latest
        command:
        - metamorphic-guard
        - worker
        - --backend
        - redis
        - --queue-config
        - '{"backend":"redis","url":"redis://redis:6379/0"}'
        - --log-json
        - --metrics
        - --metrics-port
        - "9090"
        env:
        - name: METAMORPHIC_GUARD_PROMETHEUS
          value: "1"
        ports:
        - containerPort: 9090
          name: metrics
        resources:
          requests:
            memory: "1Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "4000m"
        livenessProbe:
          httpGet:
            path: /metrics
            port: 9090
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /metrics
            port: 9090
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: metamorphic-guard-worker
spec:
  selector:
    app: metamorphic-guard
    component: worker
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
```

#### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: metamorphic-guard-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: metamorphic-guard-worker
  minReplicas: 5
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  # Scale based on queue depth (requires custom metrics adapter)
  - type: External
    external:
      metric:
        name: queue_pending_tasks
      target:
        type: AverageValue
        averageValue: "10"  # Scale up if >10 tasks per worker
```

### 4. Configuration Management

#### ConfigMap for Queue Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: metamorphic-guard-config
data:
  queue-config.json: |
    {
      "backend": "redis",
      "url": "redis://redis:6379/0",
      "heartbeat_timeout": 60,
      "circuit_breaker_threshold": 3,
      "heartbeat_check_interval": 10.0,
      "enable_requeue": true,
      "max_requeue_attempts": 3,
      "adaptive_batching": true,
      "initial_batch_size": 10,
      "max_batch_size": 100,
      "compress": true
    }
```

#### Secrets for Sensitive Data

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: metamorphic-guard-secrets
type: Opaque
stringData:
  redis-password: ${REDIS_PASSWORD}
  openai-api-key: ${OPENAI_API_KEY}
  anthropic-api-key: ${ANTHROPIC_API_KEY}
```

### 5. Monitoring Setup

#### Prometheus ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: metamorphic-guard
spec:
  selector:
    matchLabels:
      app: metamorphic-guard
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
```

#### Grafana Dashboard Import

1. Import dashboard from `docs/grafana/metamorphic-guard-dashboard.json`
2. Configure Prometheus data source
3. Customize alert thresholds as needed

### 6. Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: metamorphic-guard-network-policy
spec:
  podSelector:
    matchLabels:
      app: metamorphic-guard
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector: {}  # Allow from monitoring namespace
    ports:
    - protocol: TCP
      port: 9090  # Metrics port
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: redis  # Allow access to Redis
    ports:
    - protocol: TCP
      port: 6379
  - to: []  # Allow all outbound (for worker tasks)
```

## Security Hardening

### 1. Use Docker Executor for Untrusted Code

```json
{
  "executor": "docker",
  "executor_config": {
    "image": "python:3.11-slim",
    "read_only": true,
    "cap_drop": ["ALL"],
    "tmpfs": ["/tmp"],
    "security_opt": ["no-new-privileges:true"]
  }
}
```

### 2. Resource Limits

```yaml
resources:
  limits:
    memory: "2Gi"
    cpu: "2000m"
  requests:
    memory: "512Mi"
    cpu: "500m"
```

### 3. Network Policies

Restrict network access to minimum required:
- Workers: Queue backend only
- Coordinator: Queue backend + metrics endpoint

### 4. Secrets Management

- Use Kubernetes Secrets or external secret management (Vault, AWS Secrets Manager)
- Never commit API keys or passwords
- Rotate credentials regularly

## Performance Optimization

### Queue Backend Tuning

**Redis:**
```bash
# Increase memory
redis-cli CONFIG SET maxmemory 4gb

# Enable persistence
redis-cli CONFIG SET save "900 1 300 10 60 10000"
```

**SQS:**
- Use long polling (20 seconds)
- Set appropriate visibility timeout
- Enable dead-letter queue

### Worker Tuning

```yaml
# Increase batch size for fast tasks
"initial_batch_size": 20,
"max_batch_size": 200

# Enable compression for large payloads
"compress": true

# Tune heartbeat based on task duration
"heartbeat_timeout": 120  # 2x average task duration
```

## High Availability

### Multi-Region Deployment

1. **Primary region:** Full deployment (coordinator + workers + queue)
2. **Secondary region:** Workers only (read from shared queue)
3. **Queue replication:** Use queue backend HA features (Redis Cluster, SQS)

### Failover Procedures

1. **Queue backend failover:**
   - Use Redis Sentinel or AWS SQS multi-region
   - Update queue config to point to new backend
   - Restart workers

2. **Worker failover:**
   - Automatic via Kubernetes (restarts crashed pods)
   - Tasks automatically requeued on worker loss

3. **Coordinator failover:**
   - Use StatefulSet for coordinator
   - Or implement external coordination (e.g., via database)

## Capacity Planning

### Worker Count Calculation

```
workers = (task_count * avg_task_duration_s) / (max_evaluation_time_s * concurrency_per_worker)
```

Example:
- 10,000 tasks
- Average duration: 2 seconds
- Max evaluation time: 1 hour (3600s)
- Concurrency: 2 tasks per worker

```
workers = (10000 * 2) / (3600 * 2) = 2.78 ≈ 3 workers
```

### Queue Capacity

- **Redis:** Limited by memory (typically handles millions of tasks)
- **SQS:** 120,000 in-flight messages standard, 300,000 extended
- **Kafka:** Virtually unlimited (disk-based)

## Backup & Recovery

### Configuration Backup

```bash
# Backup ConfigMaps and Secrets
kubectl get configmap metamorphic-guard-config -o yaml > backup/configmap.yaml
kubectl get secret metamorphic-guard-secrets -o yaml > backup/secret.yaml
```

### Queue Backup (Redis)

```bash
# Enable persistence
redis-cli CONFIG SET save "900 1 300 10 60 10000"

# Manual backup
redis-cli BGSAVE

# Restore from backup
redis-cli --rdb /path/to/dump.rdb
```

### Recovery Procedures

1. **Restore from backup:**
   ```bash
   kubectl apply -f backup/configmap.yaml
   kubectl apply -f backup/secret.yaml
   ```

2. **Restart deployments:**
   ```bash
   kubectl rollout restart deployment/metamorphic-guard-coordinator
   kubectl rollout restart deployment/metamorphic-guard-worker
   ```

3. **Verify connectivity:**
   ```bash
   kubectl exec -it deployment/metamorphic-guard-worker -- \
     metamorphic-guard worker --backend redis --queue-config '...'
   ```

## Troubleshooting

### Common Deployment Issues

1. **Image pull errors:**
   - Verify registry credentials
   - Check network access to registry

2. **Queue connection failures:**
   - Verify queue backend is accessible
   - Check DNS resolution
   - Verify credentials

3. **Worker pod crashes:**
   - Check resource limits
   - Review logs: `kubectl logs deployment/metamorphic-guard-worker`
   - Check events: `kubectl describe pod <pod-name>`

### Health Checks

```bash
# Check coordinator
kubectl get deployment metamorphic-guard-coordinator

# Check workers
kubectl get deployment metamorphic-guard-worker

# Check queue connection
kubectl exec -it deployment/metamorphic-guard-worker -- \
  redis-cli -h redis PING

# Check metrics endpoint
curl http://metamorphic-guard-worker:9090/metrics
```

## See Also

- [Queue Dispatch Guide](queue-dispatch.md) - Queue configuration
- [Operational Runbook](runbook.md) - Day-to-day operations
- [Prometheus Metrics Guide](prometheus.md) - Monitoring setup
- [Security Guide](../../SECURITY.md) - Security best practices

