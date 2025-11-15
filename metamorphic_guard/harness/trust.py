"""
Trust score computation for RAG evaluations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Sequence, Tuple

from ..types import JSONDict

if TYPE_CHECKING:
    from ..specs import Spec


def compute_trust_scores(
    results: Sequence[JSONDict],
    test_inputs: Sequence[Tuple[object, ...]],
    spec: "Spec",
) -> Optional[JSONDict]:
    """
    Compute trust scores for RAG evaluations if applicable.
    
    Args:
        results: Evaluation results
        test_inputs: Test input tuples
        spec: Task specification
        
    Returns:
        Trust scores dictionary or None if not applicable
    """
    try:
        from ..rag_guards import assess
        
        # Check if this looks like a RAG evaluation
        # RAG evaluations typically have prompts and sources in inputs
        trust_scores_list = []
        
        for result, args in zip(results, test_inputs):
            if not result.get("success"):
                continue
                
            output = result.get("result", "")
            if not isinstance(output, str):
                continue
                
            # Try to extract question and sources from inputs
            # For LLM evaluations, args might be (prompt, system_prompt) or similar
            if len(args) >= 1:
                question = str(args[0]) if args[0] else ""
                sources = []
                
                # Try to find sources in remaining args or in the result metadata
                if len(args) > 1:
                    for arg in args[1:]:
                        if isinstance(arg, str) and len(arg) > 50:
                            sources.append(arg)
                        elif isinstance(arg, (list, tuple)):
                            sources.extend([str(s) for s in arg if isinstance(s, str)])
                
                # If we have question and output, compute trust score
                if question and output:
                    try:
                        trust_result = assess(question=question, answer=output, sources=sources)
                        if trust_result:
                            trust_scores_list.append(trust_result)
                    except Exception:
                        # RAG assessment failed, skip this case
                        continue
        
        if not trust_scores_list:
            return None
        
        # Aggregate trust scores
        total = len(trust_scores_list)
        if total == 0:
            return None
        
        avg_score = sum(t.get("score", 0.0) for t in trust_scores_list) / total
        all_flags: Dict[str, bool] = {}
        for trust_result in trust_scores_list:
            flags = trust_result.get("flags", {})
            for flag, value in flags.items():
                if flag not in all_flags:
                    all_flags[flag] = True
                all_flags[flag] = all_flags[flag] and value
        
        return {
            "score": avg_score,
            "count": total,
            "flags": all_flags,
        }
        
    except ImportError:
        # RAG guards not available
        return None
    except Exception:
        # Error computing trust scores
        return None

