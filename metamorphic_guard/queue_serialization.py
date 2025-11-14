"""
Serialization helpers for queue payloads.
"""

from __future__ import annotations

import base64
import binascii
import json
import warnings
import zlib
from typing import Any, List, Sequence, Tuple

from .errors import QueueSerializationError

try:  # pragma: no cover - optional dependency
    import msgpack  # type: ignore

    MSGPACK_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    MSGPACK_AVAILABLE = False


ArgsTuple = Tuple[Any, ...]
ArgsList = List[ArgsTuple]


def prepare_payload(
    args_list: Sequence[ArgsTuple],
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
    try:
        if use_msgpack and MSGPACK_AVAILABLE:
            raw = msgpack.packb(list(args_list), use_bin_type=True)
        else:
            if use_msgpack and not MSGPACK_AVAILABLE:
                warnings.warn(
                    "MessagePack requested but not available. Install with: pip install msgpack. "
                    "Falling back to JSON.",
                    UserWarning,
                    stacklevel=2,
                )
            raw = json.dumps(list(args_list)).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise QueueSerializationError(
            "Unable to serialize queue arguments.",
            details={"use_msgpack": use_msgpack, "args_preview": _preview_args(args_list)},
            original=exc,
        ) from exc

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
    try:
        encoded = base64.b64encode(data)
    except (TypeError, ValueError) as exc:
        raise QueueSerializationError(
            "Unable to base64-encode queue payload.",
            details={"use_compression": use_compression, "raw_length": raw_len},
            original=exc,
        ) from exc
    return encoded, use_compression, raw_len, len(encoded)


def decode_payload(payload: bytes, compress: bool | None = None) -> bytes:
    try:
        decoded = base64.b64decode(payload)
    except (ValueError, binascii.Error) as exc:
        raise QueueSerializationError(
            "Malformed base64 payload.",
            details={"compress": bool(compress)},
            original=exc,
        ) from exc
    if compress:
        try:
            return zlib.decompress(decoded)
        except zlib.error as exc:
            raise QueueSerializationError(
                "Compressed payload cannot be decompressed.",
                details={"compress": True},
                original=exc,
            ) from exc
    return decoded


def decode_args(
    payload: bytes,
    *,
    compress: bool,
    use_msgpack: bool = False,
) -> ArgsList:
    decoded = decode_payload(payload, compress=compress)
    try:
        if use_msgpack and MSGPACK_AVAILABLE:
            return msgpack.unpackb(decoded, raw=False, strict_map_key=False)
        return json.loads(decoded)
    except (TypeError, ValueError) as exc:
        raise QueueSerializationError(
            "Unable to decode queue payload.",
            details={"use_msgpack": use_msgpack},
            original=exc,
        ) from exc


def _preview_args(args_list: Sequence[ArgsTuple], limit: int = 2) -> Any:
    materialized = list(args_list)
    preview = materialized[:limit]
    if len(materialized) > limit:
        preview.append(f"...(+{len(materialized) - limit} more)")
    return preview


__all__ = ["prepare_payload", "decode_args", "decode_payload", "MSGPACK_AVAILABLE"]

