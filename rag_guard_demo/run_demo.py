import sys
from pathlib import Path
# Ensure we can import metamorphic_guard
sys.path.append(str(Path(__file__).resolve().parent.parent))

from metamorphic_guard import run, EvaluationConfig, Implementation
# from metamorphic_guard.api import run, EvaluationConfig, Implementation
from rag_guard_demo.src.demo_task import task

def main():
    print("Running RAG Guard Demo...")
    print("Comparing a baseline RAG implementation (prone to hallucinations) against a candidate (strict citation).")
    
    result = run(
        task=task,
        baseline=Implementation(path="rag_guard_demo/src/baseline.py"),
        candidate=Implementation(path="rag_guard_demo/src/candidate.py"),
        config=EvaluationConfig(
            n=50,  # Small number for demo
            seed=42,
            min_delta=0.1, # Expect significant improvement
        )
    )
    
    # Save report manually since we are using the API
    report_dir = Path("rag_guard_demo/reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "rag_demo_report.json"
    result.to_json(str(report_path))
    
    print("\n" + "="*50)
    print(f"Decision: {'Adopt' if result.adopt else 'Reject'}")
    print(f"Reason: {result.reason}")
    print(f"Baseline Pass Rate: {result.report['baseline']['pass_rate']:.2f}")
    print(f"Candidate Pass Rate: {result.report['candidate']['pass_rate']:.2f}")
    print(f"Delta: {result.report['delta_pass_rate']:.2f}")
    print("="*50)
    print(f"\nFull report written to: {report_path}")

if __name__ == "__main__":
    main()
