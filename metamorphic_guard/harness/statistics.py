"""
Statistical functions for computing confidence intervals, power analysis, and related metrics.
"""

from __future__ import annotations

import math
import random
from statistics import NormalDist
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from scipy import stats
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

from ..power import calculate_power, calculate_sample_size


def estimate_power(
    p_baseline: float,
    p_candidate: float,
    sample_size: int,
    alpha_value: float,
    delta_value: float,
    power_target: float,
) -> Tuple[float, Optional[int]]:
    """
    Estimate statistical power and recommended sample size.
    
    This is a wrapper around the power module functions for consistency.
    """
    if sample_size == 0:
        return 0.0, None

    effect = p_candidate - p_baseline
    pooled_var = p_baseline * (1 - p_baseline) + p_candidate * (1 - p_candidate)
    if pooled_var == 0:
        power_val = 1.0 if effect >= delta_value else 0.0
        return power_val, None

    se = math.sqrt(pooled_var / sample_size)
    if se == 0:
        power_val = 1.0 if effect >= delta_value else 0.0
        return power_val, None

    z_alpha = NormalDist().inv_cdf(1 - alpha_value)
    z_effect = (effect - delta_value) / se
    power_val = 1 - NormalDist().cdf(z_alpha - z_effect)
    power_val = max(0.0, min(1.0, power_val))

    recommended_n = None
    if delta_value > 0 and 0 < power_target < 1:
        p1 = p_baseline
        p2 = max(0.0, min(1.0, p_baseline + delta_value))
        var_target = p1 * (1 - p1) + p2 * (1 - p2)
        if var_target > 0:
            z_beta = NormalDist().inv_cdf(power_target)
            recommended_n = math.ceil(((z_alpha + z_beta) ** 2 * var_target) / (delta_value ** 2))

    return power_val, recommended_n


def compute_delta_ci(
    baseline_metrics: Dict[str, Any],
    candidate_metrics: Dict[str, Any],
    *,
    alpha: float,
    seed: int,
    samples: int,
    method: str,
) -> List[float]:
    """Compute the pass-rate delta confidence interval using the requested method."""
    method = method.lower().replace("-", "_")
    clusters = baseline_metrics.get("cluster_labels")
    if method in {"bootstrap_cluster", "bootstrap_cluster_bca"}:
        return compute_bootstrap_ci(
            baseline_metrics["pass_indicators"],
            candidate_metrics["pass_indicators"],
            alpha=alpha,
            seed=seed,
            samples=samples,
            clusters=clusters,
            use_bca=method.endswith("bca"),
            observed_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
        )
    if method in {"bootstrap", "bootstrap_bca"}:
        return compute_bootstrap_ci(
            baseline_metrics["pass_indicators"],
            candidate_metrics["pass_indicators"],
            alpha=alpha,
            seed=seed,
            samples=samples,
            clusters=None,
            use_bca=method.endswith("bca"),
            observed_delta=candidate_metrics["pass_rate"] - baseline_metrics["pass_rate"],
        )
    if method in {"newcombe", "wilson"}:
        return compute_newcombe_ci(
            baseline_metrics["passes"],
            baseline_metrics["total"],
            candidate_metrics["passes"],
            candidate_metrics["total"],
            alpha=alpha,
        )
    if method == "bayesian":
        prior_type = "jeffreys"  # Default to Jeffreys prior
        return compute_bayesian_ci(
            baseline_metrics["passes"],
            baseline_metrics["total"],
            candidate_metrics["passes"],
            candidate_metrics["total"],
            alpha=alpha,
            prior_type=prior_type,
        )
    raise ValueError(f"Unsupported CI method: {method}")


