"""
Serialization helpers for queue payloads.
"""

from __future__ import annotations

import base64
import json
import warnings
import zlib
from typing import Any, List, Tuple

try:
    import msgpack  # type: ignore

    MSGPACK_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    MSGPACK_AVAILABLE = False


def prepare_payload(
    args_list: List[Tuple[Any, ...]],
    *,
    compress_default: bool,
    adaptive: bool,
    threshold_bytes: int,
    use_msgpack: bool = False,
) -> Tuple[bytes, bool, int, int]:
    """
    Prepare a payload for queue publication with optional adaptive compression.

    Returns encoded bytes, compression flag, raw length, encoded length.
    """
    if use_msgpack and MSGPACK_AVAILABLE:
        raw = msgpack.packb(args_list, use_bin_type=True)
    else:
        if use_msgpack and not MSGPACK_AVAILABLE:
            warnings.warn(
                "MessagePack requested but not available. Install with: pip install msgpack. "
                "Falling back to JSON.",
                UserWarning,
                stacklevel=2,
            )
        raw = json.dumps(args_list).encode("utf-8")

    raw_len = len(raw)

    if not compress_default:
        encoded = base64.b64encode(raw)
        return encoded, False, raw_len, len(encoded)

    compressed = zlib.compress(raw)
    compressed_len = len(compressed)
    use_compression = not (
        adaptive and (raw_len <= threshold_bytes or compressed_len >= raw_len)
    )

    data = compressed if use_compression else raw
    encoded = base64.b64encode(data)
    return encoded, use_compression, raw_len, len(encoded)


def decode_payload(payload: bytes, compress: bool | None = None) -> bytes:
    decoded = base64.b64decode(payload)
    if compress:
        try:
            return zlib.decompress(decoded)
        except zlib.error:
            return decoded
    return decoded


def decode_args(
    payload: bytes,
    *,
    compress: bool,
    use_msgpack: bool = False,
) -> List[Tuple[Any, ...]]:
    decoded = decode_payload(payload, compress=compress)
    if use_msgpack and MSGPACK_AVAILABLE:
        return msgpack.unpackb(decoded, raw=False, strict_map_key=False)
    return json.loads(decoded)


__all__ = ["prepare_payload", "decode_args", "MSGPACK_AVAILABLE"]

