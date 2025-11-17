# implementations/candidate_normalizer.py

import re
import unicodedata

def solve(text: str) -> str:
    # Example "improved" normalizer
    # 1) Strip outer whitespace
    text = text.strip()
    
    # 2) Normalize unicode (e.g., fancy quotes, accents composed consistently)
    text = unicodedata.normalize("NFKC", text)
    
    # 3) Convert non-breaking spaces etc. to regular spaces
    text = text.replace("\u00A0", " ")
    
    # 4) Collapse whitespace runs
    text = re.sub(r"\s+", " ", text)
    
    # 5) Lowercase
    return text.lower()