def compute_bootstrap_ci(
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
    *,
    alpha: float,
    seed: int,
    samples: int,
    clusters: Optional[Sequence[Any]] = None,
    use_bca: bool = False,
    observed_delta: float | None = None,
) -> List[float]:
    """Compute a bootstrap confidence interval for the pass-rate delta."""
    n = len(baseline_indicators)
    if n == 0 or len(candidate_indicators) != n:
        return [0.0, 0.0]

    rng = random.Random(seed)
    deltas = generate_bootstrap_deltas(
        baseline_indicators,
        candidate_indicators,
        rng=rng,
        samples=samples,
        clusters=clusters,
    )

    if not deltas:
        return [0.0, 0.0]

    if use_bca:
        if observed_delta is None:
            observed_delta = (sum(candidate_indicators) / n) - (sum(baseline_indicators) / n)
        return compute_bca_interval(
            deltas,
            observed_delta=observed_delta,
            baseline_indicators=baseline_indicators,
            candidate_indicators=candidate_indicators,
            alpha=alpha,
            clusters=clusters,
        )

    lower_quantile = alpha / 2
    upper_quantile = 1 - alpha / 2
    ci_lower = percentile(deltas, lower_quantile)
    ci_upper = percentile(deltas, upper_quantile)
    return [float(ci_lower), float(ci_upper)]


def generate_bootstrap_deltas(
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
    *,
    rng: random.Random,
    samples: int,
    clusters: Optional[Sequence[Any]] = None,
) -> List[float]:
    """Generate bootstrap deltas (candidate - baseline pass rate)."""
    n = len(baseline_indicators)
    if n == 0 or len(candidate_indicators) != n:
        return []

    deltas: List[float] = []

    if clusters:
        cluster_indices: Dict[Any, List[int]] = {}
        for idx, cluster_id in enumerate(clusters):
            cluster_indices.setdefault(cluster_id, []).append(idx)
        unique_clusters = list(cluster_indices.keys())
        if unique_clusters:
            cluster_count = len(unique_clusters)
            for _ in range(max(1, samples)):
                sampled_clusters = [
                    unique_clusters[rng.randrange(cluster_count)]
                    for _ in range(cluster_count)
                ]
                baseline_sample: List[int] = []
                candidate_sample: List[int] = []
                for cluster_id in sampled_clusters:
                    indices = cluster_indices[cluster_id]
                    baseline_sample.extend(baseline_indicators[i] for i in indices)
                    candidate_sample.extend(candidate_indicators[i] for i in indices)
                if not baseline_sample or len(baseline_sample) != len(candidate_sample):
                    continue
                p_baseline = sum(baseline_sample) / len(baseline_sample)
                p_candidate = sum(candidate_sample) / len(candidate_sample)
                deltas.append(p_candidate - p_baseline)
            if deltas:
                return deltas
        # fallback to iid if clusters missing/empty

    for _ in range(max(1, samples)):
        indices = [rng.randrange(n) for _ in range(n)]
        baseline_sum = sum(baseline_indicators[i] for i in indices)
        candidate_sum = sum(candidate_indicators[i] for i in indices)
        deltas.append((candidate_sum - baseline_sum) / n)

    return deltas


