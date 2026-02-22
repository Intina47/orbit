from __future__ import annotations

import hashlib
import json
from types import ModuleType
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from decision_engine.math_utils import to_unit_vector
from decision_engine.models import EncodedEvent, RawEvent, SemanticUnderstanding

openai_module: ModuleType | None
try:
    import openai as openai_module
except ImportError:  # pragma: no cover - optional dependency at runtime
    openai_module = None

FloatArray = NDArray[np.float32]


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> FloatArray:
        """Return a dense embedding for input text."""


class SemanticProvider(Protocol):
    def understand(self, event: RawEvent) -> SemanticUnderstanding:
        """Return semantic understanding for an event."""


class DeterministicEmbeddingProvider:
    """
    Local deterministic embedding provider for tests and offline development.

    This is not a production semantic model. It only guarantees stable vectors.
    """

    def __init__(self, embedding_dim: int) -> None:
        self._embedding_dim = embedding_dim

    def embed(self, text: str) -> FloatArray:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        seed = int(digest[:16], 16)
        rng = np.random.default_rng(seed)
        vector = rng.standard_normal(self._embedding_dim).astype(np.float32)
        return to_unit_vector(vector)


class OpenAIEmbeddingProvider:  # pragma: no cover - requires external API access
    """Embedding provider backed by OpenAI embeddings API."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        if openai_module is None:
            msg = "openai package is not installed"
            raise RuntimeError(msg)
        client_cls = getattr(openai_module, "OpenAI", None)
        if client_cls is None:
            msg = "openai.OpenAI client class is not available"
            raise RuntimeError(msg)
        self._client: Any = client_cls(api_key=api_key)
        self._model = model
        self._dimensions = dimensions

    def embed(self, text: str) -> FloatArray:
        kwargs: dict[str, Any] = {"model": self._model, "input": text}
        if self._dimensions is not None:
            kwargs["dimensions"] = self._dimensions
        response = self._client.embeddings.create(**kwargs)
        vector = np.array(response.data[0].embedding, dtype=np.float32)
        return to_unit_vector(vector)


class ContextSemanticProvider:
    """
    Semantic provider that reads structured context from the event.

    Useful for tests where semantic labels are provided by fixtures.
    """

    def understand(self, event: RawEvent) -> SemanticUnderstanding:
        entities = [str(item) for item in event.context.get("entities", [])]
        relationships = [str(item) for item in event.context.get("relationships", [])]
        intent = str(event.context.get("intent", "unknown"))
        summary = str(event.context.get("summary", event.content))
        return SemanticUnderstanding(
            summary=summary,
            entities=entities,
            relationships=relationships,
            intent=intent,
        )


class OpenAISemanticProvider:  # pragma: no cover - requires external API access
    """Semantic understanding via an LLM response in strict JSON format."""

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None) -> None:
        if openai_module is None:
            msg = "openai package is not installed"
            raise RuntimeError(msg)
        client_cls = getattr(openai_module, "OpenAI", None)
        if client_cls is None:
            msg = "openai.OpenAI client class is not available"
            raise RuntimeError(msg)
        self._client: Any = client_cls(api_key=api_key)
        self._model = model

    def understand(self, event: RawEvent) -> SemanticUnderstanding:
        system_prompt = (
            "You extract semantic meaning from engineering events.\n"
            "Return only JSON with keys: summary, intent, entities, relationships.\n"
            "entities and relationships must be arrays of strings."
        )
        user_prompt = (
            "Event content:\n"
            f"{event.content}\n\n"
            f"Event context JSON:\n{json.dumps(event.context, ensure_ascii=True)}"
        )
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        output_text = getattr(response, "output_text", "")
        payload = _load_json_object(output_text)
        return SemanticUnderstanding(
            summary=str(payload.get("summary", event.content)),
            intent=str(payload.get("intent", "unknown")),
            entities=[str(item) for item in payload.get("entities", [])],
            relationships=[str(item) for item in payload.get("relationships", [])],
        )


class SemanticEncoder:
    """Combine embeddings and semantic understanding into encoded events."""

    _MAX_SEMANTIC_CONTENT_CHARS = 800
    _MAX_SEMANTIC_SUMMARY_CHARS = 280

    def __init__(
        self, embedding_provider: EmbeddingProvider, semantic_provider: SemanticProvider
    ) -> None:
        self._embedding_provider = embedding_provider
        self._semantic_provider = semantic_provider

    def encode_event(self, event: RawEvent) -> EncodedEvent:
        understanding = self._semantic_provider.understand(event)
        raw_embedding = self._embedding_provider.embed(event.content)
        semantic_text = self._build_semantic_text(event, understanding)
        semantic_embedding = self._embedding_provider.embed(semantic_text)
        semantic_key = self._semantic_key(understanding)
        return EncodedEvent(
            event=event,
            raw_embedding=raw_embedding.tolist(),
            semantic_embedding=semantic_embedding.tolist(),
            understanding=understanding,
            semantic_key=semantic_key,
        )

    def encode_query(self, query: str) -> FloatArray:
        return self._embedding_provider.embed(query)

    @staticmethod
    def _build_semantic_text(
        event: RawEvent, understanding: SemanticUnderstanding
    ) -> str:
        summary = SemanticEncoder._clip_text(
            understanding.summary, max_chars=SemanticEncoder._MAX_SEMANTIC_SUMMARY_CHARS
        )
        content = SemanticEncoder._clip_text(
            event.content, max_chars=SemanticEncoder._MAX_SEMANTIC_CONTENT_CHARS
        )
        parts = [
            summary,
            f"intent:{understanding.intent}",
            f"entities:{','.join(understanding.entities)}",
            f"relationships:{','.join(understanding.relationships)}",
            f"content:{content}",
        ]
        return "\n".join(parts)

    @staticmethod
    def _semantic_key(understanding: SemanticUnderstanding) -> str:
        summary_key = SemanticEncoder._clip_text(
            understanding.summary, max_chars=SemanticEncoder._MAX_SEMANTIC_SUMMARY_CHARS
        )
        key_source = "|".join(
            [
                understanding.intent.lower(),
                summary_key.lower(),
                ",".join(sorted(entity.lower() for entity in understanding.entities)),
            ]
        )
        return hashlib.sha256(key_source.encode("utf-8")).hexdigest()

    @staticmethod
    def _clip_text(value: str, max_chars: int) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= max_chars:
            return normalized
        if max_chars <= 3:
            return normalized[:max_chars]
        return normalized[: max_chars - 3].rstrip() + "..."


def _load_json_object(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        msg = "LLM response was not valid JSON"
        raise ValueError(msg) from exc
    if not isinstance(payload, dict):
        msg = "LLM response must be a JSON object"
        raise ValueError(msg)
    return payload
