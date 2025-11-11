"""
Helper functions for creating LLM task specifications.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from .judges import Judge, LLMJudge
from .mutants import Mutant, PromptMutant
from .specs import MetamorphicRelation, Property, Spec


def create_llm_spec(
    gen_inputs: Callable[[int, int], List[Tuple[Any, ...]]],
    judges: Optional[List[Judge | LLMJudge]] = None,
    mutants: Optional[List[Mutant | PromptMutant]] = None,
    fmt_in: Optional[Callable[[Tuple[Any, ...]], str]] = None,
    fmt_out: Optional[Callable[[Any], str]] = None,
) -> Spec:
    """
    Create a Spec for LLM evaluation.

    Args:
        gen_inputs: Function that generates test inputs (n, seed) -> List[Tuple]
        judges: List of judges to use as properties
        mutants: List of mutants to use as metamorphic relations
        fmt_in: Function to format inputs for display
        fmt_out: Function to format outputs for display

    Returns:
        Spec instance ready for use with run_eval
    """
    # Convert judges to properties
    properties: List[Property] = []
    if judges:
        for judge in judges:
            # Capture judge in closure properly to avoid late binding issue
            judge_capture = judge  # Create a new variable for each iteration

            def make_check(judge_instance: Judge) -> Callable[..., bool]:
                def check(output: Any, *args: Any) -> bool:
                    try:
                        result = judge_instance.evaluate(output, args[0] if args else None)
                        return result.get("pass", False) if isinstance(result, dict) else False
                    except Exception:
                        # If judge evaluation fails, treat as failure
                        return False

                return check

            properties.append(
                Property(
                    check=make_check(judge_capture),
                    description=f"{judge.name()}: {judge.__class__.__name__}",
                    mode="hard",
                )
            )

    # Convert mutants to metamorphic relations
    relations: List[MetamorphicRelation] = []
    if mutants:
        for mutant in mutants:
            # Capture mutant in closure properly to avoid late binding issue
            mutant_capture = mutant  # Create a new variable for each iteration

            def make_transform(mutant_instance: Mutant) -> Callable[..., Tuple[Any, ...]]:
                def transform(*args: Any, rng: Any = None) -> Tuple[Any, ...]:
                    if len(args) == 0:
                        return args
                    try:
                        # Transform the first argument (prompt)
                        # Pass rng as keyword argument to match PromptMutant interface
                        transformed = mutant_instance.transform(args[0], rng=rng) if rng is not None else mutant_instance.transform(args[0])
                        return (transformed,) + args[1:]
                    except Exception:
                        # If mutation fails, return original args
                        return args

                return transform

            relations.append(
                MetamorphicRelation(
                    name=mutant.name(),
                    transform=make_transform(mutant_capture),
                    expect="equal",
                    accepts_rng=True,
                )
            )

    # Default equivalence (string comparison for LLM outputs)
    def llm_equivalence(a: Any, b: Any) -> bool:
        if isinstance(a, str) and isinstance(b, str):
            return a.strip() == b.strip()
        return a == b

    # Default formatters
    if fmt_in is None:

        def fmt_in_default(args: Tuple[Any, ...]) -> str:
            if len(args) >= 1:
                return str(args[0])[:100]  # First arg is usually the prompt
            return str(args)

        fmt_in = fmt_in_default

    if fmt_out is None:

        def fmt_out_default(result: Any) -> str:
            if isinstance(result, str):
                return result[:200]  # Truncate long outputs
            return str(result)

        fmt_out = fmt_out_default

    return Spec(
        gen_inputs=gen_inputs,
        properties=properties,
        relations=relations,
        equivalence=llm_equivalence,
        fmt_in=fmt_in,
        fmt_out=fmt_out,
    )


def simple_llm_inputs(
    prompts: List[str],
    system_prompt: Optional[str] = None,
) -> Callable[[int, int], List[Tuple[Any, ...]]]:
    """
    Create a simple input generator from a list of prompts.

    Args:
        prompts: List of user prompts
        system_prompt: Optional system prompt (same for all)

    Returns:
        Input generator function
    """
    import random

    def gen_inputs(n: int, seed: int) -> List[Tuple[Any, ...]]:
        rng = random.Random(seed)
        inputs: List[Tuple[Any, ...]] = []
        for _ in range(n):
            prompt = rng.choice(prompts)
            if system_prompt:
                inputs.append((prompt, system_prompt))
            else:
                inputs.append((prompt,))
        return inputs

    return gen_inputs

