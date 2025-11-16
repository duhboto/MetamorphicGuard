# Queue Dispatch Guide

Metamorphic Guard supports distributed evaluation using queue-based task distribution. This guide covers queue backend configuration, worker deployment, and best practices for distributed execution.

## Overview

Queue-based dispatch enables:
- **Horizontal scaling**: Distribute evaluation across multiple workers
- **Fault tolerance**: Automatic task requeuing on worker failures
- **Resource isolation**: Workers can run on separate machines
- **Backpressure handling**: Queue depth provides natural backpressure

Supported backends:
- **Memory**: In-process queue (testing/development)
- **Redis**: Production-ready, high-performance
- **AWS SQS**: Managed queue service for AWS deployments
- **RabbitMQ**: Message broker with advanced routing
- **Kafka**: High-throughput distributed streaming

## Quick Start

### Basic Queue Configuration

```bash
# Use Redis backend
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --dispatcher queue \
    --queue-config '{"backend": "redis", "connection": {"host": "localhost", "port": 6379}}'
```

### Start Workers

```bash
# Start worker process
metamorphic-guard worker \
    --backend redis \
    --queue-config '{"backend": "redis", "connection": {"host": "localhost", "port": 6379}}' \
    --poll-interval 1.0
```

## Queue Backends

### Memory Backend

In-process queue adapter for testing and development.

**Configuration:**
```json
{
  "backend": "memory",
  "spawn_local_workers": true
}
```

**Use Cases:**
- Local development
- Testing queue logic
- Single-machine deployments

**Limitations:**
- Not persistent (lost on process exit)
- Single process only
- No network distribution

### Redis Backend

Production-ready queue using Redis as the message broker.

**Installation:**
```bash
pip install redis
```

**Configuration:**
```json
{
  "backend": "redis",
  "connection": {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": "optional_password"
  },
  "lease_seconds": 60,
  "heartbeat_timeout": 30,
  "compress": true
}
```

**Connection Options:**
- `host` (str): Redis hostname. Default: `"localhost"`
- `port` (int): Redis port. Default: `6379`
- `db` (int): Redis database number. Default: `0`
- `password` (str, optional): Redis password
- `ssl` (bool): Enable SSL/TLS. Default: `false`
- `decode_responses` (bool): Decode responses as strings. Default: `false`

**Advanced Options:**
- `lease_seconds` (int): Task lease duration in seconds. Default: `60`
- `heartbeat_timeout` (int): Worker heartbeat timeout in seconds. Default: `30`
- `compress` (bool): Compress task payloads. Default: `true`

**Example:**
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Run evaluation
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --dispatcher queue \
    --queue-config '{"backend": "redis", "connection": {"host": "localhost", "port": 6379}}'
```

### AWS SQS Backend

Managed queue service for AWS deployments.

**Installation:**
```bash
pip install boto3
```

**Configuration:**
```json
{
  "backend": "sqs",
  "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/my-queue",
  "region": "us-east-1",
  "max_batch_size": 10,
  "visibility_timeout": 60
}
```

**Configuration Options:**
- `queue_url` (str, required): SQS queue URL
- `region` (str): AWS region. Default: `"us-east-1"`
- `aws_access_key_id` (str, optional): AWS access key
- `aws_secret_access_key` (str, optional): AWS secret key
- `max_batch_size` (int): Maximum batch size (SQS limit: 10). Default: `10`
- `visibility_timeout` (int): Message visibility timeout in seconds. Default: `60`

**AWS Credentials:**
Credentials can be provided via:
1. Configuration file (`~/.aws/credentials`)
2. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
3. IAM roles (for EC2/ECS/Lambda)
4. Configuration options (not recommended for production)

**Example:**
```bash
# Create SQS queue
aws sqs create-queue --queue-name metamorphic-guard-tasks

# Run evaluation
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --dispatcher queue \
    --queue-config '{"backend": "sqs", "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/metamorphic-guard-tasks", "region": "us-east-1"}'
