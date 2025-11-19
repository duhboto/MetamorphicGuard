import json
import random
from pathlib import Path
from typing import List, Dict, Any, Tuple

from metamorphic_guard.api import TaskSpec, Property, Metric, MetamorphicRelation
from metamorphic_guard.judges.rag_guards import CitationVerificationJudge, AttributionJudge
from metamorphic_guard.mutant_bank.rag_mutants import ContextReorderMutant

# Load knowledge base
KB_PATH = Path(__file__).parent.parent / "knowledge_base.json"
with open(KB_PATH) as f:
    KB = json.load(f)

def gen_inputs(n: int, seed: int) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Generate (query, context) pairs."""
    rng = random.Random(seed)
    inputs = []
    
    queries = [
        ("What is Metamorphic Guard?", ["1", "2"]),
        ("What does Ranking Guard do?", ["3"]),
        ("Explain Fairness Guard.", ["4"]),
        ("How does the LLM demo work?", ["5"]),
    ]

    for _ in range(n):
        q_template, relevant_ids = rng.choice(queries)
        
        # Retrieve relevant docs + some noise
        docs = [doc for doc in KB if doc['id'] in relevant_ids]
        noise = [doc for doc in KB if doc['id'] not in relevant_ids]
        
        # Add 1-2 noise docs
        if noise:
            docs.extend(rng.sample(noise, k=min(len(noise), 2)))
        
        # Shuffle docs to simulate retrieval variance
        rng.shuffle(docs)
        
        inputs.append((q_template, docs))
    
    return inputs

# Judges
citation_judge = CitationVerificationJudge(config={"strict_matching": True})
attribution_judge = AttributionJudge(config={"min_overlap_ratio": 0.1}) # Low threshold for demo

def check_citations(output: str, query: str, docs: List[Dict[str, Any]]) -> bool:
    sources = [d['content'] for d in docs]
    source_indices = [int(d['id']) for d in docs]
    res = citation_judge.evaluate(output, input_data={"sources": sources, "source_indices": source_indices})
    return res["pass"]

def check_attribution(output: str, query: str, docs: List[Dict[str, Any]]) -> bool:
    sources = [d['content'] for d in docs]
    res = attribution_judge.evaluate(output, input_data={"sources": sources})
    # Attribution judge returns pass=False if no attribution found
    # For the demo, let's say pass=True if the judge says so OR if the output is a valid refusal
    if "cannot answer" in output:
        return True
    return res["pass"]

# Mutants
context_reorder = ContextReorderMutant()

def apply_context_reorder(query: str, docs: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    shuffled_docs = docs.copy()
    random.shuffle(shuffled_docs)
    return (query, shuffled_docs)

# MR: Output should be consistent when context is reordered
# (Assuming the implementation handles re-indexing citations correctly)
# If the implementation relies on absolute positions for citations [1], [2], 
# reordering context SHOULD change the citations (e.g. [1] might become [2]).
# But the *semantic answer* should be the same.
# Our simple mock implementation returns fixed strings or relies on "Source [1]".
# If we shuffle, "Source [1]" becomes a different doc. 
# So the mock implementation `candidate_generate` uses `enumerate(docs)`.
# If we shuffle docs, the relevant doc might move from index 0 to index 1.
# The candidate will then output "... [2]".
# So exact string equality will fail.
# We need semantic equivalence or just check that it still passes properties.
# Let's use a property-based MR: "properties should still hold".
# Metamorphic Guard supports `expect="properties_hold"`.

task = TaskSpec(
    name="rag_guard_demo",
    gen_inputs=gen_inputs,
    properties=[
        Property(check=check_citations, description="Citations must be valid and present"),
        Property(check=check_attribution, description="Content must be attributed to sources"),
    ],
    relations=[
        MetamorphicRelation(
            name="context_reorder_robustness",
            transform=apply_context_reorder,
            expect="properties_hold", 
        )
    ],
    # Simple metrics
    metrics=[
        Metric(name="citation_count", extract=lambda out, *args: out.count("["), kind="mean"),
    ],
    equivalence=lambda a, b: a == b
)

