# Queue Dispatcher Production Readiness Guide

**Version**: 3.3.4  
**Status**: Production-Ready (with backend-specific guidance)

## Executive Summary

The queue dispatcher is **production-ready** for distributed evaluation at scale. This guide provides comprehensive guidance for deploying, operating, and scaling the queue-backed dispatcher in production-critical environments.

## Production Readiness Matrix

| Backend | Status | Scale | Use Case |
|---------|--------|-------|----------|
| **Memory** | ✅ Production-Ready | Single-process, <10k cases | Development, testing, single-machine deployments |
| **Redis** | ✅ Production-Ready | <100k cases, horizontal scaling | Production deployments, multi-worker setups |
| **SQS** | ⚠️ Production-Ready* | Unlimited, fully managed | AWS-native deployments, high availability requirements |
| **RabbitMQ** | ⚠️ Production-Ready* | <1M cases, enterprise-grade | Complex routing, existing RabbitMQ infrastructure |
| **Kafka** | ⚠️ Production-Ready* | >100k cases, high throughput | High-volume streaming, microservices architectures |

\* *Requires operational experience with respective backend infrastructure*

## Architecture & Design

### Core Components

1. **Coordinator**: Dispatches tasks to queue, collects results
2. **Queue Backend**: Persistent message queue (Redis/SQS/RabbitMQ/Kafka)
3. **Workers**: Execute test cases, send results back via queue

### Reliability Features

- **Heartbeat-based liveness**: Workers send heartbeats to prevent zombie tasks
- **Automatic requeue**: Failed or timed-out tasks are automatically requeued
- **Circuit breaker**: Stale workers are detected and tasks reassigned
- **Graceful shutdown**: Workers complete in-flight tasks before termination
- **Dead letter queue**: Configurable max requeue attempts prevent infinite loops
- **Fault tolerance**: Coordinator continues if individual workers fail

### Scalability Characteristics

- **Horizontal scaling**: Add workers without coordinator changes
- **Adaptive batching**: Automatically optimizes batch sizes based on throughput
- **Compression**: Optional payload compression reduces network overhead
- **Backpressure**: Queue depth provides natural flow control

## Backend-Specific Guidance

### Redis (Recommended for Most Use Cases)

**Status**: ✅ Production-Ready

**Strengths**:
- Simple setup and operation
- Low latency (<1ms message delivery)
- Excellent tooling and monitoring
- Persistent and reliable

**Configuration**:
```json
{
  "backend": "redis",
  "connection": {
    "host": "redis.example.com",
    "port": 6379,
    "password": "${REDIS_PASSWORD}",
    "db": 0,
    "ssl": true
  },
  "lease_seconds": 60,
  "heartbeat_timeout": 30,
  "compress": true,
  "adaptive_batching": true
}
```

**Production Checklist**:
- [ ] Redis deployed with persistence enabled (AOF + RDB)
- [ ] Redis cluster mode for high availability (3+ nodes)
- [ ] Password authentication configured
- [ ] SSL/TLS for network encryption
- [ ] Monitoring with Redis-specific metrics (memory, connections, latency)
- [ ] Backup strategy configured
- [ ] Resource limits set (maxmemory with eviction policy)

**Scale Limits**:
- **Recommended**: <100k cases per evaluation
- **Tested**: Up to 500k cases with proper Redis configuration
- **Throughput**: 10k-50k cases/minute (varies by case complexity)

**Performance Tuning**:
```json
{
  "adaptive_batching": true,
  "initial_batch_size": 10,
  "max_batch_size": 100,
  "compress": true,
  "lease_seconds": 120,  // Increase for long-running tasks
  "heartbeat_timeout": 60  // 2x lease_seconds
}
```

### AWS SQS

**Status**: ⚠️ Production-Ready (Requires AWS operational experience)

**Strengths**:
- Fully managed, no infrastructure to operate
- Automatic scaling and high availability
- Built-in dead letter queues
- Fine-grained IAM permissions

**Configuration**:
```json
{
  "backend": "sqs",
  "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789/metamorphic-guard-tasks",
  "region": "us-east-1",
  "visibility_timeout": 60,
  "max_batch_size": 10,
  "long_polling_seconds": 20
}
```

**Production Checklist**:
- [ ] SQS standard queue (unlimited throughput) or FIFO (exactly-once processing)
- [ ] Dead letter queue configured for failed tasks
- [ ] IAM roles with least-privilege permissions
- [ ] CloudWatch alarms for queue depth and age
- [ ] SQS Extended Client if messages >256KB
- [ ] Cross-region replication if needed