```

### RabbitMQ Backend

Message broker with advanced routing and management features.

**Installation:**
```bash
pip install pika
```

**Configuration:**
```json
{
  "backend": "rabbitmq",
  "url": "amqp://user:pass@localhost:5672/",
  "exchange": "metamorphic_guard",
  "queue": "tasks",
  "routing_key": "task",
  "durable": true,
  "prefetch_count": 10
}
```

**Configuration Options:**
- `url` (str, required): AMQP connection URL
- `exchange` (str): Exchange name. Default: `"metamorphic_guard"`
- `queue` (str): Queue name. Default: `"tasks"`
- `routing_key` (str): Routing key. Default: `"task"`
- `durable` (bool): Make queue/exchange durable. Default: `true`
- `prefetch_count` (int): Consumer prefetch count. Default: `10`

**Example:**
```bash
# Start RabbitMQ
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Run evaluation
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --dispatcher queue \
    --queue-config '{"backend": "rabbitmq", "url": "amqp://guest:guest@localhost:5672/"}'
```

### Kafka Backend

High-throughput distributed streaming platform.

**Installation:**
```bash
pip install kafka-python
```

**Configuration:**
```json
{
  "backend": "kafka",
  "bootstrap_servers": "localhost:9092",
  "topic": "metamorphic_guard_tasks",
  "consumer_group": "metamorphic_guard_workers",
  "max_batch_size": 100,
  "auto_commit": true
}
```

**Configuration Options:**
- `bootstrap_servers` (str, required): Kafka broker addresses (comma-separated)
- `topic` (str): Topic name. Default: `"metamorphic_guard_tasks"`
- `consumer_group` (str): Consumer group ID. Default: `"metamorphic_guard_workers"`
- `max_batch_size` (int): Maximum batch size. Default: `100`
- `auto_commit` (bool): Auto-commit offsets. Default: `true`

**Example:**
```bash
# Start Kafka (requires Zookeeper)
docker-compose up -d zookeeper kafka

# Run evaluation
metamorphic-guard evaluate \
    --task my_task \
    --baseline old.py \
    --candidate new.py \
    --dispatcher queue \
    --queue-config '{"backend": "kafka", "bootstrap_servers": "localhost:9092", "topic": "metamorphic_guard_tasks"}'
```

## Worker Management

### Starting Workers

Workers consume tasks from the queue and execute them.

**Basic Worker:**
```bash
metamorphic-guard worker \
    --backend redis \
    --queue-config '{"backend": "redis", "connection": {"host": "localhost", "port": 6379}}'
```

**Worker Options:**
- `--backend`: Queue backend (`memory`, `redis`, `sqs`, `rabbitmq`, `kafka`)
- `--queue-config`: JSON configuration for queue backend
- `--poll-interval`: Poll interval in seconds (default: `1.0`)
- `--default-timeout-s`: Fallback timeout per task (default: `2.0`)
- `--default-mem-mb`: Fallback memory limit per task (default: `512`)
- `--log-file`: Path to log file
- `--log-json`: Enable JSON logging to stdout
- `--metrics`: Enable Prometheus metrics
- `--metrics-port`: Prometheus metrics port

### Worker Scaling

Scale workers horizontally based on queue depth:

```bash
# Start multiple workers
for i in {1..10}; do
  metamorphic-guard worker \
      --backend redis \
      --queue-config '{"backend": "redis", "connection": {"host": "localhost", "port": 6379}}' \
      --log-file "logs/worker-$i.jsonl" &
done
```

### Kubernetes Deployment

Deploy workers as Kubernetes deployments:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metamorphic-guard-worker
spec:
  replicas: 10
  template:
    metadata:
      labels:
        app: metamorphic-guard-worker
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
        - '{"backend": "redis", "connection": {"host": "redis-service", "port": 6379}}'
        - --log-json
        - --metrics
        - --metrics-port
        - "9090"
        env:
        - name: METAMORPHIC_GUARD_PROMETHEUS
          value: "1"
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
  name: metamorphic-guard-worker
spec:
  selector:
    app: metamorphic-guard-worker
  ports:
  - port: 9090
    targetPort: 9090
    name: metrics
```

