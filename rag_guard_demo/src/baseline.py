import random
from typing import List, Dict, Any

def solve(query: str, docs: List[Dict[str, Any]]) -> str:
    """
    Baseline implementation: Sometimes answers without citations, or hallucinates.
    """
    # Simulate hallucination or poor citation 30% of the time
    if random.random() < 0.3:
        return "Metamorphic Guard is a great tool for testing. It was built by Google." # Hallucination
    
    # Simulate missing citations
    if random.random() < 0.3:
        return "Metamorphic Guard uses metamorphic testing to compare program versions." # No citation

    # Correct behavior
    return "According to Source [1], Metamorphic Guard compares program versions using metamorphic testing."
