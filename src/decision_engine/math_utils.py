from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.floating[Any]]


def to_unit_vector(values: FloatArray) -> FloatArray:
    norm = float(np.linalg.norm(values))
    if norm == 0.0:
        return values
    return values / norm


def cosine_similarity(left: FloatArray, right: FloatArray) -> float:
    left_unit = to_unit_vector(left)
    right_unit = to_unit_vector(right)
    return float(np.dot(left_unit, right_unit))
