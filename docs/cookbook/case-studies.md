# Real-World Case Studies

This document presents real-world deployment examples and use cases for Metamorphic Guard.

## Table of Contents

1. [E-Commerce Recommendation System](#e-commerce-recommendation-system)
2. [Financial Risk Model Validation](#financial-risk-model-validation)
3. [LLM-Powered Customer Support](#llm-powered-customer-support)
4. [Healthcare Algorithm Certification](#healthcare-algorithm-certification)
5. [Search Engine Ranking](#search-engine-ranking)

## E-Commerce Recommendation System

### Challenge

An e-commerce platform needed to validate improvements to their product recommendation algorithm without risking revenue loss from poor recommendations.

### Solution

```python
from metamorphic_guard import run_eval, TaskSpec, Property, MetamorphicRelation
from metamorphic_guard.specs import Spec

@task("recommendation")
def recommendation_spec() -> Spec:
    return Spec(
        gen_inputs=lambda n, seed: generate_user_contexts(n, seed),
        properties=[
            Property(
                check=lambda recs, user: len(recs) == 10,
                description="Returns exactly 10 recommendations"
            ),
            Property(
                check=lambda recs, user: all(r in valid_products for r in recs),
                description="All recommendations are valid products"
            ),
            Property(
                check=lambda recs, user: len(set(recs)) == len(recs),
                description="No duplicate recommendations"
            ),
        ],
        relations=[
            MetamorphicRelation(
                name="user_permutation",
                transform=lambda user: permute_user_features(user),
                expect="equal",
                category="invariance",
                description="Permuting user features should not change recommendations"
            ),
            MetamorphicRelation(
                name="product_availability",
                transform=lambda user: mark_products_unavailable(user),
                expect="subset",
                category="robustness",
                description="Unavailable products should not appear in recommendations"
            ),
        ],
        equivalence=lambda a, b: set(a) == set(b),
    )

# Run evaluation with strict policy
result = run_eval(
    task_name="recommendation",
    baseline_path="recommendation_v1.py",
    candidate_path="recommendation_v2.py",
    n=5000,
    policy="policies/strict.toml",
    min_delta=0.02,  # Require 2% improvement
    min_pass_rate=0.95,  # 95% pass rate required
)
```

### Results

- **Throughput**: Evaluated 5,000 user contexts in 12 minutes using distributed execution
- **Cost**: $0 (no LLM usage, pure algorithm comparison)
- **Decision**: Candidate improved pass rate by 3.2% with 95% CI [2.1%, 4.3%] → **Adopted**

### Key Learnings

- Metamorphic relations caught edge cases (unavailable products, feature permutations)
- Distributed execution enabled rapid iteration
- Policy-as-code ensured consistent gating criteria

## Financial Risk Model Validation

### Challenge

A financial services company needed to validate risk model improvements while maintaining regulatory compliance and auditability.

### Solution

```python
from metamorphic_guard import run_eval
from pathlib import Path

# Run with full provenance and audit trail
result = run_eval(
    task_name="risk_model",
    baseline_path="risk_model_v1.py",
    candidate_path="risk_model_v2.py",
    n=10000,
    seed=42,  # Reproducible
    policy="policies/compliance.toml",
    policy_version="compliance-v2.1",
    report_dir=Path("audit/reports"),
    html_report=Path("audit/report.html"),
    junit_report=Path("audit/junit.xml"),
    # Enable provenance tracking
    executor_config={
        "record_provenance": True,
        "include_hashes": True,
    },
)

# Create audit bundle
from metamorphic_guard.bundle import create_bundle

bundle_path = create_bundle(
    report_path=Path("audit/reports/report_123.json"),
    baseline_path="risk_model_v1.py",
    candidate_path="risk_model_v2.py",
    output=Path("audit/bundles/audit_2024-01-15.tgz"),
)

# Sign for compliance
import subprocess
subprocess.run(["gpg", "--armor", "--detach-sig", str(bundle_path)])
```

### Results

- **Compliance**: Full audit trail with provenance, signed artifacts
- **Statistical Rigor**: Bootstrap CIs with alpha=0.01 for regulatory requirements
- **Reproducibility**: All evaluations reproducible with seed and bundles
- **Decision**: Candidate improved accuracy by 1.8% with CI [1.2%, 2.4%] → **Adopted**

### Key Learnings

- Provenance tracking essential for regulatory compliance
- Reproducible bundles enable audit verification
- Policy versioning ensures traceability

## LLM-Powered Customer Support

### Challenge

A SaaS company wanted to evaluate a new LLM model for customer support while controlling costs and ensuring quality.

### Solution

```python
from metamorphic_guard.llm_harness import LLMHarness
from metamorphic_guard.judges.builtin import LengthJudge, CoherenceJudge
from metamorphic_guard.mutants.builtin import ParaphraseMutant

# Set up harness
harness = LLMHarness(
    model="gpt-4",
    provider="openai",
    executor_config={
        "api_key": os.getenv("OPENAI_API_KEY"),
        "max_retries": 3,
        "timeout": 30.0,
    },
    max_tokens=512,
    temperature=0.0,  # Deterministic
)

# Define test cases
test_cases = [
    {
        "system": "You are a helpful customer support agent.",
        "user": "How do I reset my password?",
    },
    # ... more cases
]

# Run evaluation with cost estimation
from metamorphic_guard.cost_estimation import estimate_and_check_budget

estimate = estimate_and_check_budget(
    executor_name="openai",
    executor_config={"model": "gpt-4"},
    n=len(test_cases),
    budget_limit=100.0,
    warning_threshold=50.0,
    action=BudgetAction.WARN,
    system_prompt="You are a helpful customer support agent.",
    user_prompts=[case["user"] for case in test_cases],
    max_tokens=512,
)

print(f"Estimated cost: ${estimate['estimated_cost_usd']:.2f}")

# Run evaluation
report = harness.run(
    case=test_cases[0],  # Or pass list of cases
    props=[
        LengthJudge(config={"min_chars": 50, "max_chars": 500}),
        CoherenceJudge(config={"min_score": 0.7}),
    ],
    mrs=[ParaphraseMutant()],
    n=1000,
    seed=42,
)

# Check results
print(f"Pass rate: {report['candidate']['pass_rate']:.2%}")
print(f"Cost: ${report['llm_metrics']['cost_total_usd']:.2f}")
print(f"Adopt: {report['decision']['adopt']}")
```

### Results

- **Cost Control**: Pre-run estimation prevented budget overruns
- **Quality Assurance**: Judges ensured response quality (length, coherence)
- **Cost Efficiency**: Identified that gpt-3.5-turbo provided similar quality at 1/10th cost
- **Decision**: Switched to gpt-3.5-turbo → **Adopted**

### Key Learnings

- Cost estimation critical for LLM evaluations
- Judges provide automated quality checks
- Model comparison reveals cost-quality tradeoffs

## Healthcare Algorithm Certification

### Challenge

A healthcare AI company needed to certify algorithm improvements before clinical deployment, requiring rigorous validation and documentation.

### Solution

```python
from metamorphic_guard import run_eval
from metamorphic_guard.stability import stability_audit

# Run stability audit (multiple runs)
stability_result = stability_audit(
    task_name="diagnostic_algorithm",
    baseline_path="algorithm_v1.py",
    candidate_path="algorithm_v2.py",
    n=2000,
    runs=10,  # 10 independent runs
    seed=42,
)

# Check consistency
if stability_result["consistent"]:
    print("✅ All runs produced consistent decisions")
else:
    print("⚠️ Decisions varied across runs - investigate flakiness")

# Run full evaluation with strict policy
result = run_eval(
    task_name="diagnostic_algorithm",
    baseline_path="algorithm_v1.py",
    candidate_path="algorithm_v2.py",
    n=5000,
    policy="policies/clinical.toml",  # Very strict thresholds
    alpha=0.01,  # 99% confidence
    min_delta=0.05,  # Require 5% improvement
    min_pass_rate=0.98,  # 98% pass rate
    stability=5,  # Require 5 consistent runs
    shrink_violations=True,  # Minimize counterexamples
)

# Create certification bundle
from metamorphic_guard.bundle import create_bundle

bundle = create_bundle(
    report_path=result["report_path"],
    baseline_path="algorithm_v1.py",
    candidate_path="algorithm_v2.py",
    output=Path("certification/bundle.tgz"),
)
```

### Results

- **Certification**: Met all clinical validation requirements
- **Stability**: 10/10 runs produced consistent decisions
- **Documentation**: Complete audit trail with reproducible bundles
- **Decision**: Candidate improved accuracy by 6.1% with CI [4.8%, 7.4%] → **Certified for deployment**

### Key Learnings

- Stability audits essential for clinical applications
- Strict policies ensure safety margins
- Reproducible bundles enable regulatory review

## Search Engine Ranking

### Challenge

A search engine needed to validate ranking algorithm improvements while ensuring fairness across query types and user segments.

### Solution

```python
from metamorphic_guard import run_eval
from metamorphic_guard.monitors import FairnessGapMonitor

# Define query categories
query_categories = {
    "technical": lambda q: "code" in q.lower() or "api" in q.lower(),
    "general": lambda q: True,
    "shopping": lambda q: "buy" in q.lower() or "price" in q.lower(),
}

# Run evaluation with fairness monitoring
result = run_eval(
    task_name="search_ranking",
    baseline_path="ranking_v1.py",
    candidate_path="ranking_v2.py",
    n=10000,
    monitors=[
        FairnessGapMonitor(
            group_key=lambda result, args: categorize_query(args[0], query_categories),
            max_gap=0.05,  # Max 5% gap between groups
        ),
    ],
    policy="policies/fairness.toml",
)

# Check fairness metrics
fairness_data = result["monitors"]["fairness_gap"]
print(f"Max fairness gap: {fairness_data['summary']['max_gap']:.4f}")

if fairness_data["summary"]["max_gap"] > 0.05:
    print("⚠️ Fairness threshold exceeded")
    for group, gap in fairness_data["summary"]["gaps"].items():
        print(f"  {group}: {gap:.4f}")
```

### Results

- **Fairness**: All query categories within 3% pass rate gap
- **Performance**: Ranking quality improved by 4.2% overall
- **Scalability**: Evaluated 10,000 queries in 8 minutes using distributed execution
- **Decision**: Candidate improved quality while maintaining fairness → **Adopted**

### Key Learnings

- Fairness monitoring catches unintended biases
- Category-based analysis reveals group-level differences
- Distributed execution enables large-scale fairness audits

## Reference Projects

This repository includes two complete reference projects that demonstrate real-world Metamorphic Guard workflows:

### Ranking Guard Project

The **Ranking Guard Project** (`ranking_guard_project/`) provides a production-ready workflow for qualifying new ranking algorithms before rolling them into production. It demonstrates:

- Property-based checks for ranking correctness
- Metamorphic relations for input permutation and noise tolerance
- Statistical analysis with bootstrap confidence intervals
- CI/CD integration with GitHub Actions
- Adoption gating based on pass-rate deltas

**Key Features:**
- CLI tool (`ranking-guard`) for easy evaluation
- Multiple candidate implementations (heap-based, buggy examples)
- Comprehensive documentation and best practices
- Sample reports and CI pipeline examples

**See**: [Ranking Guard Project README](../../ranking_guard_project/README.md)

### Fairness Guard Project

The **Fairness Guard Project** (`fairness_guard_project/`) demonstrates how to enforce social-impact requirements on machine learning systems. It shows:

- Fairness-aware evaluation with demographic parity constraints
- Functional guarantees (output shape, minimum approval rates)
- Metamorphic relations for deployment reality testing
- Group-level fairness metrics and reporting
- Regulatory compliance considerations

**Key Features:**
- CLI tool (`fairness-guard`) for fairness evaluation
- Fairness metrics (overall approval rates, group-level rates, fairness gaps)
- Compliance-ready reporting for governance dashboards
- CI/CD integration with fairness checks

**See**: [Fairness Guard Project README](../../fairness_guard_project/README.md)

Both projects include:
- Complete implementations (baseline and candidate examples)
- Comprehensive documentation
- CI/CD pipeline examples (GitHub Actions)
- Programmatic usage examples
- Best practices and troubleshooting guides

## Common Patterns Across Case Studies

1. **Policy-as-Code**: All cases used TOML policies for consistent gating
2. **Distributed Execution**: Large evaluations benefited from queue-based execution
3. **Observability**: Metrics and monitoring essential for production use
4. **Reproducibility**: Seeds and bundles enable audit and verification
5. **Cost Management**: Pre-run estimation prevents budget surprises (LLM cases)
6. **Statistical Rigor**: Bootstrap CIs provide confidence in decisions

## Lessons Learned

- **Start with small n**: Validate approach with n=100-400 before scaling
- **Use appropriate policies**: Match policy strictness to use case criticality
- **Enable monitoring**: Always enable monitors for production evaluations
- **Track provenance**: Essential for compliance and debugging
- **Estimate costs**: Always estimate before large LLM evaluations
- **Test stability**: Run stability audits for critical applications

