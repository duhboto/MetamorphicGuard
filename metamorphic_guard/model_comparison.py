"""
Native model comparison support for LLM evaluations.

Provides streamlined APIs for comparing multiple LLM models with statistical
analysis and ranking.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, TypedDict

from .llm_harness import LLMHarness, LLMCaseInput
from .judges import Judge, LLMJudge
from .mutants import Mutant, PromptMutant
from .types import JSONDict, JSONValue


class ModelComparisonResult(TypedDict, total=False):
    """Result of a single model evaluation in a comparison."""

    model: str
    provider: str
    report: JSONDict
    pass_rate: float
    cost_usd: float
    avg_latency_ms: float
    violations: int
    rank: int


class ModelComparisonReport(TypedDict, total=False):
    """Complete comparison report across multiple models."""

    models: List[ModelComparisonResult]
    best_model: str
    ranking: List[str]
    pairwise_comparisons: JSONDict
    summary: JSONDict


def compare_models(
    models: Sequence[Dict[str, JSONValue]],
    case: LLMCaseInput,
    props: Optional[Sequence[Judge | LLMJudge]] = None,
    mrs: Optional[Sequence[Mutant | PromptMutant]] = None,
    n: int = 100,
    seed: int = 42,
    bootstrap: bool = True,
    rank_by: str = "pass_rate",
    **kwargs: JSONValue,
) -> ModelComparisonReport:
    """
    Compare multiple LLM models on the same test cases.

    Args:
        models: List of model configurations, each with:
            - "model": Model identifier (required)
            - "provider": Provider name (required, default: "openai")
            - "executor_config": Executor config dict (optional)
            - "max_tokens": Max tokens (optional)
            - "temperature": Temperature (optional)
        case: Test case input (same format as LLMHarness.run)
        props: List of judges for evaluation
        mrs: List of mutants to apply
        n: Number of test cases
        seed: Random seed
        bootstrap: Whether to compute bootstrap confidence intervals
        rank_by: Metric to rank by ("pass_rate", "cost_usd", "latency_ms", "combined")
        **kwargs: Additional arguments passed to LLMHarness.run

    Returns:
        ModelComparisonReport with results, ranking, and pairwise comparisons

    Example:
        from metamorphic_guard.model_comparison import compare_models
        from metamorphic_guard.judges.builtin import LengthJudge

        results = compare_models(
            models=[
                {"model": "gpt-3.5-turbo", "provider": "openai"},
                {"model": "gpt-4", "provider": "openai"},
                {"model": "claude-3-haiku", "provider": "anthropic"},
            ],
            case={"user": "Explain quantum computing"},
            props=[LengthJudge(min_chars=100)],
            n=50,
        )

        print(f"Best model: {results['best_model']}")
        print(f"Ranking: {results['ranking']}")
    """
    results: List[ModelComparisonResult] = []

    # Evaluate each model
    for model_config in models:
        model_name = model_config.get("model")
        if not model_name or not isinstance(model_name, str):
            raise ValueError(f"Each model config must have a 'model' string field, got: {model_config}")

        provider = model_config.get("provider", "openai")
        if not isinstance(provider, str):
            raise ValueError(f"'provider' must be a string, got: {provider}")

        executor_config = model_config.get("executor_config")
        if executor_config is not None and not isinstance(executor_config, dict):
            raise ValueError(f"'executor_config' must be a dict, got: {executor_config}")

        max_tokens = model_config.get("max_tokens")
        if max_tokens is not None and not isinstance(max_tokens, int):
            raise ValueError(f"'max_tokens' must be an int, got: {max_tokens}")

        temperature = model_config.get("temperature")
        if temperature is not None and not isinstance(temperature, (int, float)):
            raise ValueError(f"'temperature' must be a number, got: {temperature}")

        # Create harness for this model
        harness = LLMHarness(
            model=str(model_name),
            provider=str(provider),
            executor_config=executor_config if isinstance(executor_config, dict) else None,
            max_tokens=int(max_tokens) if max_tokens is not None else 512,
            temperature=float(temperature) if temperature is not None else 0.0,
            seed=seed,
        )

        # Run evaluation
        report = harness.run(
            case=case,
            props=props,
            mrs=mrs,
            n=n,
            seed=seed,
            bootstrap=bootstrap,
            **kwargs,
        )

        # Extract metrics
        baseline_results = report.get("baseline", {}).get("results", [])
        candidate_results = report.get("candidate", {}).get("results", [])

        baseline_pass_rate = report.get("baseline", {}).get("pass_rate", 0.0)
        candidate_pass_rate = report.get("candidate", {}).get("pass_rate", 0.0)

        # Use candidate pass rate (since baseline_model defaults to candidate)
        pass_rate = candidate_pass_rate

        # Extract cost
        llm_metrics = report.get("llm_metrics", {})
        cost_usd = llm_metrics.get("candidate_cost_usd", 0.0)
        if not isinstance(cost_usd, (int, float)):
            cost_usd = 0.0

        # Extract latency
        avg_latency_ms = llm_metrics.get("candidate_avg_latency_ms", 0.0)
        if not isinstance(avg_latency_ms, (int, float)):
            avg_latency_ms = 0.0

        # Count violations
        violations = sum(1 for r in candidate_results if not r.get("passed", False))

        results.append(
            ModelComparisonResult(
                model=str(model_name),
                provider=str(provider),
                report=report,
                pass_rate=float(pass_rate),
                cost_usd=float(cost_usd),
                avg_latency_ms=float(avg_latency_ms),
                violations=int(violations),
            )
        )

    # Rank models
    if rank_by == "pass_rate":
        sorted_results = sorted(results, key=lambda x: x["pass_rate"], reverse=True)
    elif rank_by == "cost_usd":
        sorted_results = sorted(results, key=lambda x: x["cost_usd"])
    elif rank_by == "latency_ms":
        sorted_results = sorted(results, key=lambda x: x["avg_latency_ms"])
    elif rank_by == "combined":
        # Combined score: pass_rate / (cost_usd + 1) / (latency_ms / 1000 + 1)
        def combined_score(r: ModelComparisonResult) -> float:
            cost_factor = r["cost_usd"] + 1.0
            latency_factor = (r["avg_latency_ms"] / 1000.0) + 1.0
            return r["pass_rate"] / (cost_factor * latency_factor)

        sorted_results = sorted(results, key=combined_score, reverse=True)
    else:
        raise ValueError(f"Invalid rank_by: {rank_by}. Must be 'pass_rate', 'cost_usd', 'latency_ms', or 'combined'")

    # Assign ranks
    for rank, result in enumerate(sorted_results, start=1):
        result["rank"] = rank

    # Reorder results by rank
    results = sorted_results

    # Generate pairwise comparisons
    pairwise: JSONDict = {}
    for i, r1 in enumerate(results):
        for j, r2 in enumerate(results):
            if i < j:
                pair_key = f"{r1['model']}_vs_{r2['model']}"
                pairwise[pair_key] = {
                    "model1": r1["model"],
                    "model2": r2["model"],
                    "pass_rate_diff": r1["pass_rate"] - r2["pass_rate"],
                    "cost_diff": r1["cost_usd"] - r2["cost_usd"],
                    "latency_diff": r1["avg_latency_ms"] - r2["avg_latency_ms"],
                }

    # Summary statistics
    summary: JSONDict = {
        "total_models": len(results),
        "best_pass_rate": results[0]["pass_rate"] if results else 0.0,
        "worst_pass_rate": results[-1]["pass_rate"] if results else 0.0,
        "avg_pass_rate": sum(r["pass_rate"] for r in results) / len(results) if results else 0.0,
        "total_cost": sum(r["cost_usd"] for r in results),
        "avg_cost": sum(r["cost_usd"] for r in results) / len(results) if results else 0.0,
        "avg_latency": sum(r["avg_latency_ms"] for r in results) / len(results) if results else 0.0,
    }

    return ModelComparisonReport(
        models=results,
        best_model=results[0]["model"] if results else "",
        ranking=[r["model"] for r in results],
        pairwise_comparisons=pairwise,
        summary=summary,
    )


def compare_with_baseline(
    baseline_model: str,
    candidate_models: Sequence[str],
    case: LLMCaseInput,
    baseline_provider: str = "openai",
    candidate_provider: Optional[str] = None,
    props: Optional[Sequence[Judge | LLMJudge]] = None,
    mrs: Optional[Sequence[Mutant | PromptMutant]] = None,
    n: int = 100,
    seed: int = 42,
    bootstrap: bool = True,
    **kwargs: JSONValue,
) -> ModelComparisonReport:
    """
    Compare multiple candidate models against a single baseline.

    Args:
        baseline_model: Baseline model identifier
        candidate_models: List of candidate model identifiers
        case: Test case input
        baseline_provider: Provider for baseline (default: "openai")
        candidate_provider: Provider for candidates (defaults to baseline_provider)
        props: List of judges
        mrs: List of mutants
        n: Number of test cases
        seed: Random seed
        bootstrap: Whether to compute bootstrap confidence intervals
        **kwargs: Additional arguments

    Returns:
        ModelComparisonReport with baseline and candidates
    """
    if candidate_provider is None:
        candidate_provider = baseline_provider

    # Build model configs
    models: List[Dict[str, JSONValue]] = [
        {"model": baseline_model, "provider": baseline_provider},
    ]
    for candidate in candidate_models:
        models.append({"model": candidate, "provider": candidate_provider})

    return compare_models(
        models=models,
        case=case,
        props=props,
        mrs=mrs,
        n=n,
        seed=seed,
        bootstrap=bootstrap,
        **kwargs,
    )

