"""Provider registry and adapters for embedding/semantic model backends."""

from memory_engine.providers.registry import (
    build_embedding_provider,
    build_semantic_provider,
)

__all__ = ["build_embedding_provider", "build_semantic_provider"]
