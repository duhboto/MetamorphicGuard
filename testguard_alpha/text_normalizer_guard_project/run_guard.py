# run_guard.py

import os
from pathlib import Path
from metamorphic_guard.harness import run_eval
import spec  # Import to register the task

def main() -> None:
    # Get absolute paths to the implementation files
    project_dir = Path(__file__).parent
    baseline_path = str(project_dir / "implementations" / "baseline_normalizer.py")
    candidate_path = str(project_dir / "implementations" / "candidate_normalizer.py")
    
    result = run_eval(
        task_name="text_normalizer",
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        n=500,
        seed=123,
        min_delta=0.0,     # you can tighten this later
        min_pass_rate=0.95, # require pretty high property/MR pass rate
    )
    
    decision = result.get("decision", {})
    print("=" * 60)
    print("METAMORPHIC GUARD EVALUATION RESULTS")
    print("=" * 60)
    print(f"Adopt candidate: {decision.get('adopt', False)}")
    print(f"Reason: {decision.get('reason', 'N/A')}")
    print()
    
    baseline_stats = result.get("baseline", {})
    candidate_stats = result.get("candidate", {})
    print(f"Baseline: {baseline_stats.get('passes', 0)}/{baseline_stats.get('total', 0)} passed ({baseline_stats.get('pass_rate', 0)*100:.1f}%)")
    print(f"Candidate: {candidate_stats.get('passes', 0)}/{candidate_stats.get('total', 0)} passed ({candidate_stats.get('pass_rate', 0)*100:.1f}%)")
    print()
    
    print(f"Delta pass rate: {result.get('delta_pass_rate', 0):.4f}")
    delta_ci = result.get("delta_ci", [0, 0])
    print(f"Delta CI (95%): [{delta_ci[0]:.4f}, {delta_ci[1]:.4f}]")
    print()
    
    # Show relation results
    relation_coverage = result.get("relation_coverage", {})
    if relation_coverage:
        print("Metamorphic Relations:")
        for rel in relation_coverage.get("relations", []):
            name = rel.get("name", "unknown")
            baseline_pr = rel.get("baseline", {}).get("pass_rate", 0) * 100
            candidate_pr = rel.get("candidate", {}).get("pass_rate", 0) * 100
            baseline_failures = rel.get("baseline", {}).get("failures", 0)
            candidate_failures = rel.get("candidate", {}).get("failures", 0)
            status = "✓" if candidate_failures == 0 else "✗"
            print(f"  {status} {name}: baseline={baseline_pr:.1f}% ({baseline_failures} failures), candidate={candidate_pr:.1f}% ({candidate_failures} failures)")
        print()
    
    # Show property violations if any
    baseline_violations = baseline_stats.get("prop_violations", [])
    candidate_violations = candidate_stats.get("prop_violations", [])
    
    if candidate_violations:
        print(f"⚠️  Candidate Property Violations: {len(candidate_violations)}")
        # Show first few violations as examples
        for i, violation in enumerate(candidate_violations[:3]):
            case_idx = violation.get("case_index", "?")
            prop_desc = violation.get("property", "unknown")
            print(f"  Example {i+1}: Case #{case_idx} - {prop_desc}")
        if len(candidate_violations) > 3:
            print(f"  ... and {len(candidate_violations) - 3} more violations")
        print()
    
    if baseline_violations:
        print(f"⚠️  Baseline Property Violations: {len(baseline_violations)}")
        print()
    
    # Show MR violations if any
    baseline_mr_violations = baseline_stats.get("mr_violations", [])
    candidate_mr_violations = candidate_stats.get("mr_violations", [])
    
    if candidate_mr_violations:
        print(f"⚠️  Candidate MR Violations: {len(candidate_mr_violations)}")
        # Show first few violations as examples
        for i, violation in enumerate(candidate_mr_violations[:3]):
            case_idx = violation.get("case_index", "?")
            mr_name = violation.get("relation", "unknown")
            print(f"  Example {i+1}: Case #{case_idx} - {mr_name} relation failed")
        if len(candidate_mr_violations) > 3:
            print(f"  ... and {len(candidate_mr_violations) - 3} more violations")
        print()
    
    print("=" * 60)

if __name__ == "__main__":
    main()