### Docker Compose

Deploy workers with Docker Compose:

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  coordinator:
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
      - '{"backend": "redis", "connection": {"host": "redis", "port": 6379}}'
    depends_on:
      - redis

  worker:
    image: my-registry/metamorphic-guard:latest
    command:
      - metamorphic-guard
      - worker
      - --backend
      - redis
      - --queue-config
      - '{"backend": "redis", "connection": {"host": "redis", "port": 6379}}'
      - --log-json
    deploy:
      replicas: 5
    depends_on:
      - redis
```

## Heartbeat and Requeueing

### Worker Heartbeats

Workers send heartbeats to indicate they're alive. Tasks are automatically requeued if a worker times out.

**Configuration:**
```json
{
  "backend": "redis",
  "heartbeat_timeout": 30,
  "circuit_breaker_threshold": 3,
  "heartbeat_check_interval": 5.0
}
```

**Options:**
- `heartbeat_timeout` (float): Worker heartbeat timeout in seconds. Default: `30`
- `circuit_breaker_threshold` (int): Failed heartbeats before marking worker dead. Default: `3`
- `heartbeat_check_interval` (float): Interval between heartbeat checks. Default: `5.0`

### Task Requeueing

Tasks are automatically requeued if:
1. Worker heartbeat times out
2. Task lease expires
3. Worker crashes

**Requeue Limits:**
```json
{
  "backend": "redis",
  "enable_requeue": true,
  "max_requeue_attempts": 3
}
```

**Options:**
- `enable_requeue` (bool): Enable automatic requeuing. Default: `true`
- `max_requeue_attempts` (int): Maximum requeue attempts per task. Default: `3`

## Batching

### Adaptive Batching

Automatically adjust batch size based on queue depth and worker throughput.

**Configuration:**
```json
{
  "backend": "redis",
  "adaptive_batching": true,
  "initial_batch_size": 10,
  "max_batch_size": 100,
  "min_batch_size": 1
}
```

**Options:**
- `adaptive_batching` (bool): Enable adaptive batching. Default: `false`
- `initial_batch_size` (int): Initial batch size. Default: `10`
- `max_batch_size` (int): Maximum batch size. Default: `100`
- `min_batch_size` (int): Minimum batch size. Default: `1`

### Fixed Batching

Use fixed batch size for predictable throughput.

**Configuration:**
```json
{
  "backend": "redis",
  "adaptive_batching": false,
  "batch_size": 50
}
```

## Configuration Examples

### Development (Memory)

```toml
[dispatcher]
type = "queue"

[queue]
config = '''
{
  "backend": "memory",
  "spawn_local_workers": true
}
'''
```

### Production (Redis)

```toml
[dispatcher]
type = "queue"

[queue]
config = '''
{
  "backend": "redis",
  "connection": {
    "host": "redis.example.com",
    "port": 6379,
    "password": "${REDIS_PASSWORD}"
  },
  "lease_seconds": 60,
  "heartbeat_timeout": 30,
  "compress": true,
  "adaptive_batching": true,
  "initial_batch_size": 10,
  "max_batch_size": 100
}
'''
```

### AWS (SQS)

```toml
[dispatcher]
type = "queue"

[queue]
config = '''
{
  "backend": "sqs",
  "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/metamorphic-guard-tasks",
  "region": "us-east-1",
  "max_batch_size": 10,
  "visibility_timeout": 60
}
'''
```

### High Throughput (Kafka)

```toml
[dispatcher]
type = "queue"

[queue]
config = '''
{
  "backend": "kafka",
  "bootstrap_servers": "kafka-1:9092,kafka-2:9092,kafka-3:9092",
  "topic": "metamorphic_guard_tasks",
  "consumer_group": "metamorphic_guard_workers",
  "max_batch_size": 1000
}
'''
```

## Monitoring

### Queue Metrics

Monitor queue health with Prometheus metrics:

```promql
# Pending tasks
metamorphic_queue_pending_tasks

