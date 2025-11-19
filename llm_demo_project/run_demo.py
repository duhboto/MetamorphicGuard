import sys
import os
from pathlib import Path

# Add the project root and the demo project to sys.path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "llm_demo_project" / "src"))

from metamorphic_guard.harness import run_eval
from metamorphic_guard.util import write_report
from metamorphic_guard.gate import decide_adopt
from metamorphic_guard.monitoring import resolve_monitors
from mock_executor import MockLLMExecutor
from llm_task import llm_demo_spec

def main():
    print("🚀 Starting LLM Demo with Mock Executor...")
    
    # Register our task
    from metamorphic_guard.specs import _TASK_REGISTRY
    _TASK_REGISTRY["llm_demo"] = llm_demo_spec

    # Create dummy "files" for baseline/candidate to satisfy the file-based API if needed
    # But for LLM harness we usually pass prompts. 
    # Here run_eval expects paths. We'll use dummy paths that the MockExecutor reads as "System Prompts"
    
    baseline_path = Path("llm_demo_project/baseline_system_prompt.txt")
    candidate_path = Path("llm_demo_project/candidate_system_prompt.txt")
    
    baseline_path.write_text("You are a helpful assistant. Be verbose.", encoding="utf-8")
    candidate_path.write_text("You are a helpful assistant. Be concise.", encoding="utf-8")

    # Determine executor based on API keys
    executor = "mock_executor:MockLLMExecutor"
    executor_config = {"model": "mock-gpt-4", "latency_ms": 50}
    
    if os.environ.get("OPENAI_API_KEY"):
        print("🔑 Found OPENAI_API_KEY, using real OpenAI executor...")
        executor = "openai"
        executor_config = {"model": "gpt-3.5-turbo", "max_tokens": 250}
    elif os.environ.get("ANTHROPIC_API_KEY"):
        print("🔑 Found ANTHROPIC_API_KEY, using real Anthropic executor...")
        executor = "anthropic"
        executor_config = {"model": "claude-3-haiku-20240307", "max_tokens": 250}
    else:
        print("ℹ️  No API keys found, using Mock executor (simulated)...")

    try:
        # Resolve monitors
        monitors = resolve_monitors(["latency", "llm_cost"])

        result = run_eval(
            task_name="llm_demo",
            baseline_path=str(baseline_path),
            candidate_path=str(candidate_path),
            n=20,
            seed=42,
            executor=executor,
            executor_config=executor_config,
            min_delta=0.0, # We just want to see it run
            monitors=monitors
        )
        
        decision = decide_adopt(result, min_delta=0.01, min_pass_rate=0.8)
        result["decision"] = decision
        
        report_path = write_report(result, directory=Path("llm_demo_project/reports"))
        
        print("\n✅ Evaluation Complete!")
        print(f"Report saved to: {report_path}")
        print("\nResults:")
        print(f"  Pass Rate Delta: {result['delta_pass_rate']:.4f}")
        print(f"  Decision: {'Adopt' if decision['adopt'] else 'Reject'} ({decision['reason']})")
        
        # Clean up
        baseline_path.unlink()
        candidate_path.unlink()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

