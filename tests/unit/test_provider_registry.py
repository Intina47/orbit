from __future__ import annotations

import pytest

import decision_engine.semantic_encoding as semantic_encoding
from decision_engine.semantic_encoding import (
    ContextSemanticProvider,
    DeterministicEmbeddingProvider,
    OpenAIEmbeddingProvider,
    OpenAISemanticProvider,
)
from memory_engine.providers import adapters
from memory_engine.providers.registry import (
    build_embedding_provider,
    build_semantic_provider,
)


def test_registry_defaults_to_deterministic_and_context(monkeypatch) -> None:
    monkeypatch.delenv("MDE_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("MDE_SEMANTIC_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("USE_LOCAL_EMBEDDINGS", "true")
    monkeypatch.setenv("USE_LLM_SEMANTICS", "false")

    embedding = build_embedding_provider(embedding_dim=16)
    semantic = build_semantic_provider()

    assert isinstance(embedding, DeterministicEmbeddingProvider)
    assert isinstance(semantic, ContextSemanticProvider)


def test_registry_rejects_unknown_provider_names() -> None:
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        build_embedding_provider(embedding_dim=16, provider_name="not-a-provider")
    with pytest.raises(ValueError, match="Unsupported semantic provider"):
        build_semantic_provider(provider_name="not-a-provider")


def test_registry_anthropic_embedding_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_embedding_provider(embedding_dim=8, provider_name="anthropic")


def test_registry_openai_provider_paths(monkeypatch) -> None:
    class _FakeOpenAIClient:
        def __init__(self, api_key: str | None = None) -> None:
            self.api_key = api_key

    class _FakeOpenAIModule:
        OpenAI = _FakeOpenAIClient

    monkeypatch.setattr(semantic_encoding, "openai_module", _FakeOpenAIModule())
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    embedding = build_embedding_provider(embedding_dim=16, provider_name="openai")
    semantic = build_semantic_provider(provider_name="openai")
    assert isinstance(embedding, OpenAIEmbeddingProvider)
    assert isinstance(semantic, OpenAISemanticProvider)


def test_registry_optional_provider_constructors_raise_when_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(adapters, "anthropic_module", None)
    monkeypatch.setattr(adapters, "google_genai_module", None)
    monkeypatch.setattr(adapters, "ollama_module", None)

    with pytest.raises(RuntimeError):
        build_embedding_provider(embedding_dim=8, provider_name="anthropic")
    with pytest.raises(RuntimeError):
        build_embedding_provider(embedding_dim=8, provider_name="gemini")
    with pytest.raises(RuntimeError):
        build_embedding_provider(embedding_dim=8, provider_name="ollama")
    with pytest.raises(RuntimeError):
        build_semantic_provider(provider_name="anthropic")
    with pytest.raises(RuntimeError):
        build_semantic_provider(provider_name="gemini")
    with pytest.raises(RuntimeError):
        build_semantic_provider(provider_name="ollama")
