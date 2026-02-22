from __future__ import annotations

import numpy as np

from decision_engine.vector_codec import decode_vector, encode_vector


def test_vector_codec_round_trip_float16_payload() -> None:
    values = [0.123456, -0.987654, 0.0, 1.0]
    encoded = encode_vector(values)
    decoded = decode_vector(encoded)

    assert encoded.startswith("f16b64:")
    assert len(decoded) == len(values)
    np.testing.assert_allclose(decoded, values, rtol=1e-3, atol=1e-3)


def test_vector_codec_backwards_compatible_with_json() -> None:
    decoded = decode_vector("[0.1, 0.2, -0.3]")
    np.testing.assert_allclose(decoded, [0.1, 0.2, -0.3], rtol=1e-6, atol=1e-6)


def test_vector_codec_handles_invalid_payload() -> None:
    assert decode_vector("f16b64:not-a-size:%%%") == []
