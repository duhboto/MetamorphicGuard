import base64

import pytest

from metamorphic_guard.errors import QueueSerializationError
from metamorphic_guard.queue_serialization import decode_args, prepare_payload


def test_prepare_payload_raises_on_unserializable_object() -> None:
    class Unserializable:
        pass

    with pytest.raises(QueueSerializationError):
        prepare_payload(
            [(Unserializable(),)],
            compress_default=False,
            adaptive=False,
            threshold_bytes=1024,
        )


def test_decode_args_rejects_malformed_base64() -> None:
    bad_payload = base64.b64encode(b"{}")[:-4]  # Corrupt the padding
    with pytest.raises(QueueSerializationError):
        decode_args(bad_payload, compress=False, use_msgpack=False)

