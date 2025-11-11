"""
Counterexample shrinking to find minimal failing inputs.

Shrinking reduces the size/complexity of failing test cases while preserving
the failure, making debugging easier.
"""

from __future__ import annotations

from typing import Any, Callable, Tuple


def shrink_input(
    args: Tuple[Any, ...],
    test_fails: Callable[[Tuple[Any, ...]], bool],
    max_attempts: int = 100,
) -> Tuple[Any, ...]:
    """
    Attempt to shrink a failing input to a minimal counterexample.
    
    Args:
        args: Original failing input tuple
        test_fails: Function that returns True if the input still fails
        max_attempts: Maximum shrinking attempts before giving up
        
    Returns:
        Shrunk input tuple (may be the same as original if shrinking fails)
    """
    current = args
    attempts = 0
    
    while attempts < max_attempts:
        shrunk = _try_shrink(current, test_fails)
        if shrunk == current:
            # No further shrinking possible
            break
        current = shrunk
        attempts += 1
    
    return current


def _try_shrink(
    args: Tuple[Any, ...],
    test_fails: Callable[[Tuple[Any, ...]], bool],
) -> Tuple[Any, ...]:
    """Try to shrink the input tuple by one step."""
    # Try removing arguments (from the end)
    if len(args) > 1:
        for i in range(len(args) - 1, -1, -1):
            candidate = args[:i] + args[i + 1 :]
            if test_fails(candidate):
                return candidate
    
    # Try shrinking each argument individually
    shrunk_args = []
    for i, arg in enumerate(args):
        shrunk_arg = _shrink_value(arg, lambda val: test_fails(args[:i] + (val,) + args[i + 1 :]))
        shrunk_args.append(shrunk_arg)
    
    candidate = tuple(shrunk_args)
    if candidate != args and test_fails(candidate):
        return candidate
    
    return args


def _shrink_value(value: Any, test_fails: Callable[[Any], bool]) -> Any:
    """Shrink a single value."""
    if isinstance(value, list):
        return _shrink_list(value, test_fails)
    elif isinstance(value, tuple):
        return tuple(_shrink_list(list(value), lambda lst: test_fails(tuple(lst))))
    elif isinstance(value, str):
        return _shrink_string(value, test_fails)
    elif isinstance(value, (int, float)):
        return _shrink_number(value, test_fails)
    elif isinstance(value, dict):
        return _shrink_dict(value, test_fails)
    else:
        # Unknown type, return as-is
        return value


def _shrink_list(lst: list[Any], test_fails: Callable[[list[Any]], bool]) -> list[Any]:
    """Shrink a list by removing elements or shrinking elements."""
    if not lst:
        return lst
    
    # Try removing elements from the end
    for i in range(len(lst) - 1, -1, -1):
        candidate = lst[:i] + lst[i + 1 :]
        if test_fails(candidate):
            return candidate
    
    # Try removing elements from the beginning
    for i in range(len(lst)):
        candidate = lst[i + 1 :]
        if test_fails(candidate):
            return candidate
    
    # Try shrinking each element
    shrunk = []
    for i, item in enumerate(lst):
        shrunk_item = _shrink_value(
            item, lambda val: test_fails(lst[:i] + [val] + lst[i + 1 :])
        )
        shrunk.append(shrunk_item)
    
    if shrunk != lst and test_fails(shrunk):
        return shrunk
    
    return lst


def _shrink_string(s: str, test_fails: Callable[[str], bool]) -> str:
    """Shrink a string by removing characters."""
    if not s:
        return s
    
    # Try removing from the end
    for i in range(len(s) - 1, 0, -1):
        candidate = s[:i]
        if test_fails(candidate):
            return candidate
    
    # Try removing from the beginning
    for i in range(1, len(s)):
        candidate = s[i:]
        if test_fails(candidate):
            return candidate
    
    # Try removing from the middle (binary search style)
    if len(s) > 2:
        mid = len(s) // 2
        candidate = s[:mid] + s[mid + 1 :]
        if test_fails(candidate):
            return candidate
    
    return s


def _shrink_number(n: int | float, test_fails: Callable[[int | float], bool]) -> int | float:
    """Shrink a number by reducing its magnitude."""
    if n == 0:
        return n
    
    # Try zero
    if test_fails(0):
        return 0
    
    # Try smaller positive values (for positive numbers)
    if n > 0:
        # Try half
        candidate = n // 2 if isinstance(n, int) else n / 2
        if candidate != n and test_fails(candidate):
            return candidate
        
        # Try 1
        if n > 1 and test_fails(1):
            return 1
    
    # Try larger negative values (for negative numbers)
    if n < 0:
        # Try half
        candidate = n // 2 if isinstance(n, int) else n / 2
        if candidate != n and test_fails(candidate):
            return candidate
        
        # Try -1
        if n < -1 and test_fails(-1):
            return -1
    
    return n


def _shrink_dict(d: dict[str, Any], test_fails: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    """Shrink a dictionary by removing keys or shrinking values."""
    if not d:
        return d
    
    # Try removing keys
    keys = list(d.keys())
    for key in reversed(keys):
        candidate = {k: v for k, v in d.items() if k != key}
        if test_fails(candidate):
            return candidate
    
    # Try shrinking values
    shrunk = {}
    for key, value in d.items():
        shrunk_value = _shrink_value(
            value, lambda val: test_fails({**d, key: val})
        )
        shrunk[key] = shrunk_value
    
    if shrunk != d and test_fails(shrunk):
        return shrunk
    
    return d

