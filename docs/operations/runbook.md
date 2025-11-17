# Operational Runbook

Comprehensive operational guide for Metamorphic Guard in production environments.

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Common Issues](#common-issues)
3. [Emergency Procedures](#emergency-procedures)
4. [Maintenance Tasks](#maintenance-tasks)
5. [Performance Tuning](#performance-tuning)
6. [Monitoring & Alerting](#monitoring--alerting)

## Quick Reference

### Key Commands

```bash
# Check system status
curl http://localhost:9090/metrics | grep metamorphic

# View logs
tail -f logs/metamorphic-guard.jsonl | jq

# Check queue health
redis-cli LLEN metamorphic_guard:tasks
redis-cli HGETALL metamorphic_guard:workers

# Restart workers
kubectl rollout restart deployment/metamorphic-guard-worker

# Scale workers
kubectl scale deployment/metamorphic-guard-worker --replicas=20
```

### Key Metrics

- `metamorphic_queue_pending_tasks`: Should be low (< 100)
- `metamorphic_queue_active_workers`: Should match expected worker count
- `metamorphic_queue_cases_requeued_total`: Should be low (indicates worker health)
- `metamorphic_cases_total{status="failure"}`: Monitor failure rate

## Common Issues

### Issue: Workers Not Processing Tasks

**Symptoms:**
- `metamorphic_queue_pending_tasks` increasing
- `metamorphic_queue_cases_completed_total` not increasing
- High queue depth

**Diagnosis:**
```bash
# Check worker count
redis-cli HGETALL metamorphic_guard:workers

# Check worker logs
kubectl logs -l app=metamorphic-guard-worker --tail=100

# Check queue connection
redis-cli PING
```

**Resolution:**
1. Verify queue backend is accessible
2. Check worker logs for connection errors
3. Verify worker registration in queue
4. Restart workers if necessary:
   ```bash
   kubectl rollout restart deployment/metamorphic-guard-worker
   ```

### Issue: High Requeue Rate

**Symptoms:**
- `metamorphic_queue_cases_requeued_total` increasing rapidly
- Tasks timing out before completion

**Diagnosis:**
```bash
# Check worker heartbeats
redis-cli HGETALL metamorphic_guard:heartbeats

# Check task duration vs timeout
# Review logs for timeout errors
tail -f logs/metamorphic-guard.jsonl | jq 'select(.event == "queue_timeout")'
```

**Resolution:**
1. **Increase heartbeat timeout** if tasks take longer:
   ```json
   {
     "heartbeat_timeout": 120  // Increase from default 30
   }
   ```
2. **Scale up workers** if overloaded
3. **Check worker resources** (CPU/memory limits)
4. **Optimize task duration** (reduce timeout limits, optimize code)

### Issue: Queue Backlog

**Symptoms:**
- `metamorphic_queue_pending_tasks` continuously increasing
- Completion rate slower than dispatch rate

**Diagnosis:**
```promql
# Check dispatch vs completion rates
rate(metamorphic_queue_cases_dispatched_total[5m])
rate(metamorphic_queue_cases_completed_total[5m])

# Check worker utilization
rate(metamorphic_queue_cases_completed_total[5m]) / 
metamorphic_queue_active_workers
```

**Resolution:**
1. **Scale up workers** immediately:
   ```bash
   kubectl scale deployment/metamorphic-guard-worker --replicas=50
   ```
2. **Check worker capacity** (may be resource-constrained)
3. **Enable adaptive batching** for better throughput
4. **Review task duration** (may need optimization)

### Issue: Worker Crashes

**Symptoms:**
- Worker count decreasing
- Tasks being requeued
- High error rate in worker logs

**Diagnosis:**
```bash
# Check worker status
kubectl get pods -l app=metamorphic-guard-worker

# Check crash logs
kubectl logs -l app=metamorphic-guard-worker --previous

# Check resource limits
kubectl describe pod -l app=metamorphic-guard-worker | grep -A 5 "Limits"
```

**Resolution:**
1. **Increase resource limits** if OOM killed:
   ```yaml
   resources:
     limits:
       memory: "4Gi"  # Increase from 2Gi
       cpu: "2000m"
   ```
2. **Reduce batch size** if memory constrained
3. **Check for memory leaks** in implementation code
4. **Add resource monitoring** for early detection

### Issue: Queue Connection Failures

**Symptoms:**
- Evaluation hangs or times out
- Connection errors in logs
- Workers unable to consume tasks

**Diagnosis:**
```bash
# Test queue connection
redis-cli -h redis.example.com -p 6379 PING

# Check network connectivity
ping redis.example.com

# Check DNS resolution
nslookup redis.example.com
```

**Resolution:**
1. **Verify queue backend is running**
2. **Check network connectivity** (firewalls, security groups)
3. **Verify credentials** (if using authentication)
4. **Check queue backend logs** for errors
5. **Enable retry logic** for transient failures

## Emergency Procedures

### Evaluation Stuck / Not Progressing

1. **Check queue status:**
   ```bash
   redis-cli LLEN metamorphic_guard:tasks
   redis-cli HGETALL metamorphic_guard:workers
   ```

2. **Check worker logs:**
   ```bash
   kubectl logs -l app=metamorphic-guard-worker --tail=50
   ```

3. **Restart workers** if necessary:
   ```bash
   kubectl rollout restart deployment/metamorphic-guard-worker
   ```

4. **Abort stuck evaluation** if needed (cleanup queue manually):
   ```bash
   # Clear queue (USE WITH CAUTION)
   redis-cli DEL metamorphic_guard:tasks
   ```

### High Failure Rate

1. **Check failure patterns:**
   ```promql
   sum(rate(metamorphic_cases_total{status="failure"}[5m])) by (role)
   ```

2. **Review error logs:**
   ```bash
   tail -f logs/metamorphic-guard.jsonl | jq 'select(.status == "failure")'
   ```

3. **Temporary mitigation:**
   - Reduce test case count
   - Increase timeout limits
   - Use more forgiving policy

4. **Root cause analysis:**
   - Check implementation code changes
   - Review test case generation
   - Check resource constraints

### Queue Backend Failure

1. **Switch to fallback backend:**
   - Update queue config to use memory backend (temporary)
   - Or switch to different queue backend (e.g., SQS if Redis fails)

2. **Recovery procedure:**
   ```bash
   # Restart queue backend
   kubectl rollout restart statefulset/redis

   # Verify connectivity
   redis-cli PING

   # Restart workers
   kubectl rollout restart deployment/metamorphic-guard-worker
   ```

3. **Data recovery:**
   - Tasks in-flight will be lost (expected)
   - Re-run evaluation after recovery

## Maintenance Tasks

### Regular Maintenance

**Weekly:**
- Review queue depth trends
- Check worker resource utilization
- Review error rates and patterns
- Update dependencies (via Dependabot PRs)

**Monthly:**
- Review and optimize queue configuration
- Performance benchmarking
- Capacity planning review
- Security audit (vulnerability scanning)

### Queue Cleanup

```bash
# Check queue size
redis-cli LLEN metamorphic_guard:tasks

# Clean up old worker heartbeats (if needed)
redis-cli DEL metamorphic_guard:workers

# Clean up completed result queues (job-specific)
redis-cli KEYS "metamorphic_guard:results:*"
# Delete old result queues manually if needed
```

### Performance Optimization

1. **Tune batch sizes:**
   ```json
   {
     "adaptive_batching": true,
     "initial_batch_size": 20,  // Increase for faster workers
     "max_batch_size": 200
   }
   ```

2. **Optimize heartbeat settings:**
   ```json
   {
     "heartbeat_timeout": 60,  // Match task duration
     "heartbeat_check_interval": 10.0
   }
   ```

3. **Enable compression:**
   ```json
   {
     "compress": true
   }
   ```

## Performance Tuning

### Queue Backend Selection

| Use Case | Backend | Reason |
|----------|---------|--------|
| Development | Memory | Fastest, no setup |
| < 10k cases | Redis | Balanced performance |
| AWS deployments | SQS | Managed service |
| > 100k cases | Kafka | Highest throughput |

### Worker Scaling

**Vertical Scaling:**
- Increase CPU/memory per worker
- Enable adaptive batching
- Increase batch sizes

**Horizontal Scaling:**
- Add more worker instances
- Use Kubernetes HPA (Horizontal Pod Autoscaler)
- Scale based on queue depth

### Resource Limits

**Recommended Limits:**
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "4000m"
```

Adjust based on:
- Average task duration
- Memory per task (`--mem-mb`)
- Concurrent workers per pod

## Monitoring & Alerting

### Critical Alerts

1. **No Active Workers:**
   ```promql
   metamorphic_queue_active_workers == 0
   ```
   - **Action**: Restart workers immediately

2. **High Requeue Rate:**
   ```promql
   rate(metamorphic_queue_cases_requeued_total[5m]) /
   rate(metamorphic_queue_cases_dispatched_total[5m]) > 0.2
   ```
   - **Action**: Check worker health, increase timeouts

3. **Queue Backlog:**
   ```promql
   metamorphic_queue_pending_tasks > 1000
   ```
   - **Action**: Scale up workers

### Warning Alerts

1. **High Failure Rate:**
   ```promql
   sum(rate(metamorphic_cases_total{status="failure"}[5m])) /
   sum(rate(metamorphic_cases_total[5m])) > 0.1
   ```
   - **Action**: Review error logs, check implementation

2. **Worker Resource Usage:**
   ```promql
   container_memory_usage_bytes{pod=~"metamorphic-guard-worker.*"} /
   container_spec_memory_limit_bytes > 0.8
   ```
   - **Action**: Increase memory limits or reduce batch size

### Dashboard Queries

**Queue Efficiency:**
```promql
sum(rate(metamorphic_queue_cases_completed_total[5m])) /
sum(rate(metamorphic_queue_cases_dispatched_total[5m]))
```

**Worker Utilization:**
```promql
sum(rate(metamorphic_queue_cases_completed_total[5m])) /
metamorphic_queue_active_workers
```

**Case Success Rate:**
```promql
sum(rate(metamorphic_cases_total{status="success"}[5m])) by (role) /
sum(rate(metamorphic_cases_total[5m])) by (role)
```

## Troubleshooting Guide

### Diagnostic Commands

```bash
# Check evaluation status
curl http://localhost:9090/metrics | grep metamorphic

# View recent errors
tail -f logs/metamorphic-guard.jsonl | jq 'select(.level == "ERROR")'

# Check queue depth
redis-cli LLEN metamorphic_guard:tasks

# Check worker heartbeats
redis-cli HGETALL metamorphic_guard:workers

# Monitor dispatch rate
watch -n 1 'redis-cli LLEN metamorphic_guard:tasks'
```

### Log Analysis

**Common log patterns:**
```bash
# Find timeout errors
jq 'select(.event == "queue_timeout")' logs/metamorphic-guard.jsonl

# Find requeue events
jq 'select(.event == "queue_requeued")' logs/metamorphic-guard.jsonl

# Find worker registration issues
jq 'select(.event == "worker_register_failed")' logs/metamorphic-guard.jsonl
```

## See Also

- [Queue Dispatch Guide](queue-dispatch.md) - Configuration and usage
- [Prometheus Metrics Guide](prometheus.md) - Monitoring setup
- [Deployment Guide](deployment.md) - Production deployment
- [Troubleshooting Guide](queue-dispatch.md#troubleshooting) - Common issues

