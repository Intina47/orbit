from __future__ import annotations

import base64
import binascii
import json

import numpy as np

_FLOAT16_PREFIX = "f16b64"


def encode_vector(values: list[float]) -> str:
    """Encode vectors compactly for persistence while staying backward compatible."""
    if not values:
        return "[]"
    array = np.asarray(values, dtype=np.float32)
    payload = base64.b64encode(array.astype(np.float16).tobytes()).decode("ascii")
    return f"{_FLOAT16_PREFIX}:{array.shape[0]}:{payload}"


def decode_vector(serialized: str) -> list[float]:
    """Decode vector payload from either float16-packed or legacy JSON formats."""
    text = serialized.strip()
    if not text or text == "[]":
        return []
    if text.startswith(f"{_FLOAT16_PREFIX}:"):
        parts = text.split(":", 2)
        if len(parts) != 3:
            return []
        try:
            size = int(parts[1])
            binary = base64.b64decode(parts[2], validate=True)
        except (ValueError, binascii.Error):
            return []
        if size <= 0 or len(binary) != size * 2:
            return []
        array = np.frombuffer(binary, dtype=np.float16).astype(np.float32)
        return [float(item) for item in array]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    output: list[float] = []
    for item in data:
        try:
            output.append(float(item))
        except (TypeError, ValueError):
            continue
    return output
