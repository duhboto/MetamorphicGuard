# Deployment Guide

This guide covers deployment strategies for Metamorphic Guard, from single-machine setups to distributed containerized deployments.

## Overview

Metamorphic Guard can be deployed in several configurations:

1. **Single Machine**: Local execution with thread/process pools
2. **Distributed**: Queue-based execution with remote workers
3. **Containerized**: Docker/Kubernetes deployments
4. **Serverless**: AWS Lambda, Google Cloud Functions, Azure Functions

## Single Machine Deployment

### Basic Installation

```bash
# Install from PyPI
pip install metamorphic-guard

# Or install from source
git clone https://github.com/your-org/metamorphic-guard.git
cd metamorphic-guard
pip install -e .
```

### Local Execution

```bash
# Run evaluation locally
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --n 400 \
    --parallel 4
```

### Resource Considerations

**CPU:**
- Single-threaded: 1 CPU core
- Parallel execution: 1 core per worker (default: 1)
- Recommended: 4-8 cores for parallel execution

**Memory:**
- Base: ~200MB
- Per worker: ~100-500MB (depends on task)
- Recommended: 2-4GB for parallel execution

**Disk:**
- Base installation: ~50MB
- Reports: ~1-10MB per evaluation
- Logs: ~1-100MB per evaluation (if enabled)
- Recommended: 10GB free space

## Distributed Deployment

### Architecture

```
┌─────────────┐
│ Coordinator │  Dispatches tasks to queue
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Queue     │  Redis/SQS/RabbitMQ/Kafka
└──────┬──────┘
       │
       ├──────────┬──────────┬──────────┐
       ▼          ▼          ▼          ▼
   ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
   │Worker│  │Worker│  │Worker│  │Worker│
   └──────┘  └──────┘  └──────┘  └──────┘
```

### Coordinator Setup

The coordinator dispatches tasks to the queue:

```bash
# Start coordinator
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --dispatcher queue \
    --queue-config '{"backend": "redis", "connection": {"host": "redis.example.com", "port": 6379}}' \
    --log-json \
    --metrics \
    --metrics-port 9090
```

### Worker Setup

Workers consume tasks from the queue:

```bash
# Start worker
metamorphic-guard worker \
    --backend redis \
    --queue-config '{"backend": "redis", "connection": {"host": "redis.example.com", "port": 6379}}' \
    --poll-interval 1.0 \
    --log-json \
    --metrics \
    --metrics-port 9091
```

### Scaling Workers

Scale workers horizontally based on queue depth:

```bash
# Start multiple workers
for i in {1..10}; do
  metamorphic-guard worker \
      --backend redis \
      --queue-config '{"backend": "redis", "connection": {"host": "redis.example.com", "port": 6379}}' \
      --log-file "logs/worker-$i.jsonl" \
      --metrics-port $((9091 + i)) &
done
```

## Docker Deployment

### Basic Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir metamorphic-guard[observability]

# Copy application code (if needed)
# COPY . /app

# Expose metrics port
EXPOSE 9090

# Default command
CMD ["metamorphic-guard", "evaluate", "--help"]
```

### Coordinator Container

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir metamorphic-guard[observability,queue]

EXPOSE 9090

CMD ["metamorphic-guard", "evaluate", \
     "--task", "${TASK}", \
     "--baseline", "${BASELINE}", \
     "--candidate", "${CANDIDATE}", \
     "--dispatcher", "queue", \
     "--queue-config", "${QUEUE_CONFIG}", \
     "--log-json", \
     "--metrics", \
     "--metrics-port", "9090"]
```

### Worker Container

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir metamorphic-guard[observability,queue]

EXPOSE 9091

