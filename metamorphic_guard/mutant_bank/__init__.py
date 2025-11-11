"""Mutant bank: Versioned pack of metamorphic relations for LLM/AI tasks."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..mutants import PromptMutant
from ..mutants.builtin import ParaphraseMutant, NegationFlipMutant, RoleSwapMutant
from ..mutants.advanced import (
    JailbreakProbeMutant,
    ChainOfThoughtToggleMutant,
    InstructionPermutationMutant,
)

__version__ = "1.0.0"

# Versioned mutant packs
MUTANT_PACKS: Dict[str, Dict[str, any]] = {
    "llm_basic_v1": {
        "version": "1.0.0",
        "description": "Basic LLM mutants: paraphrase, negation flip, role swap",
        "mutants": ["paraphrase", "negation_flip", "role_swap"],
        "break_rate": 0.15,  # Empirical break rate
    },
    "llm_advanced_v1": {
        "version": "1.0.0",
        "description": "Advanced LLM mutants: jailbreak probes, CoT toggle, instruction permutation",
        "mutants": ["jailbreak_probe", "chain_of_thought", "instruction_permutation"],
        "break_rate": 0.25,
    },
    "llm_complete_v1": {
        "version": "1.0.0",
        "description": "Complete LLM mutant pack (basic + advanced)",
        "mutants": [
            "paraphrase",
            "negation_flip",
            "role_swap",
            "jailbreak_probe",
            "chain_of_thought",
            "instruction_permutation",
        ],
        "break_rate": 0.30,
    },
    "rag_basic_v1": {
        "version": "1.0.0",
        "description": "RAG-specific mutants: citation shuffle, context reorder",
        "mutants": ["citation_shuffle", "context_reorder"],
        "break_rate": 0.20,
    },
}


def get_mutant_pack(name: str) -> Dict[str, any]:
    """Get a mutant pack by name."""
    if name not in MUTANT_PACKS:
        available = list(MUTANT_PACKS.keys())
        raise ValueError(f"Mutant pack '{name}' not found. Available: {available}")
    return MUTANT_PACKS[name]


def list_packs() -> List[str]:
    """List all available mutant packs."""
    return list(MUTANT_PACKS.keys())


def create_mutants_from_pack(
    pack_name: str, intensity: float = 1.0, config: Optional[Dict[str, any]] = None
) -> List[PromptMutant]:
    """
    Create mutant instances from a pack.

    Args:
        pack_name: Name of the mutant pack
        intensity: Intensity multiplier (0.0-1.0) for mutation strength
        config: Optional configuration overrides

    Returns:
        List of PromptMutant instances
    """
    pack = get_mutant_pack(pack_name)
    mutant_names = pack["mutants"]
    mutants: List[PromptMutant] = []

    # Mutant factory mapping
    factory_map: Dict[str, type] = {
        "paraphrase": ParaphraseMutant,
        "negation_flip": NegationFlipMutant,
        "role_swap": RoleSwapMutant,
        "jailbreak_probe": JailbreakProbeMutant,
        "chain_of_thought": ChainOfThoughtToggleMutant,
        "instruction_permutation": InstructionPermutationMutant,
    }

    for name in mutant_names:
        if name not in factory_map:
            # Try to load from plugin registry
            try:
                from ..plugins import mutant_plugins

                plugin_registry = mutant_plugins()
                plugin_def = plugin_registry.get(name.lower())
                if plugin_def is not None:
                    mutant_class = plugin_def.factory
                    if isinstance(mutant_class, type):
                        mutant_config = (config or {}).copy()
                        mutant_config["intensity"] = intensity
                        mutants.append(mutant_class(config=mutant_config))
                    continue
            except ImportError:
                pass

            # Skip unknown mutants
            continue

        mutant_class = factory_map[name]
        mutant_config = (config or {}).copy()
        mutant_config["intensity"] = intensity
        mutants.append(mutant_class(config=mutant_config))

    return mutants


def apply_pack(
    pack_name: str,
    prompts: Sequence[str],
    intensity: float = 1.0,
    p: float = 0.3,
    config: Optional[Dict[str, any]] = None,
) -> List[str]:
    """
    Apply a mutant pack to a batch of prompts.

    Args:
        pack_name: Name of the mutant pack
        prompts: Input prompts to mutate
        intensity: Intensity multiplier (0.0-1.0)
        p: Probability of applying each mutant (0.0-1.0)
        config: Optional configuration overrides

    Returns:
        List of mutated prompts
    """
    import random

    mutants = create_mutants_from_pack(pack_name, intensity=intensity, config=config)
    rng = random.Random(42)  # Deterministic by default

    mutated = []
    for prompt in prompts:
        result = prompt
        for mutant in mutants:
            if rng.random() < p:
                try:
                    result, _ = mutant.apply(result, None, rng)
                except Exception:
                    # If mutation fails, keep original
                    pass
        mutated.append(result)

    return mutated