def compute_bca_interval(
    deltas: Sequence[float],
    *,
    observed_delta: float,
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
    alpha: float,
    clusters: Optional[Sequence[Any]] = None,
) -> List[float]:
    """Compute the bias-corrected and accelerated (BCa) interval for bootstrap deltas."""
    if not deltas:
        return [0.0, 0.0]

    sorted_deltas = sorted(deltas)
    num_samples = len(sorted_deltas)
    # Bias correction
    proportion = sum(delta < observed_delta for delta in sorted_deltas) / num_samples
    if proportion <= 0.0:
        z0 = float("-inf")
    elif proportion >= 1.0:
        z0 = float("inf")
    else:
        z0 = NormalDist().inv_cdf(proportion)

    # Acceleration via jackknife
    n = len(baseline_indicators)
    total_baseline = sum(baseline_indicators)
    total_candidate = sum(candidate_indicators)

    jackknife: List[float] = []

    cluster_map: Dict[Any, List[int]] | None = None
    if clusters:
        cluster_map = {}
        for idx, cluster_id in enumerate(clusters):
            cluster_map.setdefault(cluster_id, []).append(idx)
        # Only keep clusters that have valid indices
        cluster_groups = [indices for indices in cluster_map.values() if indices]
        for indices in cluster_groups:
            denom = n - len(indices)
            if denom <= 0:
                continue
            baseline_loo_total = total_baseline - sum(baseline_indicators[i] for i in indices)
            candidate_loo_total = total_candidate - sum(candidate_indicators[i] for i in indices)
            p_b = baseline_loo_total / denom if denom else 0.0
            p_c = candidate_loo_total / denom if denom else 0.0
            jackknife.append(p_c - p_b)

    if not jackknife:
        if n <= 1:
            acceleration = 0.0
        else:
            for i in range(n):
                denom = n - 1
                if denom <= 0:
                    continue
                baseline_loo_total = total_baseline - baseline_indicators[i]
                candidate_loo_total = total_candidate - candidate_indicators[i]
                p_b = baseline_loo_total / denom if denom else 0.0
                p_c = candidate_loo_total / denom if denom else 0.0
                jackknife.append(p_c - p_b)

    if len(jackknife) < 2:
        acceleration = 0.0
    else:
        mean_jackknife = sum(jackknife) / len(jackknife)
        num = sum((mean_jackknife - jk) ** 3 for jk in jackknife)
        denom_sq = sum((mean_jackknife - jk) ** 2 for jk in jackknife)
        denom_pow = denom_sq ** 1.5 if denom_sq > 0 else 0.0
        if denom_pow == 0:
            acceleration = 0.0
        else:
            acceleration = num / (6.0 * denom_pow)

    def _adjusted_quantile(prob: float) -> float:
        if prob <= 0.0:
            return 0.0
        if prob >= 1.0:
            return 1.0
        if math.isinf(z0):
            return 0.0 if z0 < 0 else 1.0
        z_prob = NormalDist().inv_cdf(prob)
        denom = 1 - acceleration * (z0 + z_prob)
        if denom == 0:
            adjusted = 0.0 if z0 + z_prob < 0 else 1.0
        else:
            adjusted = NormalDist().cdf(z0 + (z0 + z_prob) / denom)
        return min(1.0, max(0.0, adjusted))

    lower_prob = _adjusted_quantile(alpha / 2)
    upper_prob = _adjusted_quantile(1 - alpha / 2)

    lower = percentile(sorted_deltas, lower_prob)
    upper = percentile(sorted_deltas, upper_prob)
    return [float(lower), float(upper)]


def compute_newcombe_ci(
    baseline_passes: int,
    baseline_total: int,
    candidate_passes: int,
    candidate_total: int,
    *,
    alpha: float,
) -> List[float]:
    """Compute the score CI for difference in proportions using Newcombe's method."""
    if baseline_total == 0 or candidate_total == 0:
        return [0.0, 0.0]

    lower_b, upper_b = wilson_interval(baseline_passes, baseline_total, alpha)
    lower_c, upper_c = wilson_interval(candidate_passes, candidate_total, alpha)

    delta_lower = lower_c - upper_b
    delta_upper = upper_c - lower_b
    return [float(delta_lower), float(delta_upper)]


def wilson_interval(successes: int, total: int, alpha: float) -> Tuple[float, float]:
    """Compute Wilson score interval for a proportion."""
    if total == 0:
        return (0.0, 0.0)

    z = NormalDist().inv_cdf(1 - alpha / 2)
    phat = successes / total
    denom = 1 + (z ** 2) / total
    center = phat + (z ** 2) / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + (z ** 2) / (4 * total)) / total)
    lower = (center - margin) / denom
    upper = (center + margin) / denom
    return (max(0.0, lower), min(1.0, upper))


