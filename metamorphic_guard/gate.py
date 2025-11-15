"""
Adoption gate logic for deciding whether to accept a candidate implementation.
"""

from typing import Any, Dict, Optional, TypedDict
import warnings

from .types import JSONDict, JSONValue


class AdoptionDecision(TypedDict, total=False):
    """Type for adoption decision result."""

    adopt: bool
    reason: str
    policy_checks: Dict[str, bool]


def decide_adopt(
    result: JSONDict,
    min_delta: float = 0.02,
    min_pass_rate: float = 0.80,
    policy: Optional[JSONDict] = None,
    **deprecated_kwargs: Any,
) -> AdoptionDecision:
    """
    Decide whether to adopt the candidate based on evaluation results.

    Args:
        result: Full evaluation result from harness
        min_delta: Minimum improvement threshold for CI lower bound
        min_pass_rate: Minimum pass rate required for candidate
        policy: Optional routing-aware policy with SLO constraints

    Returns:
        Dict with 'adopt' boolean and 'reason' string
    """
    if "improve_delta" in deprecated_kwargs:
        warnings.warn(
            "The 'improve_delta' argument is deprecated; use 'min_delta' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        min_delta = deprecated_kwargs.pop("improve_delta")
    if deprecated_kwargs:
        unexpected = ", ".join(sorted(deprecated_kwargs))
        raise TypeError(f"decide_adopt() got unexpected keyword arguments: {unexpected}")

    # If policy is provided, use routing-aware gate
    if policy:
        return _decide_adopt_with_policy(result, policy)

    # Standard gate logic
    candidate = result["candidate"]
    delta_ci = result.get("delta_ci", [0.0, 0.0])

    # Check for property violations
    if candidate.get("prop_violations"):
        return {
            "adopt": False,
            "reason": f"Property violations: {len(candidate['prop_violations'])} violations found",
        }

    # Check for metamorphic relation violations
    if candidate.get("mr_violations"):
        return {
            "adopt": False,
            "reason": f"Metamorphic relation violations: {len(candidate['mr_violations'])} violations found",
        }

    # Check minimum pass rate
    if candidate.get("pass_rate", 0.0) < min_pass_rate:
        return {
            "adopt": False,
            "reason": f"Pass rate too low: {candidate['pass_rate']:.3f} < {min_pass_rate}",
        }

    # Check improvement threshold
    if delta_ci[0] < min_delta:
        return {
            "adopt": False,
            "reason": f"Improvement insufficient: CI lower bound {delta_ci[0]:.3f} < {min_delta}",
        }

    # All conditions met
    return {"adopt": True, "reason": "meets_gate"}


def _decide_adopt_with_policy(result: JSONDict, policy: JSONDict) -> AdoptionDecision:
    """
    Routing-aware adoption gate that considers quality, cost, latency, and trust.

    Policy format:
    {
        "quality": {"min_delta": 0.0, "min_pass_rate": 0.80},
        "cost": {"max_ratio": 1.2, "max_delta_usd": None},
        "latency": {"max_ratio": 1.5, "max_delta_ms": None},
        "trust": {"min_score": 0.7, "required_flags": ["citation_correct"]},
    }

    Args:
        result: Full evaluation result
        policy: Policy dictionary with constraints

    Returns:
        Dict with 'adopt' boolean and 'reason' string
    """
    candidate = result["candidate"]
    baseline = result["baseline"]
    delta_ci = result.get("delta_ci", [0.0, 0.0])

    # Quality checks (standard gate)
    quality_policy = policy.get("quality", {})
    min_delta = quality_policy.get("min_delta", 0.0)
    min_pass_rate = quality_policy.get("min_pass_rate", 0.80)

    if candidate.get("prop_violations") or candidate.get("mr_violations"):
        return {
            "adopt": False,
            "reason": "Quality gate failed: violations detected",
        }

    if candidate.get("pass_rate", 0.0) < min_pass_rate:
        return {
            "adopt": False,
            "reason": f"Quality gate failed: pass rate {candidate['pass_rate']:.3f} < {min_pass_rate}",
        }

    if delta_ci[0] < min_delta:
        return {
            "adopt": False,
            "reason": f"Quality gate failed: delta CI lower bound {delta_ci[0]:.3f} < {min_delta}",
        }

    # Cost checks
    cost_policy = policy.get("cost", {})
    if cost_policy:
        llm_metrics = result.get("llm_metrics", {})
        candidate_cost = llm_metrics.get("candidate", {}).get("total_cost_usd", 0.0)
        baseline_cost = llm_metrics.get("baseline", {}).get("total_cost_usd", 0.0)

        if baseline_cost > 0:
            cost_ratio = candidate_cost / baseline_cost
            max_ratio = cost_policy.get("max_ratio")
            if max_ratio and cost_ratio > max_ratio:
                return {
                    "adopt": False,
                    "reason": f"Cost gate failed: ratio {cost_ratio:.2f} > {max_ratio}",
                }

        max_delta = cost_policy.get("max_delta_usd")
        if max_delta is not None:
            cost_delta = candidate_cost - baseline_cost
            if cost_delta > max_delta:
                return {
                    "adopt": False,
                    "reason": f"Cost gate failed: delta ${cost_delta:.4f} > ${max_delta:.4f}",
                }

    # Latency checks
    latency_policy = policy.get("latency", {})
    if latency_policy:
        llm_metrics = result.get("llm_metrics", {})
        candidate_latency = llm_metrics.get("candidate", {}).get("avg_latency_ms", 0.0)
        baseline_latency = llm_metrics.get("baseline", {}).get("avg_latency_ms", 0.0)

        if baseline_latency > 0:
            latency_ratio = candidate_latency / baseline_latency
            max_ratio = latency_policy.get("max_ratio")
            if max_ratio and latency_ratio > max_ratio:
                return {
                    "adopt": False,
                    "reason": f"Latency gate failed: ratio {latency_ratio:.2f} > {max_ratio}",
                }

        max_delta = latency_policy.get("max_delta_ms")
        if max_delta is not None:
            latency_delta = candidate_latency - baseline_latency
            if latency_delta > max_delta:
                return {
                    "adopt": False,
                    "reason": f"Latency gate failed: delta {latency_delta:.1f}ms > {max_delta:.1f}ms",
                }

    # Trust checks (for RAG)
    trust_policy = policy.get("trust", {})
    if trust_policy:
        trust_scores = result.get("trust_scores", {})
        candidate_trust = trust_scores.get("candidate", {}).get("score", 1.0)

        min_score = trust_policy.get("min_score", 0.7)
        if candidate_trust < min_score:
            return {
                "adopt": False,
                "reason": f"Trust gate failed: score {candidate_trust:.3f} < {min_score}",
            }

        required_flags = trust_policy.get("required_flags", [])
        if required_flags:
            candidate_flags = trust_scores.get("candidate", {}).get("flags", {})
            missing = [flag for flag in required_flags if not candidate_flags.get(flag, False)]
            if missing:
                return {
                    "adopt": False,
                    "reason": f"Trust gate failed: missing required flags: {missing}",
                }

    # All policy checks passed
    return {
        "adopt": True,
        "reason": "meets_policy_gate",
        "policy_checks": {
            "quality": True,
            "cost": bool(cost_policy),
            "latency": bool(latency_policy),
            "trust": bool(trust_policy),
        },
    }
