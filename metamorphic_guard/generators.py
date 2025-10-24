"""
Input generators for test cases.
"""

import random
from typing import Callable, List, Sequence, Tuple


def gen_top_k_inputs(n: int, seed: int) -> List[Tuple[List[int], int]]:
    """
    Generate diverse test cases for the top_k task.

    The generator aims to cover the following scenarios:
    * Empty lists and single-element lists.
    * Lists with heavy duplication.
    * Already sorted ascending/descending inputs.
    * Very long lists (up to ~200 elements).
    * k larger than the list length and k == 0.
    * Negative-only, mixed-sign, and extreme magnitude values.
    """
    rng = random.Random(seed)
    scenarios: Sequence[Callable[[random.Random], Tuple[List[int], int]]] = (
        _case_empty,
        _case_single,
        _case_duplicates,
        _case_sorted_ascending,
        _case_sorted_descending,
        _case_long,
        _case_random_dense,
        _case_k_zero,
        _case_k_bigger_than_len,
        _case_negatives_only,
        _case_extreme_values,
        _case_small_range_many_duplicates,
    )

    test_cases: List[Tuple[List[int], int]] = []
    for i in range(n):
        case_fn = rng.choice(scenarios)
        test_cases.append(case_fn(rng))
    return test_cases


def _case_empty(rng: random.Random) -> Tuple[List[int], int]:
    return [], 0


def _case_single(rng: random.Random) -> Tuple[List[int], int]:
    value = rng.randint(-1000, 1000)
    return [value], rng.choice([0, 1, 2])


def _case_duplicates(rng: random.Random) -> Tuple[List[int], int]:
    base = rng.randint(-100, 100)
    dup_count = rng.randint(3, 15)
    noise = [rng.randint(-150, 150) for _ in range(rng.randint(1, 6))]
    values = [base] * dup_count + noise
    rng.shuffle(values)
    k = rng.randint(1, max(1, len(values)))
    return values, k


def _case_sorted_ascending(rng: random.Random) -> Tuple[List[int], int]:
    length = rng.randint(2, 40)
    values = sorted(rng.randint(-500, 500) for _ in range(length))
    k = rng.randint(1, length)
    return values, k


def _case_sorted_descending(rng: random.Random) -> Tuple[List[int], int]:
    length = rng.randint(2, 40)
    values = sorted((rng.randint(-500, 500) for _ in range(length)), reverse=True)
    k = rng.randint(1, length)
    return values, k


def _case_long(rng: random.Random) -> Tuple[List[int], int]:
    length = rng.randint(100, 200)
    values = [rng.randint(-10**4, 10**4) for _ in range(length)]
    k = rng.randint(1, length)
    return values, k


def _case_random_dense(rng: random.Random) -> Tuple[List[int], int]:
    length = rng.randint(5, 80)
    values = [rng.randint(-500, 500) for _ in range(length)]
    k = rng.randint(0, length + 5)
    return values, k


def _case_k_zero(rng: random.Random) -> Tuple[List[int], int]:
    length = rng.randint(1, 25)
    values = [rng.randint(-200, 200) for _ in range(length)]
    return values, 0


def _case_k_bigger_than_len(rng: random.Random) -> Tuple[List[int], int]:
    length = rng.randint(1, 25)
    values = [rng.randint(-100, 100) for _ in range(length)]
    k = length + rng.randint(1, 20)
    return values, k


def _case_negatives_only(rng: random.Random) -> Tuple[List[int], int]:
    length = rng.randint(3, 30)
    values = [rng.randint(-10**5, -1) for _ in range(length)]
    k = rng.randint(1, length)
    return values, k


def _case_extreme_values(rng: random.Random) -> Tuple[List[int], int]:
    palette = [-10**9, -10**6, -10**3, 0, 10**3, 10**6, 10**9]
    length = rng.randint(5, 30)
    values = [rng.choice(palette) for _ in range(length)]
    k = rng.randint(1, length)
    return values, k


def _case_small_range_many_duplicates(rng: random.Random) -> Tuple[List[int], int]:
    length = rng.randint(10, 60)
    base_values = [rng.randint(-3, 3) for _ in range(length)]
    values = base_values + [rng.randint(-3, 3) for _ in range(length // 2)]
    rng.shuffle(values)
    k = rng.randint(1, max(1, len(values)))
    return values, k