# In-flight cases
metamorphic_queue_inflight_cases

# Active workers
metamorphic_queue_active_workers

# Dispatch rate
rate(metamorphic_queue_cases_dispatched_total[5m])

# Completion rate
rate(metamorphic_queue_cases_completed_total[5m])

# Requeue rate (health indicator)
rate(metamorphic_queue_cases_requeued_total[5m])
```

### Logging

Enable structured logging for queue operations:

```bash
# Coordinator
metamorphic-guard evaluate \
    --dispatcher queue \
    --log-json

# Worker
metamorphic-guard worker \
    --backend redis \
    --log-json
```

Log events include:
- `queue_dispatched`: Task dispatched to queue
- `queue_completed`: Task completed by worker
- `queue_requeued`: Task requeued due to timeout
- `heartbeat_timeout`: Worker heartbeat timeout

## Best Practices

### 1. Choose Appropriate Backend

- **Development**: Use `memory` backend
- **Small scale (< 10k cases)**: Use `redis`
- **AWS deployments**: Use `sqs`
- **High throughput (> 100k cases)**: Use `kafka`

### 2. Configure Heartbeats

Set heartbeat timeout based on task duration:

```json
{
  "heartbeat_timeout": 60,  // 2x average task duration
  "heartbeat_check_interval": 10.0
}
```

### 3. Enable Compression

Compress task payloads to reduce queue size:

```json
{
  "compress": true
}
```

### 4. Use Adaptive Batching

Enable adaptive batching for optimal throughput:

```json
{
  "adaptive_batching": true,
  "initial_batch_size": 10,
  "max_batch_size": 100
}
```

### 5. Monitor Queue Depth

Set up alerts for high queue depth:

```promql
# Alert if queue depth > 1000
metamorphic_queue_pending_tasks > 1000
```

### 6. Scale Workers Dynamically

Scale workers based on queue depth:

```bash
# Scale up if queue depth > 500
if [ $(redis-cli LLEN metamorphic_guard:tasks) -gt 500 ]; then
  kubectl scale deployment metamorphic-guard-worker --replicas=20
fi
```

### 7. Handle Failures Gracefully

Configure requeue limits to prevent infinite loops:

```json
{
  "enable_requeue": true,
  "max_requeue_attempts": 3
}
```

## Troubleshooting

### Workers Not Processing Tasks

1. **Check queue connection:**
   ```bash
   # Redis
   redis-cli PING
   
   # SQS
   aws sqs get-queue-attributes --queue-url <queue-url>
   ```

2. **Check worker logs:**
   ```bash
   tail -f logs/worker.jsonl | jq 'select(.event == "queue_consumed")'
   ```

3. **Verify worker registration:**
   ```bash
   # Redis
   redis-cli KEYS "metamorphic_guard:workers:*"
   ```

### High Requeue Rate

High requeue rate indicates worker health issues:

1. **Check worker heartbeats:**
   ```bash
   # Redis
   redis-cli HGETALL "metamorphic_guard:heartbeats"
   ```

2. **Increase heartbeat timeout:**
   ```json
   {
     "heartbeat_timeout": 120  // Increase if tasks take longer
   }
   ```

3. **Check worker resources:**
   ```bash
   # Kubernetes
   kubectl top pods -l app=metamorphic-guard-worker
   ```

### Queue Backlog

If queue depth grows continuously:

1. **Scale up workers:**
   ```bash
   kubectl scale deployment metamorphic-guard-worker --replicas=50
   ```

2. **Check task processing rate:**
   ```promql
   rate(metamorphic_queue_cases_completed_total[5m])
   ```

3. **Optimize task duration:**
   - Reduce timeout limits
   - Optimize implementation code
   - Use faster executors

## See Also

- [Structured Logging Guide](logging.md) - Queue operation logging
- [Prometheus Metrics Guide](prometheus.md) - Queue metrics monitoring
- [Deployment Guide](deployment.md) - Production deployment considerations


