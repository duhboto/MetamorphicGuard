"""
Adoption gate logic for deciding whether to accept a candidate implementation.
"""

from typing import Dict, Any


def decide_adopt(
    result: Dict[str, Any], 
    improve_delta: float = 0.02, 
    min_pass_rate: float = 0.80
) -> Dict[str, Any]:
    """
    Decide whether to adopt the candidate based on evaluation results.
    
    Args:
        result: Full evaluation result from harness
        improve_delta: Minimum improvement threshold for CI lower bound
        min_pass_rate: Minimum pass rate required for candidate
        
    Returns:
        Dict with 'adopt' boolean and 'reason' string
    """
    candidate = result["candidate"]
    delta_ci = result["delta_ci"]
    
    # Check for property violations
    if candidate["prop_violations"]:
        return {
            "adopt": False,
            "reason": f"Property violations: {len(candidate['prop_violations'])} violations found"
        }
    
    # Check for metamorphic relation violations
    if candidate["mr_violations"]:
        return {
            "adopt": False,
            "reason": f"Metamorphic relation violations: {len(candidate['mr_violations'])} violations found"
        }
    
    # Check minimum pass rate
    if candidate["pass_rate"] < min_pass_rate:
        return {
            "adopt": False,
            "reason": f"Pass rate too low: {candidate['pass_rate']:.3f} < {min_pass_rate}"
        }
    
    # Check improvement threshold
    if delta_ci[0] < improve_delta:
        return {
            "adopt": False,
            "reason": f"Improvement insufficient: CI lower bound {delta_ci[0]:.3f} < {improve_delta}"
        }
    
    # All conditions met
    return {
        "adopt": True,
        "reason": "meets_gate"
    }
