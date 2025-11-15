"""
Performance profiling for latency and cost analysis.
"""

from __future__ import annotations

import statistics
import threading
from typing import Any, Dict, List, Optional, Sequence

from .monitoring import Monitor, MonitorContext, MonitorRecord


class PerformanceProfiler(Monitor):
    """
    Comprehensive performance profiler tracking latency and cost metrics.
    
    Provides detailed statistics including percentiles, distributions, and
    comparative analysis between baseline and candidate implementations.
    """
    
    def __init__(
        self,
        percentiles: Optional[Sequence[float]] = None,
        enable_distribution: bool = True,
        enable_cost_profiling: bool = True,
    ) -> None:
        super().__init__()
        self.percentiles = percentiles or [0.5, 0.75, 0.90, 0.95, 0.99]
        self.enable_distribution = enable_distribution
        self.enable_cost_profiling = enable_cost_profiling
        self._lock = threading.Lock()
        
        # Latency tracking
        self._latencies: Dict[str, List[float]] = {"baseline": [], "candidate": []}
        
        # Cost tracking (for LLM evaluations)
        self._costs: Dict[str, List[float]] = {"baseline": [], "candidate": []}
        self._tokens: Dict[str, List[int]] = {"baseline": [], "candidate": []}
        
        # Success/failure tracking
        self._success_counts: Dict[str, int] = {"baseline": 0, "candidate": 0}
        self._failure_counts: Dict[str, int] = {"baseline": 0, "candidate": 0}
    
    def record(self, record: MonitorRecord) -> None:
        """Record a single execution result."""
        with self._lock:
            role = record.role
            duration = float(record.duration_ms or 0.0)
            
            # Track latency
            self._latencies[role].append(duration)
            
            # Track success/failure
            if record.success:
                self._success_counts[role] += 1
            else:
                self._failure_counts[role] += 1
            
            # Track cost and tokens if available
            if self.enable_cost_profiling:
                result = record.result
                if "cost_usd" in result:
                    try:
                        cost = float(result["cost_usd"])
                        self._costs[role].append(cost)
                    except (ValueError, TypeError):
                        pass
                
                if "tokens_total" in result:
                    try:
                        tokens = int(result["tokens_total"])
                        self._tokens[role].append(tokens)
                    except (ValueError, TypeError):
                        pass
    
    def finalize(self) -> Dict[str, Any]:
        """Generate comprehensive profiling report."""
        with self._lock:
            profile: Dict[str, Any] = {
                "id": self.identifier(),
                "type": "performance_profiler",
                "latency": self._profile_latency(),
                "success_rate": self._profile_success_rate(),
            }
            
            if self.enable_cost_profiling:
                profile["cost"] = self._profile_cost()
                profile["tokens"] = self._profile_tokens()
            
            if self.enable_distribution:
                profile["distribution"] = self._profile_distribution()
            
            profile["comparison"] = self._profile_comparison()
            profile["alerts"] = self._generate_alerts(profile)
            
            return profile
    
    def _profile_latency(self) -> Dict[str, Any]:
        """Generate latency profiling statistics."""
        latency_profile: Dict[str, Any] = {}
        
        for role in ["baseline", "candidate"]:
            values = self._latencies.get(role, [])
            if not values:
                latency_profile[role] = {
                    "count": 0,
                    "min_ms": None,
                    "max_ms": None,
                    "mean_ms": None,
                    "median_ms": None,
                    "stddev_ms": None,
                }
                continue
            
            sorted_values = sorted(values)
            latency_profile[role] = {
                "count": len(values),
                "min_ms": min(values),
                "max_ms": max(values),
                "mean_ms": statistics.mean(values),
                "median_ms": statistics.median(values),
                "stddev_ms": statistics.stdev(values) if len(values) > 1 else 0.0,
            }
            
            # Add percentiles
            percentile_values: Dict[str, float] = {}
            for p in self.percentiles:
                idx = max(0, min(len(sorted_values) - 1, int(p * len(sorted_values))))
                percentile_values[f"p{int(p * 100)}_ms"] = sorted_values[idx]
            latency_profile[role]["percentiles"] = percentile_values
        
        return latency_profile
    
    def _profile_success_rate(self) -> Dict[str, Any]:
        """Generate success rate statistics."""
        success_profile: Dict[str, Any] = {}
        
        for role in ["baseline", "candidate"]:
            successes = self._success_counts.get(role, 0)
            failures = self._failure_counts.get(role, 0)
            total = successes + failures
            
            if total == 0:
                success_profile[role] = {
                    "total": 0,
                    "successes": 0,
                    "failures": 0,
                    "success_rate": None,
                }
            else:
                success_profile[role] = {
                    "total": total,
                    "successes": successes,
                    "failures": failures,
                    "success_rate": successes / total,
                }
        
        return success_profile
    
    def _profile_cost(self) -> Dict[str, Any]:
        """Generate cost profiling statistics."""
        cost_profile: Dict[str, Any] = {}
        
        for role in ["baseline", "candidate"]:
            costs = self._costs.get(role, [])
            if not costs:
                cost_profile[role] = {
                    "count": 0,
                    "total_usd": 0.0,
                    "mean_usd": None,
                    "min_usd": None,
                    "max_usd": None,
                }
                continue
            
            cost_profile[role] = {
                "count": len(costs),
                "total_usd": sum(costs),
                "mean_usd": statistics.mean(costs),
                "min_usd": min(costs),
                "max_usd": max(costs),
            }
            
            if len(costs) > 1:
                cost_profile[role]["stddev_usd"] = statistics.stdev(costs)
        
        return cost_profile
    
    def _profile_tokens(self) -> Dict[str, Any]:
        """Generate token usage profiling statistics."""
        token_profile: Dict[str, Any] = {}
        
        for role in ["baseline", "candidate"]:
            tokens = self._tokens.get(role, [])
            if not tokens:
                token_profile[role] = {
                    "count": 0,
                    "total": 0,
                    "mean": None,
                    "min": None,
                    "max": None,
                }
                continue
            
            token_profile[role] = {
                "count": len(tokens),
                "total": sum(tokens),
                "mean": statistics.mean(tokens),
                "min": min(tokens),
                "max": max(tokens),
            }
            
            if len(tokens) > 1:
                token_profile[role]["stddev"] = statistics.stdev(tokens)
        
        return token_profile
    
    def _profile_distribution(self) -> Dict[str, Any]:
        """Generate latency distribution buckets."""
        distribution: Dict[str, Any] = {}
        
        for role in ["baseline", "candidate"]:
            values = self._latencies.get(role, [])
            if not values:
                distribution[role] = {}
                continue
            
            # Create buckets: 0-50ms, 50-100ms, 100-200ms, 200-500ms, 500-1000ms, 1000ms+
            buckets = [0, 50, 100, 200, 500, 1000, float("inf")]
            bucket_counts: Dict[str, int] = {}
            
            for value in values:
                for i in range(len(buckets) - 1):
                    if buckets[i] <= value < buckets[i + 1]:
                        bucket_key = f"{buckets[i]}-{buckets[i+1] if buckets[i+1] != float('inf') else 'inf'}ms"
                        bucket_counts[bucket_key] = bucket_counts.get(bucket_key, 0) + 1
                        break
            
            distribution[role] = bucket_counts
        
        return distribution
    
    def _profile_comparison(self) -> Dict[str, Any]:
        """Generate comparative analysis between baseline and candidate."""
        comparison: Dict[str, Any] = {}
        
        baseline_latency = self._latencies.get("baseline", [])
        candidate_latency = self._latencies.get("candidate", [])
        
        if baseline_latency and candidate_latency:
            baseline_mean = statistics.mean(baseline_latency)
            candidate_mean = statistics.mean(candidate_latency)
            
            comparison["latency"] = {
                "baseline_mean_ms": baseline_mean,
                "candidate_mean_ms": candidate_mean,
                "delta_ms": candidate_mean - baseline_mean,
                "delta_percent": ((candidate_mean - baseline_mean) / baseline_mean * 100) if baseline_mean > 0 else 0.0,
            }
        
        baseline_cost = self._costs.get("baseline", [])
        candidate_cost = self._costs.get("candidate", [])
        
        if baseline_cost and candidate_cost:
            baseline_mean_cost = statistics.mean(baseline_cost)
            candidate_mean_cost = statistics.mean(candidate_cost)
            
            comparison["cost"] = {
                "baseline_mean_usd": baseline_mean_cost,
                "candidate_mean_usd": candidate_mean_cost,
                "delta_usd": candidate_mean_cost - baseline_mean_cost,
                "delta_percent": ((candidate_mean_cost - baseline_mean_cost) / baseline_mean_cost * 100) if baseline_mean_cost > 0 else 0.0,
            }
        
        baseline_success = self._success_counts.get("baseline", 0)
        candidate_success = self._success_counts.get("candidate", 0)
        baseline_total = baseline_success + self._failure_counts.get("baseline", 0)
        candidate_total = candidate_success + self._failure_counts.get("candidate", 0)
        
        if baseline_total > 0 and candidate_total > 0:
            baseline_rate = baseline_success / baseline_total
            candidate_rate = candidate_success / candidate_total
            
            comparison["success_rate"] = {
                "baseline": baseline_rate,
                "candidate": candidate_rate,
                "delta": candidate_rate - baseline_rate,
                "delta_percent": ((candidate_rate - baseline_rate) / baseline_rate * 100) if baseline_rate > 0 else 0.0,
            }
        
        return comparison
    
    def _generate_alerts(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on performance regressions."""
        alerts: List[Dict[str, Any]] = []
        
        comparison = profile.get("comparison", {})
        
        # Latency regression alert
        latency_comp = comparison.get("latency", {})
        if latency_comp.get("delta_percent", 0) > 20:  # 20% slower
            alerts.append({
                "type": "latency_regression",
                "severity": "warning",
                "message": f"Candidate is {latency_comp['delta_percent']:.1f}% slower than baseline",
                "baseline_mean_ms": latency_comp.get("baseline_mean_ms"),
                "candidate_mean_ms": latency_comp.get("candidate_mean_ms"),
            })
        
        # Cost regression alert
        cost_comp = comparison.get("cost", {})
        if cost_comp.get("delta_percent", 0) > 20:  # 20% more expensive
            alerts.append({
                "type": "cost_regression",
                "severity": "warning",
                "message": f"Candidate is {cost_comp['delta_percent']:.1f}% more expensive than baseline",
                "baseline_mean_usd": cost_comp.get("baseline_mean_usd"),
                "candidate_mean_usd": cost_comp.get("candidate_mean_usd"),
            })
        
        # Success rate regression alert
        success_comp = comparison.get("success_rate", {})
        if success_comp.get("delta", 0) < -0.05:  # 5% lower success rate
            alerts.append({
                "type": "success_rate_regression",
                "severity": "error",
                "message": f"Candidate has {abs(success_comp['delta'] * 100):.1f}% lower success rate than baseline",
                "baseline": success_comp.get("baseline"),
                "candidate": success_comp.get("candidate"),
            })
        
        return alerts

