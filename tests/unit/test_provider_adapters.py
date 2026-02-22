from __future__ import annotations

import numpy as np
import pytest

from decision_engine.models import RawEvent
from memory_engine.providers import adapters
from memory_engine.providers.adapters import AnthropicEmbeddingProvider


def test_adapter_helper_prompts_and_json_parsing() -> None:
    event = RawEvent(
        content="Developer resolved deployment outage", context={"repo": "orbit"}
    )
    system_prompt, user_prompt = adapters._semantic_prompts(event)
    assert "Return only JSON" in system_prompt
    assert "deployment outage" in user_prompt

    wrapped = '```json\n{"summary":"ok","intent":"incident"}\n```'
    payload = adapters._parse_json_object(wrapped)
    understanding = adapters._semantic_from_payload(payload, "fallback")
    assert understanding.summary == "ok"
    assert understanding.intent == "incident"


def test_adapter_helper_rejects_non_object_json() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        adapters._parse_json_object('["not","object"]')


def test_adapter_embedding_dimension_coercion() -> None:
    short = np.asarray([1.0, 2.0], dtype=np.float32)
    padded = adapters._coerce_embedding_dimensions(short, 4)
    assert padded.shape[0] == 4
    long = np.asarray([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    truncated = adapters._coerce_embedding_dimensions(long, 2)
    assert truncated.shape[0] == 2


def test_anthropic_embedding_provider_functional_path(monkeypatch) -> None:
    class _FakeMessages:
        @staticmethod
        def create(**kwargs):
            _ = kwargs
            return type(
                "Response",
                (),
                {
                    "content": [
                        type("Block", (), {"text": '{"embedding":[0.1,0.2,0.3,0.4]}'})()
                    ]
                },
            )()

    class _FakeAnthropicClient:
        def __init__(self, api_key: str | None = None) -> None:
            _ = api_key
            self.messages = _FakeMessages()

    class _FakeAnthropicModule:
        Anthropic = _FakeAnthropicClient

    monkeypatch.setattr(adapters, "anthropic_module", _FakeAnthropicModule())
    provider = AnthropicEmbeddingProvider(
        model="fake-embed-model",
        api_key="test-key",
        dimensions=4,
    )
    vector = provider.embed("hello")
    assert vector.shape[0] == 4
    assert np.isclose(float(np.linalg.norm(vector)), 1.0)


def test_optional_semantic_embedding_adapters_raise_when_modules_absent(
    monkeypatch,
) -> None:
    monkeypatch.setattr(adapters, "anthropic_module", None)
    monkeypatch.setattr(adapters, "google_genai_module", None)
    monkeypatch.setattr(adapters, "ollama_module", None)

    with pytest.raises(RuntimeError):
        adapters.AnthropicSemanticProvider()
    with pytest.raises(RuntimeError):
        adapters.GeminiSemanticProvider()
    with pytest.raises(RuntimeError):
        adapters.GeminiEmbeddingProvider()
    with pytest.raises(RuntimeError):
        adapters.OllamaSemanticProvider()
    with pytest.raises(RuntimeError):
        adapters.OllamaEmbeddingProvider()
