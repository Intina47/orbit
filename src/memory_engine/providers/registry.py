"""Central provider registry for embedding and semantic adapters."""

from __future__ import annotations

import os

from decision_engine.semantic_encoding import (
    ContextSemanticProvider,
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
    OpenAISemanticProvider,
    SemanticProvider,
)
from memory_engine.providers.adapters import (
    AnthropicEmbeddingProvider,
    AnthropicSemanticProvider,
    GeminiEmbeddingProvider,
    GeminiSemanticProvider,
    OllamaEmbeddingProvider,
    OllamaSemanticProvider,
)

EmbeddingProviderName = str
SemanticProviderName = str

_EMBEDDING_ALIASES: dict[str, EmbeddingProviderName] = {
    "default": "deterministic",
    "local": "deterministic",
    "hash": "deterministic",
}

_SEMANTIC_ALIASES: dict[str, SemanticProviderName] = {
    "default": "context",
    "local": "context",
    "heuristic": "context",
}


class _FallbackEmbeddingProvider(EmbeddingProvider):
    """Fallback wrapper that degrades to deterministic embeddings on provider errors."""

    def __init__(
        self,
        primary: EmbeddingProvider,
        fallback: EmbeddingProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_unavailable = False

    def embed(self, text: str):
        if self._primary_unavailable:
            return self._fallback.embed(text)
        try:
            return self._primary.embed(text)
        except Exception:
            self._primary_unavailable = True
            return self._fallback.embed(text)


def build_embedding_provider(
    embedding_dim: int,
    provider_name: str | None = None,
) -> EmbeddingProvider:
    """Build an embedding provider from explicit name or environment."""

    resolved = _resolve_embedding_provider_name(provider_name)
    deterministic_fallback = DeterministicEmbeddingProvider(embedding_dim=embedding_dim)
    fallback_enabled = _embedding_fallback_enabled()
    if resolved == "deterministic":
        return deterministic_fallback
    primary: EmbeddingProvider
    if resolved == "openai":
        model = os.getenv(
            "MDE_OPENAI_EMBEDDING_MODEL",
            os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
        factory = lambda: OpenAIEmbeddingProvider(
            model=model,
            api_key=os.getenv("OPENAI_API_KEY"),
            dimensions=embedding_dim,
        )
    elif resolved == "anthropic":
        factory = lambda: AnthropicEmbeddingProvider(
            model=os.getenv("MDE_ANTHROPIC_EMBED_MODEL"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            dimensions=embedding_dim,
        )
    elif resolved == "gemini":
        factory = lambda: GeminiEmbeddingProvider(
            model=os.getenv("MDE_GEMINI_EMBEDDING_MODEL"),
            api_key=os.getenv("GEMINI_API_KEY"),
            dimensions=embedding_dim,
        )
    elif resolved == "ollama":
        factory = lambda: OllamaEmbeddingProvider(
            model=os.getenv("MDE_OLLAMA_EMBEDDING_MODEL"),
            host=os.getenv("MDE_OLLAMA_HOST"),
            dimensions=embedding_dim,
        )
    else:
        msg = f"Unsupported embedding provider: {resolved}"
        raise ValueError(msg)

    try:
        primary = factory()
    except Exception:
        if fallback_enabled:
            return deterministic_fallback
        raise
    if fallback_enabled:
        return _FallbackEmbeddingProvider(primary=primary, fallback=deterministic_fallback)
    return primary


def build_semantic_provider(
    provider_name: str | None = None,
    force_openai: bool = False,
) -> SemanticProvider:
    """Build a semantic provider from explicit name or environment."""

    resolved = _resolve_semantic_provider_name(provider_name, force_openai=force_openai)
    if resolved == "context":
        return ContextSemanticProvider()
    if resolved == "openai":
        return OpenAISemanticProvider(
            model=os.getenv("MDE_OPENAI_SEMANTIC_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    if resolved == "anthropic":
        return AnthropicSemanticProvider(
            model=os.getenv("MDE_ANTHROPIC_MODEL"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
    if resolved == "gemini":
        return GeminiSemanticProvider(
            model=os.getenv("MDE_GEMINI_SEMANTIC_MODEL"),
            api_key=os.getenv("GEMINI_API_KEY"),
        )
    if resolved == "ollama":
        return OllamaSemanticProvider(
            model=os.getenv("MDE_OLLAMA_SEMANTIC_MODEL"),
            host=os.getenv("MDE_OLLAMA_HOST"),
        )
    msg = f"Unsupported semantic provider: {resolved}"
    raise ValueError(msg)


def _resolve_embedding_provider_name(provider_name: str | None) -> str:
    if provider_name:
        return _normalize(provider_name, _EMBEDDING_ALIASES)
    configured = os.getenv("MDE_EMBEDDING_PROVIDER")
    if configured:
        return _normalize(configured, _EMBEDDING_ALIASES)
    use_openai = os.getenv("OPENAI_API_KEY") is not None and os.getenv(
        "USE_LOCAL_EMBEDDINGS", "true"
    ).lower() in {"false", "0", "no"}
    if use_openai:
        return "openai"
    return "deterministic"


def _resolve_semantic_provider_name(
    provider_name: str | None,
    force_openai: bool = False,
) -> str:
    if provider_name:
        return _normalize(provider_name, _SEMANTIC_ALIASES)
    configured = os.getenv("MDE_SEMANTIC_PROVIDER")
    if configured:
        return _normalize(configured, _SEMANTIC_ALIASES)
    if force_openai:
        return "openai"
    use_openai = os.getenv("USE_LLM_SEMANTICS", "false").lower() in {"true", "1", "yes"}
    if use_openai:
        return "openai"
    return "context"


def _normalize(name: str, aliases: dict[str, str]) -> str:
    key = name.strip().lower()
    return aliases.get(key, key)


def _embedding_fallback_enabled() -> bool:
    return os.getenv("MDE_EMBEDDING_FALLBACK_TO_DETERMINISTIC", "true").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
