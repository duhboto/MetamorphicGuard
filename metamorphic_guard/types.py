"""
Shared typing helpers for Metamorphic Guard.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, MutableMapping, Sequence, Tuple, Union

JSONPrimitive = Union[str, int, float, bool, None]
JSONValue = Union["JSONPrimitive", "JSONDict", "JSONList"]
JSONList = List[JSONValue]
JSONDict = Dict[str, JSONValue]

StrMapping = Mapping[str, JSONPrimitive | JSONList | JSONDict]
MutableStrMapping = MutableMapping[str, JSONPrimitive | JSONList | JSONDict]

StrSequence = Sequence[str]
StrTuple = Tuple[str, ...]

__all__ = [
    "JSONPrimitive",
    "JSONValue",
    "JSONList",
    "JSONDict",
    "StrMapping",
    "MutableStrMapping",
    "StrSequence",
    "StrTuple",
]