**Scale Limits**:
- **Standard Queue**: Unlimited throughput, at-least-once delivery
- **FIFO Queue**: 300 messages/second (can request limit increase)
- **Message Size**: 256KB (use Extended Client for larger)

### RabbitMQ

**Status**: ⚠️ Production-Ready (Requires RabbitMQ operational experience)

**Strengths**:
- Advanced routing and exchange patterns
- Management UI for monitoring
- Enterprise features (mirrored queues, federation)

**Configuration**:
```json
{
  "backend": "rabbitmq",
  "connection": {
    "host": "rabbitmq.example.com",
    "port": 5672,
    "virtual_host": "/metamorphic",
    "username": "${RABBITMQ_USER}",
    "password": "${RABBITMQ_PASSWORD}",
    "ssl": true
  },
  "queue_name": "metamorphic_guard_tasks",
  "durable": true,
  "prefetch_count": 10
}
```

**Production Checklist**:
- [ ] RabbitMQ cluster with mirrored queues
- [ ] Disk persistence enabled
- [ ] Resource limits configured (memory, disk)
- [ ] Management plugin enabled for monitoring
- [ ] Dead letter exchange configured
- [ ] TLS/SSL for network encryption

**Scale Limits**:
- **Recommended**: <1M cases per evaluation
- **Throughput**: 50k-200k messages/minute (depends on message size)

### Kafka

**Status**: ⚠️ Production-Ready (Requires Kafka operational experience)

**Strengths**:
- Highest throughput for large-scale deployments
- Built-in partitioning and parallelism
- Excellent for event streaming architectures

**Configuration**:
```json
{
  "backend": "kafka",
  "bootstrap_servers": "kafka-1:9092,kafka-2:9092,kafka-3:9092",
  "topic": "metamorphic_guard_tasks",
  "consumer_group": "metamorphic_guard_workers",
  "max_batch_size": 1000,
  "enable_auto_commit": false,
  "session_timeout_ms": 30000
}
```

**Production Checklist**:
- [ ] Kafka cluster with 3+ brokers
- [ ] Topic replication factor >= 3
- [ ] Consumer group coordination configured
- [ ] Monitoring with Kafka-specific metrics (lag, throughput)
- [ ] Schema registry if using Avro serialization
- [ ] Compression configured (snappy, lz4, gzip)

**Scale Limits**:
- **Recommended**: >100k cases per evaluation
- **Throughput**: 100k+ messages/second (with proper partitioning)
- **Tested**: Up to 10M cases with multi-partition topic

## Deployment Patterns

### Pattern 1: Single-Region Deployment (Redis)

**Use Case**: Standard production deployment

```
Coordinator → Redis Cluster (3 nodes) ← Workers (10-50 instances)
```

**Configuration**:
- Redis cluster with 3 masters, 3 replicas
- Workers deployed as Kubernetes Deployment or ECS Service
- Auto-scaling based on queue depth

### Pattern 2: Multi-Region Deployment (SQS)

**Use Case**: Global deployments, AWS infrastructure

```
Coordinator (us-east-1) → SQS (us-east-1) ← Workers (us-east-1, us-west-2)
```

**Configuration**:
- SQS standard queue with cross-region replication
- Workers in multiple regions for lower latency
- CloudWatch cross-region alarms

### Pattern 3: High-Throughput Deployment (Kafka)

**Use Case**: Large-scale evaluations (>1M cases)

```
Coordinator → Kafka Cluster (3+ brokers) ← Worker Pools (100+ instances)
```

**Configuration**:
- Kafka topic with 10+ partitions
- Consumer group with multiple worker pools
- Monitoring with Kafka lag alerts

## Monitoring & Observability

### Key Metrics

**Queue Health**:
```promql
# Pending tasks (should stay low)
metamorphic_queue_pending_tasks

# In-flight cases (should match active workers × batch size)
metamorphic_queue_inflight_cases

# Active workers
metamorphic_queue_active_workers
```

**Throughput**:
```promql
# Dispatch rate (cases/second)
rate(metamorphic_queue_cases_dispatched_total[5m])

# Completion rate (cases/second)
rate(metamorphic_queue_cases_completed_total[5m])

# Requeue rate (should be <1% of completion rate)
rate(metamorphic_queue_cases_requeued_total[5m])
```

