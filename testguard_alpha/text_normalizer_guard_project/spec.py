# spec.py

import random
import string
from typing import List, Tuple

from metamorphic_guard import (
    Spec,
    Property,
    MetamorphicRelation,
    task,
)
from metamorphic_guard.specs import Metric

# ---------- Input generator ----------

ALPHABET = string.ascii_letters
PUNCT = ".,!?;:'\"-()[]/\\"
WHITES = [" ", "\t", "\n", "\r", "\u00A0"]  # includes non-breaking space

def gen_inputs(n: int, seed: int) -> List[Tuple[str]]:
    rng = random.Random(seed)
    cases: List[Tuple[str]] = []
    for _ in range(n):
        chunks = []
        for _ in range(rng.randint(3, 12)):
            kind = rng.choice(["word", "punct", "space"])
            if kind == "word":
                word_len = rng.randint(1, 12)
                word = "".join(rng.choice(ALPHABET) for _ in range(word_len))
                # random casing
                if rng.random() < 0.33:
                    word = word.lower()
                elif rng.random() < 0.66:
                    word = word.upper()
                else:
                    word = word.title()
                chunks.append(word)
            elif kind == "punct":
                chunks.append(rng.choice(PUNCT))
            else:  # space
                chunks.append(rng.choice(WHITES) * rng.randint(1, 4))
        text = "".join(chunks)
        cases.append((text,))
    return cases

# ---------- Properties ----------

properties = [
    Property(
        description="Output is a string",
        check=lambda output, text: isinstance(output, str),
    ),
    Property(
        description="No leading/trailing whitespace after normalization",
        check=lambda output, text: output == output.strip(),
    ),
    Property(
        description="No internal runs of pure whitespace longer than 1 char",
        check=lambda output, text: "  " not in output,
    ),
]

# ---------- Equivalence ----------

def equivalence(a: str, b: str) -> bool:
    # For this project, we expect identical normalized output.
    return a == b

# ---------- Optional metric ----------

metrics = [
    Metric(
        name="length",
        extract=lambda output, text: float(len(output)),
        kind="mean",
    )
]

# ---------- Metamorphic Relations ----------

def pad_whitespace_transform(*args, rng=None):
    """Add leading and trailing whitespace."""
    text = args[0]
    return ("   \t" + text + "\n\n",)

def burst_whitespace_transform(*args, rng=None):
    """Expand spaces into mixed whitespace characters."""
    text = args[0]
    if rng is None:
        import random
        rng = random.Random()
    result = []
    for char in text:
        if char == " ":
            # Replace space with random mix of whitespace
            result.append(rng.choice(WHITES) * rng.randint(1, 3))
        else:
            result.append(char)
    return ("".join(result),)

def case_flip_transform(*args, rng=None):
    """Flip case of the input text."""
    text = args[0]
    if rng is None:
        import random
        rng = random.Random()
    if rng.random() < 0.5:
        return (text.swapcase(),)
    else:
        return (text.upper(),)

relations = [
    MetamorphicRelation(
        name="pad_whitespace",
        transform=pad_whitespace_transform,
        expect="equal",
        accepts_rng=True,
    ),
    MetamorphicRelation(
        name="burst_whitespace",
        transform=burst_whitespace_transform,
        expect="equal",
        accepts_rng=True,
    ),
    MetamorphicRelation(
        name="case_flip",
        transform=case_flip_transform,
        expect="equal",
        accepts_rng=True,
    ),
]

# ---------- TaskSpec ----------

@task("text_normalizer")
def text_normalizer_spec():
    return Spec(
        gen_inputs=gen_inputs,
        properties=properties,
        relations=relations,
        equivalence=equivalence,
        metrics=metrics,
    )