CMD ["metamorphic-guard", "worker", \
     "--backend", "${QUEUE_BACKEND}", \
     "--queue-config", "${QUEUE_CONFIG}", \
     "--log-json", \
     "--metrics", \
     "--metrics-port", "9091"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  coordinator:
    build:
      context: .
      dockerfile: Dockerfile.coordinator
    environment:
      - TASK=my_task
      - BASELINE=old.py
      - CANDIDATE=new.py
      - QUEUE_CONFIG={"backend":"redis","connection":{"host":"redis","port":6379}}
    depends_on:
      - redis
    ports:
      - "9090:9090"
    volumes:
      - ./reports:/app/reports
      - ./logs:/app/logs

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - QUEUE_BACKEND=redis
      - QUEUE_CONFIG={"backend":"redis","connection":{"host":"redis","port":6379}}
    deploy:
      replicas: 5
    depends_on:
      - redis
    ports:
      - "9091-9095:9091"
    volumes:
      - ./logs:/app/logs

volumes:
  redis-data:
```

### Production Docker Compose

For production deployments, use the hardened configuration:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    command:
      - redis-server
      - "--appendonly"
      - "yes"
      - "--appendfsync"
      - "everysec"
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  coordinator:
    image: my-registry/metamorphic-guard:latest
    environment:
      - METAMORPHIC_GUARD_LOG_JSON=1
      - METAMORPHIC_GUARD_PROMETHEUS=1
    command:
      - metamorphic-guard
      - evaluate
      - --task
      - my_task
      - --baseline
      - old.py
      - --candidate
      - new.py
      - --dispatcher
      - queue
      - --queue-config
      - '{"backend":"redis","connection":{"host":"redis","port":6379}}'
      - --log-json
      - --metrics
      - --metrics-port
      - "9090"
    depends_on:
      redis:
        condition: service_healthy
    ports:
      - "9090:9090"
    volumes:
      - ./reports:/app/reports:rw
      - ./logs:/app/logs:rw
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/metrics"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    image: my-registry/metamorphic-guard:latest
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    environment:
      - PYTHONUNBUFFERED=1
      - METAMORPHIC_GUARD_LOG_JSON=1
      - METAMORPHIC_GUARD_PROMETHEUS=1
    command:
      - metamorphic-guard
      - worker
      - --backend
      - redis
      - --queue-config
      - '{"backend":"redis","connection":{"host":"redis","port":6379}}'
      - --log-json
      - --metrics
      - --metrics-port
      - "9091"
    deploy:
      replicas: 10
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    depends_on:
      redis:
        condition: service_healthy
    ports:
      - "9091-9100:9091"
    volumes:
      - ./logs:/app/logs:rw
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/metrics"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  redis-data:
```

## Kubernetes Deployment

### Basic Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metamorphic-guard-coordinator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: metamorphic-guard-coordinator
  template:
    metadata:
      labels:
        app: metamorphic-guard-coordinator
    spec:
      containers:
      - name: coordinator
        image: my-registry/metamorphic-guard:latest
        command:
        - metamorphic-guard
        - evaluate
        - --task
        - my_task
        - --baseline
        - old.py
        - --candidate
        - new.py
        - --dispatcher
        - queue
        - --queue-config
        - '{"backend":"redis","connection":{"host":"redis-service","port":6379}}'
        - --log-json
        - --metrics
        - --metrics-port
        - "9090"
        env:
        - name: METAMORPHIC_GUARD_LOG_JSON
          value: "1"
        - name: METAMORPHIC_GUARD_PROMETHEUS
          value: "1"
        ports:
        - containerPort: 9090
          name: metrics
        volumeMounts:
        - name: reports
          mountPath: /app/reports
        - name: logs
          mountPath: /app/logs
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
      volumes:
      - name: reports
        persistentVolumeClaim:
          claimName: reports-pvc
      - name: logs
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: metamorphic-guard-coordinator
spec:
  selector:
    app: metamorphic-guard-coordinator
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metamorphic-guard-worker
spec:
  replicas: 10
  selector:
    matchLabels:
      app: metamorphic-guard-worker
  template:
    metadata:
      labels:
        app: metamorphic-guard-worker
    spec:
      containers:
      - name: worker
        image: my-registry/metamorphic-guard:latest
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        command:
        - metamorphic-guard
        - worker
        - --backend
        - redis
        - --queue-config
        - '{"backend":"redis","connection":{"host":"redis-service","port":6379}}'
        - --log-json
        - --metrics
        - --metrics-port
        - "9090"
        env:
        - name: METAMORPHIC_GUARD_LOG_JSON
          value: "1"
        - name: METAMORPHIC_GUARD_PROMETHEUS
          value: "1"
        ports:
        - containerPort: 9090
          name: metrics
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: logs
          mountPath: /app/logs
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
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
      volumes:
      - name: tmp
        emptyDir: {}
      - name: logs
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: metamorphic-guard-worker
spec:
  selector:
    app: metamorphic-guard-worker
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Horizontal Pod Autoscaler

Scale workers based on queue depth:

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
  - type: External
    external:
      metric:
        name: metamorphic_queue_pending_tasks
      target:
        type: AverageValue
        averageValue: "10"  # Scale up if > 10 pending tasks per pod
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 5
        periodSeconds: 30
      selectPolicy: Max
```

### Redis Deployment

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis-service
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
        - redis-server
        - --appendonly
        - "yes"
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: data
          mountPath: /data
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes:
        - ReadWriteOnce
      resources:
        requests:
          storage: 10Gi
```

## Helm Chart

A Helm chart is available in `deploy/helm/metamorphic-guard/`:

```bash
# Install chart
helm install metamorphic-guard ./deploy/helm/metamorphic-guard \
    --set coordinator.task=my_task \
    --set coordinator.baseline=old.py \
    --set coordinator.candidate=new.py \
    --set redis.enabled=true \
    --set worker.replicas=10
```

### Customizing Values

```yaml
# values.yaml
coordinator:
  task: my_task
  baseline: old.py
  candidate: new.py
  dispatcher: queue
  queueConfig:
    backend: redis
    connection:
      host: redis-service
      port: 6379
  metrics:
    enabled: true
    port: 9090
  logging:
    enabled: true
    json: true

worker:
  replicas: 10
  queueConfig:
    backend: redis
    connection:
      host: redis-service
      port: 6379
  metrics:
    enabled: true
    port: 9090
  resources:
    requests:
      memory: "512Mi"
      cpu: "500m"
    limits:
      memory: "2Gi"
      cpu: "2000m"

redis:
  enabled: true
  persistence:
    enabled: true
    size: 10Gi
```

## Serverless Deployment

### AWS Lambda

```python
# lambda_handler.py
import json
from metamorphic_guard import run_eval

def lambda_handler(event, context):
    result = run_eval(
        task_name=event['task'],
        baseline_path=event['baseline'],
        candidate_path=event['candidate'],
        n=event.get('n', 400),
        dispatcher='local',
        parallel=1
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
```

```yaml
# serverless.yml
service: metamorphic-guard

provider:
  name: aws
  runtime: python3.11
  memorySize: 2048
  timeout: 900

functions:
  evaluate:
    handler: lambda_handler.lambda_handler
    events:
      - http:
          path: evaluate
          method: post
```

### Google Cloud Functions

```python
# main.py
import json
from metamorphic_guard import run_eval

def evaluate(request):
    request_json = request.get_json()
    
    result = run_eval(
        task_name=request_json['task'],
        baseline_path=request_json['baseline'],
        candidate_path=request_json['candidate'],
        n=request_json.get('n', 400)
    )
    
    return json.dumps(result), 200, {'Content-Type': 'application/json'}
```

### Azure Functions

```python
# __init__.py
import json
import azure.functions as func
from metamorphic_guard import run_eval

def main(req: func.HttpRequest) -> func.HttpResponse:
    req_body = req.get_json()
    
    result = run_eval(
        task_name=req_body['task'],
        baseline_path=req_body['baseline'],
        candidate_path=req_body['candidate'],
        n=req_body.get('n', 400)
    )
    
    return func.HttpResponse(
        json.dumps(result),
        mimetype="application/json"
    )
```

## Security Considerations

### Container Security

1. **Use non-root user:**
   ```dockerfile
   RUN useradd -m -u 1000 appuser
   USER appuser
   ```

2. **Read-only filesystem:**
   ```yaml
   securityContext:
     readOnlyRootFilesystem: true
   volumeMounts:
   - name: tmp
     mountPath: /tmp
   ```

3. **Drop capabilities:**
   ```yaml
   securityContext:
     capabilities:
       drop:
       - ALL
   ```

4. **No privilege escalation:**
   ```yaml
   securityContext:
     allowPrivilegeEscalation: false
   ```

### Network Security

1. **Use internal networks:**
   ```yaml
   networks:
     - internal
   ```

2. **Restrict ingress:**
   ```yaml
   # Only expose metrics port internally
   ports:
   - containerPort: 9090
     name: metrics
   ```

3. **Use service mesh:**
   - Istio
   - Linkerd
   - Consul Connect

### Secrets Management

1. **Use Kubernetes secrets:**
   ```yaml
   env:
   - name: REDIS_PASSWORD
     valueFrom:
       secretKeyRef:
         name: redis-secret
         key: password
   ```

2. **Use external secret managers:**
   - AWS Secrets Manager
   - HashiCorp Vault
   - Google Secret Manager

## Monitoring and Observability

### Metrics Collection

Enable Prometheus metrics:

```bash
# Coordinator
--metrics --metrics-port 9090

# Worker
--metrics --metrics-port 9091
```

### Log Aggregation

Enable structured logging:

```bash
# Coordinator
--log-json --log-file logs/coordinator.jsonl

# Worker
--log-json --log-file logs/worker.jsonl
```

### Distributed Tracing

Enable OpenTelemetry:

```bash
--otlp-endpoint http://otel-collector:4317
```

## Performance Tuning

### Worker Scaling

Scale workers based on:
- Queue depth
- Task duration
- Available resources

```bash
# Calculate optimal worker count
optimal_workers = (queue_depth * avg_task_duration) / target_completion_time
```

### Resource Limits

Set appropriate resource limits:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

### Queue Configuration

Optimize queue settings:

```json
{
  "backend": "redis",
  "adaptive_batching": true,
  "initial_batch_size": 10,
  "max_batch_size": 100,
  "lease_seconds": 60,
  "heartbeat_timeout": 30
}
```

## Troubleshooting

### Workers Not Processing

1. **Check queue connection:**
   ```bash
   # Redis
   redis-cli -h redis.example.com PING
   ```

2. **Check worker logs:**
   ```bash
   kubectl logs -l app=metamorphic-guard-worker
   ```

3. **Check worker registration:**
   ```bash
   # Redis
   redis-cli KEYS "metamorphic_guard:workers:*"
   ```

### High Memory Usage

1. **Reduce worker count:**
   ```yaml
   replicas: 5  # Reduce from 10
   ```

2. **Reduce batch size:**
   ```json
   {
     "max_batch_size": 50  # Reduce from 100
   }
   ```

3. **Enable compression:**
   ```json
   {
     "compress": true
   }
   ```

### Network Issues

1. **Check DNS resolution:**
   ```bash
   kubectl exec -it pod-name -- nslookup redis-service
   ```

2. **Check network policies:**
   ```bash
   kubectl get networkpolicies
   ```

3. **Test connectivity:**
   ```bash
   kubectl exec -it pod-name -- curl http://redis-service:6379
   ```

## Best Practices

### 1. Use Health Checks

Configure health checks for all services:

```yaml
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
```

### 2. Enable Monitoring

Enable metrics and logging for all components:

```bash
--metrics --metrics-port 9090
--log-json --log-file logs/app.jsonl
```

### 3. Use Resource Limits

Set appropriate resource requests and limits:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

### 4. Implement Auto-scaling

Use HPA or cluster autoscaler:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 5
  maxReplicas: 50
  metrics:
  - type: External
    external:
      metric:
        name: metamorphic_queue_pending_tasks
```

### 5. Use Persistent Storage

Use persistent volumes for reports and logs:

```yaml
volumeMounts:
- name: reports
  mountPath: /app/reports
volumes:
- name: reports
  persistentVolumeClaim:
    claimName: reports-pvc
```

### 6. Implement Backup

Backup critical data:

```bash
# Backup Redis
redis-cli --rdb /backup/redis-$(date +%Y%m%d).rdb

# Backup reports
tar -czf reports-$(date +%Y%m%d).tar.gz reports/
```

## See Also

- [Structured Logging Guide](logging.md) - Logging configuration
- [Prometheus Metrics Guide](prometheus.md) - Metrics collection
- [Queue Dispatch Guide](queue-dispatch.md) - Queue configuration
- [Webhooks Guide](webhooks.md) - Alert configuration