def compute_relative_risk(
    baseline_metrics: Dict[str, Any],
    candidate_metrics: Dict[str, Any],
    *,
    alpha: float,
    method: str,
) -> Tuple[float, List[float]]:
    """Compute relative risk (candidate/baseline pass rate) with confidence interval."""
    p_b = baseline_metrics.get("pass_rate")
    if p_b is None:
        total_b = baseline_metrics.get("total", 0)
        p_b = baseline_metrics.get("passes", 0) / total_b if total_b else 0.0

    p_c = candidate_metrics.get("pass_rate")
    if p_c is None:
        total_c = candidate_metrics.get("total", 0)
        p_c = candidate_metrics.get("passes", 0) / total_c if total_c else 0.0

    if p_b == 0:
        return float("inf"), [float("inf"), float("inf")]

    rr = p_c / p_b
    method = method.lower()
    if method != "log":
        raise ValueError(f"Unsupported relative risk CI method: {method}")

    # Katz log method
    total_b = max(1, baseline_metrics.get("total", 0))
    total_c = max(1, candidate_metrics.get("total", 0))
    successes_b = max(1, baseline_metrics.get("passes", 0))
    successes_c = max(1, candidate_metrics.get("passes", 0))
    failures_b = max(1, total_b - successes_b)
    failures_c = max(1, total_c - successes_c)

    ln_rr = math.log(rr) if rr > 0 else float("-inf")
    se = math.sqrt((1 / successes_c) - (1 / total_c) +
                   (1 / successes_b) - (1 / total_b))
    z = NormalDist().inv_cdf(1 - alpha / 2)
    lower = math.exp(ln_rr - z * se)
    upper = math.exp(ln_rr + z * se)
    return rr, [float(lower), float(upper)]


def two_proportion_p_value(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
) -> float:
    """Two-sided z-test for difference in proportions."""
    if total_a <= 0 or total_b <= 0:
        return 1.0

    p_a = successes_a / total_a
    p_b = successes_b / total_b
    pooled_successes = successes_a + successes_b
    pooled_total = total_a + total_b
    if pooled_total <= 0:
        return 1.0

    pooled = pooled_successes / pooled_total
    variance = pooled * (1 - pooled) * (1 / total_a + 1 / total_b)
    if variance <= 0:
        return 1.0

    z = abs(p_a - p_b) / math.sqrt(variance)
    p_value = 2 * (1 - NormalDist().cdf(z))
    return max(0.0, min(1.0, float(p_value)))


def percentile(values: Sequence[float], q: float) -> float:
    """Compute the q-th percentile (0 <= q <= 1) using linear interpolation."""
    if not values:
        return 0.0
    if q <= 0:
        return float(min(values))
    if q >= 1:
        return float(max(values))

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    index = q * (n - 1)
    lower_idx = int(math.floor(index))
    upper_idx = min(lower_idx + 1, n - 1)
    weight = index - lower_idx
    return float(sorted_vals[lower_idx] * (1 - weight) + sorted_vals[upper_idx] * weight)


def compute_paired_stats(
    baseline_indicators: Sequence[int],
    candidate_indicators: Sequence[int],
) -> Optional[Dict[str, Any]]:
    """
    Compute paired statistics for baseline and candidate pass indicators.
    
    Args:
        baseline_indicators: Sequence of 0/1 indicators for baseline passes
        candidate_indicators: Sequence of 0/1 indicators for candidate passes
    
    Returns:
        Dictionary with paired statistics and McNemar test p-value, or None if invalid input.
    """
    if not baseline_indicators or not candidate_indicators:
        return None

    total = min(len(baseline_indicators), len(candidate_indicators))
    if total <= 0:
        return None

    both_pass = both_fail = baseline_only = candidate_only = 0
    baseline_sum = candidate_sum = 0

    for b, c in zip(baseline_indicators, candidate_indicators):
        if b:
            baseline_sum += 1
        if c:
            candidate_sum += 1

        if b and c:
            both_pass += 1
        elif b and not c:
            baseline_only += 1
        elif not b and c:
            candidate_only += 1
        else:
            both_fail += 1

    discordant = baseline_only + candidate_only
    delta = (candidate_sum - baseline_sum) / total

    if discordant == 0:
        chi2 = 0.0
        p_value = 1.0
    else:
        diff = abs(baseline_only - candidate_only)
        numerator = max(diff - 1.0, 0.0)
        chi2 = (numerator * numerator) / discordant
        p_value = math.erfc(math.sqrt(max(chi2, 0.0)) / math.sqrt(2.0))

    return {
        "total": total,
        "both_pass": both_pass,
        "both_fail": both_fail,
        "baseline_only": baseline_only,
        "candidate_only": candidate_only,
        "discordant": discordant,
        "delta": delta,
        "mcnemar_chi2": chi2,
        "mcnemar_p": p_value,
        "method": "mcnemar_cc",
    }


