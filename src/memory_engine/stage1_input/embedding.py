from __future__ import annotations

from decision_engine.semantic_encoding import EmbeddingProvider
from memory_engine.providers.registry import (
    build_embedding_provider as _build_from_registry,
)


def build_embedding_provider(
    embedding_dim: int,
    provider_name: str | None = None,
) -> EmbeddingProvider:
    """Build embedding provider from environment config."""

    return _build_from_registry(
        embedding_dim=embedding_dim, provider_name=provider_name
    )
