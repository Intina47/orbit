from __future__ import annotations

import pytest

from decision_engine.semantic_encoding import _load_json_object


def test_load_json_object_success() -> None:
    payload = _load_json_object('{"summary":"ok","intent":"interaction"}')
    assert payload["summary"] == "ok"


def test_load_json_object_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        _load_json_object("{not-json}")


def test_load_json_object_non_object_raises() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        _load_json_object('["a","b"]')
