"""RAG-specific metamorphic relations and mutants."""

from __future__ import annotations

import random
from typing import Any, Optional

from ..mutants import PromptMutant


class CitationShuffleMutant(PromptMutant):
    """Shuffle citation order in RAG prompts to test consistency."""

    PLUGIN_METADATA = {
        "name": "Citation Shuffle",
        "version": "1.0.0",
        "description": "Shuffles citation order in RAG prompts",
    }

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self.intensity = float(config.get("intensity", 1.0)) if config else 1.0

    def transform(self, prompt: str, **kwargs: Any) -> str:
        """Shuffle citations in the prompt."""
        import re

        rng = kwargs.get("rng")
        if rng is None:
            rng = random.Random()

        # Find citation patterns like [1], [2], or (source1), (source2)
        citation_pattern = r"\[(\d+)\]|\(([^)]+)\)"

        # Find all citations
        citations = re.findall(citation_pattern, prompt)
        if len(citations) < 2:
            return prompt

        # Shuffle citation numbers/text
        shuffled = citations.copy()
        rng.shuffle(shuffled)

        # Replace in order
        result = prompt
        for i, (original, replacement) in enumerate(zip(citations, shuffled)):
            if original[0]:  # Numbered citation
                result = result.replace(f"[{original[0]}]", f"[{replacement[0]}]", 1)
            else:  # Text citation
                result = result.replace(f"({original[1]})", f"({replacement[1]})", 1)

        return result


class ContextReorderMutant(PromptMutant):
    """Reorder context chunks in RAG prompts to test robustness."""

    PLUGIN_METADATA = {
        "name": "Context Reorder",
        "version": "1.0.0",
        "description": "Reorders context chunks in RAG prompts",
    }

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self.intensity = float(config.get("intensity", 1.0)) if config else 1.0

    def transform(self, prompt: str, **kwargs: Any) -> str:
        """Reorder context sections in the prompt."""
        rng = kwargs.get("rng")
        if rng is None:
            rng = random.Random()

        # Split by common separators
        sections = prompt.split("\n\n")
        if len(sections) < 2:
            return prompt

        # Identify context sections (heuristic: longer sections)
        context_sections = [s for s in sections if len(s) > 100]
        if len(context_sections) < 2:
            return prompt

        # Shuffle context sections
        shuffled = context_sections.copy()
        rng.shuffle(shuffled)

        # Reconstruct prompt
        result_sections = []
        context_idx = 0
        for section in sections:
            if section in context_sections:
                result_sections.append(shuffled[context_idx])
                context_idx += 1
            else:
                result_sections.append(section)

        return "\n\n".join(result_sections)