def compute_bayesian_ci(
    baseline_passes: int,
    baseline_total: int,
    candidate_passes: int,
    candidate_total: int,
    *,
    alpha: float,
    prior_type: str = "jeffreys",
) -> List[float]:
    """
    Compute Bayesian credible interval for pass-rate delta using Beta-Binomial model.
    
    Uses Beta prior for each pass rate, then computes posterior distribution
    of the difference (candidate - baseline).
    
    Args:
        baseline_passes: Number of baseline passes
        baseline_total: Total baseline tests
        candidate_passes: Number of candidate passes
        candidate_total: Total candidate tests
        alpha: Significance level (1 - alpha is the credible interval coverage)
        prior_type: Type of prior - "uniform" (Beta(1,1)), "jeffreys" (Beta(0.5,0.5)), 
                   or "beta" with custom parameters
    
    Returns:
        [lower_bound, upper_bound] credible interval for the delta
    """
    if not _SCIPY_AVAILABLE:
        raise ValueError(
            "Bayesian CI requires scipy. Install with: pip install scipy"
        )
    
    # Set prior parameters
    if prior_type == "uniform":
        alpha_prior = beta_prior = 1.0
    elif prior_type == "jeffreys":
        alpha_prior = beta_prior = 0.5
    elif prior_type.startswith("beta:"):
        # Custom prior: "beta:alpha,beta"
        parts = prior_type.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid prior_type format: {prior_type}")
        params = parts[1].split(",")
        if len(params) != 2:
            raise ValueError(f"Invalid prior_type format: {prior_type}")
        try:
            alpha_prior = float(params[0])
            beta_prior = float(params[1])
        except ValueError as e:
            raise ValueError(f"Invalid prior_type format: {prior_type}") from e
    else:
        raise ValueError(f"Unknown prior_type: {prior_type}. Use 'uniform', 'jeffreys', or 'beta:alpha,beta'")
    
    # Compute posterior parameters for baseline and candidate
    baseline_alpha_post = alpha_prior + baseline_passes
    baseline_beta_post = beta_prior + (baseline_total - baseline_passes)
    
    candidate_alpha_post = alpha_prior + candidate_passes
    candidate_beta_post = beta_prior + (candidate_total - candidate_passes)
    
    # For small samples, use analytical approximation
    # For larger samples, use Monte Carlo sampling
    if baseline_total < 50 or candidate_total < 50:
        # Use analytical method for small samples
        # Sample from posterior distributions and compute difference
        n_samples = 10000
        baseline_samples = stats.beta.rvs(
            baseline_alpha_post, 
            baseline_beta_post, 
            size=n_samples
        )
        candidate_samples = stats.beta.rvs(
            candidate_alpha_post, 
            candidate_beta_post, 
            size=n_samples
        )
        delta_samples = candidate_samples - baseline_samples
        delta_samples.sort()
        
        # Compute credible interval
        lower_idx = int(n_samples * (alpha / 2))
        upper_idx = int(n_samples * (1 - alpha / 2))
        ci_lower = float(delta_samples[lower_idx])
        ci_upper = float(delta_samples[upper_idx])
    else:
        # For larger samples, use normal approximation
        # Posterior mean and variance for each
        baseline_mean = baseline_alpha_post / (baseline_alpha_post + baseline_beta_post)
        baseline_var = (baseline_alpha_post * baseline_beta_post) / (
            (baseline_alpha_post + baseline_beta_post) ** 2 * 
            (baseline_alpha_post + baseline_beta_post + 1)
        )
        
        candidate_mean = candidate_alpha_post / (candidate_alpha_post + candidate_beta_post)
        candidate_var = (candidate_alpha_post * candidate_beta_post) / (
            (candidate_alpha_post + candidate_beta_post) ** 2 * 
            (candidate_alpha_post + candidate_beta_post + 1)
        )
        
        # Delta distribution (difference of two independent normals)
        delta_mean = candidate_mean - baseline_mean
        delta_std = math.sqrt(baseline_var + candidate_var)
        
        # Normal approximation for credible interval
        z_score = NormalDist().inv_cdf(1 - alpha / 2)
        ci_lower = delta_mean - z_score * delta_std
        ci_upper = delta_mean + z_score * delta_std
    
    return [ci_lower, ci_upper]

