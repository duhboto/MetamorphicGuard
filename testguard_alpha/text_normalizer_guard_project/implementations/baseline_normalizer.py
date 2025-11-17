# implementations/baseline_normalizer.py

import re

def solve(text: str) -> str:
    # Super simple: strip, collapse whitespace, lowercase
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.lower()

