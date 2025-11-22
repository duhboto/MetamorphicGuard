#!/usr/bin/env python3
"""
Comprehensive demo script showing Metamorphic Guard features.

This script demonstrates:
1. Basic evaluation
2. Advanced features (monitors, policies)
3. Programmatic API usage
4. Result interpretation
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from metamorphic_guard import run, Implementation, EvaluationConfig
from comprehensive_demo.task_spec import create_recommendation_task


def main():
    """Run comprehensive demo evaluations."""
    
    print("=" * 60)
    print("Metamorphic Guard Comprehensive Demo")
    print("=" * 60)
    print()
    
    # Create task specification
    print("📋 Creating task specification...")
    task_spec = create_recommendation_task()
    print(f"   Task: {task_spec.name}")
    print(f"   Properties: {len(task_spec.properties)}")
    print(f"   Metamorphic Relations: {len(task_spec.relations)}")
    print()
    
    # Run 1: Basic evaluation (improved candidate)
    print("=" * 60)
    print("Evaluation 1: Improved Candidate (Should Pass)")
    print("=" * 60)
    print()
    
    result1 = run(
        task=task_spec,
        baseline=Implementation(path="implementations/baseline_recommender.py"),
        candidate=Implementation(path="implementations/candidate_improved.py"),
        config=EvaluationConfig(
            n=200,
            seed=42,
            min_delta=0.02,
            min_pass_rate=0.80,
        ),
    )
    
    print(f"Adopt?        {'✅ Yes' if result1.adopt else '❌ No'}")
    print(f"Reason        {result1.reason}")
    print(f"Δ Pass Rate   {result1.delta_pass_rate:.4f}")
    if result1.delta_ci:
        print(f"Δ 95% CI      [{result1.delta_ci[0]:.4f}, {result1.delta_ci[1]:.4f}]")
    print(f"Report        {result1.report_path}")
    print()
    
    # Run 2: Regression candidate (should fail)
    print("=" * 60)
    print("Evaluation 2: Regression Candidate (Should Fail)")
    print("=" * 60)
    print()
    
    result2 = run(
        task=task_spec,
        baseline=Implementation(path="implementations/baseline_recommender.py"),
        candidate=Implementation(path="implementations/candidate_regression.py"),
        config=EvaluationConfig(
            n=200,
            seed=42,
            min_delta=0.02,
            min_pass_rate=0.80,
        ),
    )
    
    print(f"Adopt?        {'✅ Yes' if result2.adopt else '❌ No'}")
    print(f"Reason        {result2.reason}")
    print(f"Δ Pass Rate   {result2.delta_pass_rate:.4f}")
    if result2.delta_ci:
        print(f"Δ 95% CI      [{result2.delta_ci[0]:.4f}, {result2.delta_ci[1]:.4f}]")
    print(f"Report        {result2.report_path}")
    print()
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print()
    print(f"✅ Improved candidate: {'PASSED' if result1.adopt else 'FAILED'}")
    print(f"❌ Regression candidate: {'PASSED' if result2.adopt else 'FAILED'}")
    print()
    print("Expected behavior:")
    print("  - Improved candidate should pass (better than baseline)")
    print("  - Regression candidate should fail (violates fairness)")
    print()
    print("Next steps:")
    print("  1. View HTML reports: open reports/*.html")
    print("  2. Try CLI: metamorphic-guard evaluate --config configs/basic.toml")
    print("  3. Read tutorial: TUTORIAL.md")
    print()


if __name__ == "__main__":
    main()







