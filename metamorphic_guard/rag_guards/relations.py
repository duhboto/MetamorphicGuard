"""
Metamorphic relations for RAG systems.
"""

from typing import Any, List, Tuple, Optional
import random

def add_irrelevant_context(
    question: str, 
    context: str, 
    *, 
    rng: Optional[random.Random] = None
) -> Tuple[str, str]:
    """
    Inject irrelevant noise into the context.
    
    Expectation: Answer should remain semantically equivalent (Robustness).
    """
    if rng is None:
        rng = random.Random()
        
    # Simulating irrelevant noise (can be replaced with actual irrelevant document retrieval)
    noise_sentences = [
        "The sky is blue.",
        "Pizza is a popular dish.",
        "Python is a programming language.",
        "The quick brown fox jumps over the lazy dog.",
        "Metamorphic testing is effective.",
    ]
    
    noise = rng.choice(noise_sentences)
    
    # Insert noise at random position
    if not context:
        return question, noise
        
    # Simple split by newline or period
    parts = context.split("\n")
    insert_idx = rng.randint(0, len(parts))
    parts.insert(insert_idx, noise)
    
    new_context = "\n".join(parts)
    return question, new_context


def remove_relevant_context(
    question: str, 
    context: str, 
    *, 
    rng: Optional[random.Random] = None
) -> Tuple[str, str]:
    """
    Remove a significant portion of the context.
    
    Expectation: Answer should change or become 'I don't know' (Faithfulness).
    If the model hallucinates the answer without context, this catches it.
    """
    if rng is None:
        rng = random.Random()
    
    if not context:
        return question, context
        
    # Heuristic: Remove 50% of lines to break context
    lines = context.split("\n")
    if len(lines) <= 1:
        # If only one line/paragraph, remove it entirely (empty context)
        return question, ""
        
    keep_count = max(1, len(lines) // 2)
    keep_indices = set(rng.sample(range(len(lines)), keep_count))
    
    new_lines = [line for i, line in enumerate(lines) if i in keep_indices]
    new_context = "\n".join(new_lines)
    
    return question, new_context


def shuffle_context(
    question: str, 
    context: str, 
    *, 
    rng: Optional[random.Random] = None
) -> Tuple[str, str]:
    """
    Shuffle the order of context passages.
    
    Expectation: Answer should remain semantically equivalent (Position Invariance).
    Tests for "lost in the middle" phenomenon.
    """
    if rng is None:
        rng = random.Random()
        
    if not context:
        return question, context
        
    lines = context.split("\n")
    rng.shuffle(lines)
    new_context = "\n".join(lines)
    
    return question, new_context

