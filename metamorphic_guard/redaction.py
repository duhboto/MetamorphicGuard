"""Utilities for redacting sensitive data from sandbox outputs."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, List, Sequence


_DEFAULT_PATTERNS = (
    r"AKIA[0-9A-Z]{16}",  # AWS access key id
    r"ASIA[0-9A-Z]{16}",
    r"(?i)secret[_-]?key\s*[:=]\s*[A-Za-z0-9/+]{16,}",
    r"(?i)api[-_]?key\s*[:=]\s*[A-Za-z0-9_-]{16,}",
    r"(?i)token\s*[:=]\s*[A-Za-z0-9\-_.]{16,}",
)

_REPLACEMENT = "[REDACTED]"


def _normalize_patterns(patterns: Any) -> List[str]:
    if patterns is None:
        return []
    if isinstance(patterns, str):
        return [p.strip() for p in patterns.split(",") if p.strip()]
    if isinstance(patterns, Sequence):
        normalized: List[str] = []
        for item in patterns:
            if not item:
                continue
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    normalized.append(stripped)
        return normalized
    return []


def _env_patterns() -> List[str]:
    env_value = os.environ.get("METAMORPHIC_GUARD_REDACT", "")
    return _normalize_patterns(env_value)


@lru_cache(maxsize=16)
def _compile_patterns(pattern_tuple: tuple[str, ...]) -> List[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in pattern_tuple if pattern]


@dataclass(slots=True)
class SecretRedactor:
    patterns: Sequence[re.Pattern[str]]
    replacement: str = _REPLACEMENT

    def redact(self, payload: Any) -> Any:
        if isinstance(payload, str):
            return self._redact_text(payload)
        if isinstance(payload, dict):
            return {self.redact(key): self.redact(value) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self.redact(item) for item in payload]
        if isinstance(payload, tuple):
            return tuple(self.redact(item) for item in payload)
        if isinstance(payload, set):
            return {self.redact(item) for item in payload}
        return payload

    def _redact_text(self, text: str) -> str:
        redacted = text
        for pattern in self.patterns:
            redacted = pattern.sub(self.replacement, redacted)
        return redacted


def get_redactor(config: dict[str, Any] | None = None) -> SecretRedactor:
    config = config or {}
    config_patterns = _normalize_patterns(config.get("redact_patterns"))
    combined_patterns = tuple(sorted(set(_DEFAULT_PATTERNS) | set(_env_patterns()) | set(config_patterns)))
    compiled = _compile_patterns(combined_patterns)
    return SecretRedactor(compiled)