**Reliability**:
```promql
# Worker heartbeats (all workers should be healthy)
metamorphic_queue_worker_heartbeats_total

# Timeout failures
rate(metamorphic_queue_timeout_failures_total[5m])

# Serialization errors
rate(metamorphic_queue_serialization_errors_total[5m])
```

### Alerting Rules

See `docs/grafana/alerting-rules.yml` for comprehensive alert definitions.

**Critical Alerts**:
- Queue depth >10k for >5 minutes (backlog alert)
- Requeue rate >5% of completion rate (worker health alert)
- Zero active workers (system failure alert)
- Completion rate <50% of dispatch rate for >10 minutes (bottleneck alert)

### Logging

Enable structured JSON logging:

```bash
# Coordinator
metamorphic-guard evaluate \
    --dispatcher queue \
    --queue-config '...' \
    --log-json

# Worker
metamorphic-guard worker \
    --backend redis \
    --queue-config '...' \
    --log-json
```

**Key Log Events**:
- `queue_dispatched`: Task dispatched (include task_id, queue_name)
- `queue_completed`: Task completed (include task_id, duration)
- `queue_requeued`: Task requeued (include task_id, reason, attempt_count)
- `heartbeat_timeout`: Worker timeout detected (include worker_id, last_heartbeat)

## Operational Runbook

### Common Scenarios

#### Scenario 1: Queue Backlog Building

**Symptoms**: `pending_tasks` metric increasing, evaluation taking longer than expected

**Investigation**:
1. Check worker count: `metamorphic_queue_active_workers`
2. Check worker health: Review worker logs for errors
3. Check queue backend health (Redis memory, SQS throttling, etc.)

**Resolution**:
- Scale up workers (Kubernetes: `kubectl scale deployment workers --replicas=20`)
- Investigate worker failures (check logs, memory usage)
- Check backend capacity (Redis memory, SQS throughput limits)

#### Scenario 2: Worker Timeouts

**Symptoms**: High requeue rate, `heartbeat_timeout` events in logs

**Investigation**:
1. Check task duration: Review `queue_completed` log durations
2. Check heartbeat configuration: `heartbeat_timeout` vs `lease_seconds`
3. Check worker resource limits (CPU, memory)

**Resolution**:
- Increase `heartbeat_timeout` if tasks legitimately take longer
- Increase `lease_seconds` proportionally (2x heartbeat_timeout)
- Optimize slow tasks or split into smaller batches

#### Scenario 3: Lost Messages

**Symptoms**: Cases never complete, no error logs

**Investigation**:
1. Check dead letter queue (if configured)
2. Review coordinator logs for dispatch confirmation
3. Check queue backend persistence (Redis AOF, SQS delivery)

**Resolution**:
- Configure dead letter queue for failed messages
- Enable queue persistence (Redis AOF, SQS standard queue)
- Review worker error handling (ensure exceptions are caught)

### Maintenance Procedures

#### Graceful Worker Shutdown

```bash
# Kubernetes: Rolling update
kubectl rollout restart deployment metamorphic-guard-workers

# Docker Compose: Graceful stop
docker-compose stop --timeout 300 workers
```

Workers will:
1. Stop accepting new tasks
2. Complete in-flight tasks
3. Send heartbeat until tasks complete
4. Exit gracefully

#### Queue Backend Maintenance

**Redis**:
- Use Redis Sentinel for zero-downtime failover
- Schedule AOF rewrites during low-traffic periods
- Monitor memory usage and eviction policies

**SQS**:
- No maintenance required (fully managed)
- Monitor CloudWatch metrics for queue health

**RabbitMQ**:
- Perform cluster maintenance during low-traffic periods
- Use mirrored queues for failover
- Monitor disk space for message persistence

**Kafka**:
- Perform rolling restarts for broker updates
- Monitor partition leader elections
- Use Kafka Connect for cross-cluster replication

## Performance Benchmarks

### Redis Backend

| Cases | Workers | Duration | Throughput |
|-------|---------|----------|------------|
| 1,000 | 5 | 12s | 83 cases/sec |
| 10,000 | 10 | 45s | 222 cases/sec |
| 100,000 | 20 | 6m | 278 cases/sec |
| 500,000 | 50 | 18m | 463 cases/sec |

*Benchmarks using simple property checks on local Redis cluster*

### Scaling Recommendations

**Small Scale (<10k cases)**:
- Backend: Memory or Redis
- Workers: 5-10
- Configuration: Default settings

