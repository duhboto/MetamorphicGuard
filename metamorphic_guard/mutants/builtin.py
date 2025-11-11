"""
Built-in prompt mutation strategies.
"""

import random
from typing import Any, Dict, Optional

from .__init__ import PromptMutant


class ParaphraseMutant(PromptMutant):
    """Paraphrase the prompt while preserving meaning."""

    PLUGIN_METADATA = {
        "name": "Paraphrase Mutant",
        "description": "Paraphrase prompts to test robustness",
        "version": "1.0.0",
    }

    def transform(self, prompt: str, **kwargs: Any) -> str:
        """Simple paraphrase by word substitution and reordering."""
        rng = kwargs.get("rng")
        if rng is None:
            rng = random.Random()

        # Simple transformations
        words = prompt.split()
        if len(words) < 3:
            return prompt

        # Swap adjacent words (simple reordering)
        if len(words) >= 2 and rng.random() < 0.3:
            i = rng.randint(0, len(words) - 2)
            words[i], words[i + 1] = words[i + 1], words[i]

        # Synonym substitutions (basic examples)
        synonyms = {
            "summarize": ["condense", "brief", "outline"],
            "explain": ["describe", "clarify", "elaborate"],
            "create": ["generate", "make", "produce"],
            "find": ["locate", "identify", "discover"],
        }

        for i, word in enumerate(words):
            word_lower = word.lower().rstrip(".,!?")
            if word_lower in synonyms and rng.random() < 0.2:
                words[i] = rng.choice(synonyms[word_lower]) + word[len(word_lower) :]

        return " ".join(words)


class NegationFlipMutant(PromptMutant):
    """Flip negation in prompts to test consistency."""

    PLUGIN_METADATA = {
        "name": "Negation Flip Mutant",
        "description": "Flip negation in prompts",
        "version": "1.0.0",
    }

    def transform(self, prompt: str, **kwargs: Any) -> str:
        """Flip negation words."""
        rng = kwargs.get("rng")
        if rng is None:
            rng = random.Random()

        # Simple negation pairs
        negations = [
            ("don't", "do"),
            ("doesn't", "does"),
            ("not", ""),
            ("never", "always"),
            ("no", "yes"),
        ]

        result = prompt
        for neg, pos in negations:
            if neg in result.lower() and rng.random() < 0.5:
                # Simple replacement (case-insensitive)
                import re

                result = re.sub(rf"\b{re.escape(neg)}\b", pos, result, flags=re.IGNORECASE)
                break

        return result


class RoleSwapMutant(PromptMutant):
    """Swap system/user roles to test role sensitivity."""

    PLUGIN_METADATA = {
        "name": "Role Swap Mutant",
        "description": "Swap system and user prompts",
        "version": "1.0.0",
    }

    def transform(self, prompt: str, **kwargs: Any) -> str:
        """For role-based prompts, this would swap roles."""
        # This is a placeholder - actual implementation would need context
        # about system vs user prompts
        return prompt