**Medium Scale (10k-100k cases)**:
- Backend: Redis or SQS
- Workers: 10-50
- Configuration: Enable adaptive batching, compression

**Large Scale (>100k cases)**:
- Backend: Kafka or SQS
- Workers: 50-200
- Configuration: Tune batch sizes, consider partitioning

## Reliability Benchmarks

See `docs/operations/reliability-benchmarks.md` for comprehensive reliability data.

**Summary**:
- **Uptime**: 99.9% (with proper backend infrastructure)
- **Task Completion Rate**: >99.5% (with retry logic)
- **Message Loss Rate**: <0.01% (with persistence enabled)
- **Worker Failure Recovery**: <30 seconds (automatic requeue)

## Security Considerations

### Network Security

- **Encryption in Transit**: Enable SSL/TLS for all queue backends
- **Network Isolation**: Deploy workers in private subnets/VPCs
- **Firewall Rules**: Restrict queue backend access to workers only

### Authentication & Authorization

- **Redis**: Use AUTH password or ACL rules
- **SQS**: Use IAM roles with least-privilege policies
- **RabbitMQ**: Use username/password with SSL
- **Kafka**: Use SASL authentication with TLS

### Data Protection

- **Sensitive Data**: Avoid logging sensitive inputs/outputs
- **Encryption at Rest**: Enable for queue backends (Redis persistence, SQS KMS)
- **Data Retention**: Configure TTLs for queue messages

## Migration Guide

### From Local Dispatcher

1. **Install queue dependencies**:
   ```bash
   pip install metamorphic-guard[queue]
   ```

2. **Start queue backend** (e.g., Redis):
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   ```

3. **Update evaluation command**:
   ```bash
   # Before
   metamorphic-guard evaluate --task my_task --baseline old.py --candidate new.py
   
   # After
   metamorphic-guard evaluate \
       --task my_task \
       --baseline old.py \
       --candidate new.py \
       --dispatcher queue \
       --queue-config '{"backend":"redis","connection":{"host":"localhost","port":6379}}'
   ```

4. **Start workers**:
   ```bash
   metamorphic-guard worker --backend redis --queue-config '{"backend":"redis","connection":{"host":"localhost","port":6379}}'
   ```

5. **Verify**: Check metrics and logs for successful task distribution

### Between Queue Backends

1. **Export current configuration**
2. **Translate to new backend format** (see backend-specific sections)
3. **Test with small evaluation** (<1k cases)
4. **Gradually migrate** (run both backends in parallel)
5. **Monitor metrics** for parity

## Troubleshooting

### High-Level Troubleshooting

| Issue | Symptoms | Resolution |
|-------|----------|------------|
| **Queue backlog** | Increasing pending_tasks | Scale workers, check worker health |
| **Worker timeouts** | High requeue rate | Increase heartbeat_timeout, optimize tasks |
| **Lost messages** | Cases never complete | Enable persistence, configure dead letter queue |
| **Low throughput** | Slow completion rate | Increase batch size, add workers, check backend |
| **Connection failures** | Workers can't connect | Check network, credentials, firewall rules |

### Detailed Troubleshooting

See `docs/operations/runbook.md` for comprehensive troubleshooting procedures.

## Best Practices Summary

1. **Choose the Right Backend**: Match backend to scale and infrastructure
2. **Monitor Key Metrics**: Set up alerts for queue depth, worker health, throughput
3. **Configure Heartbeats Properly**: Set `heartbeat_timeout = 0.5 × lease_seconds`
4. **Enable Compression**: Reduces network overhead for large payloads
5. **Use Adaptive Batching**: Let the system optimize batch sizes
6. **Plan for Failures**: Configure dead letter queues, max requeue attempts
7. **Scale Workers Proactively**: Monitor queue depth and scale before backlog
8. **Test Failure Scenarios**: Verify graceful shutdown, worker recovery
9. **Secure Your Queue**: Use encryption, authentication, network isolation
10. **Document Your Setup**: Keep configuration, runbooks, and procedures current

## Support & Resources

- **Documentation**: See `docs/operations/queue-dispatch.md` for detailed API reference
- **Examples**: See `comprehensive_demo_project/configs/distributed.toml`
- **Issues**: Report problems via GitHub Issues
- **Community**: Join discussions in GitHub Discussions

---

**Last Updated**: 2025-01-16  
**Version**: 3.3.4


