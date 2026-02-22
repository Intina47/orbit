"""Optional provider adapters for Anthropic, Gemini, and Ollama."""

from __future__ import annotations

import json
import os
from importlib import import_module
from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from decision_engine.math_utils import to_unit_vector
from decision_engine.models import RawEvent, SemanticUnderstanding
from decision_engine.semantic_encoding import EmbeddingProvider, SemanticProvider

FloatArray = NDArray[np.float32]


def _optional_import(module_name: str) -> ModuleType | None:
    try:  # pragma: no cover - optional dependency
        return import_module(module_name)
    except ImportError:  # pragma: no cover - optional dependency
        return None


anthropic_module: ModuleType | None = _optional_import("anthropic")
google_genai_module: ModuleType | None = _optional_import("google.genai")
ollama_module: ModuleType | None = _optional_import("ollama")


def _semantic_prompts(event: RawEvent) -> tuple[str, str]:
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
    return system_prompt, user_prompt


def _strip_markdown_fences(text: str) -> str:
    value = text.strip()
    if not value.startswith("```"):
        return value
    lines = value.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = _strip_markdown_fences(raw)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        msg = "provider semantic response must be a JSON object"
        raise ValueError(msg)
    return payload


def _semantic_from_payload(
    payload: dict[str, Any], fallback_text: str
) -> SemanticUnderstanding:
    return SemanticUnderstanding(
        summary=str(payload.get("summary", fallback_text)),
        intent=str(payload.get("intent", "unknown")),
        entities=[str(item) for item in payload.get("entities", [])],
        relationships=[str(item) for item in payload.get("relationships", [])],
    )


def _coerce_embedding_dimensions(
    vector: NDArray[np.float32], dimensions: int | None
) -> NDArray[np.float32]:
    if dimensions is None or vector.shape[0] == dimensions:
        return vector
    if vector.shape[0] > dimensions:
        return vector[:dimensions]
    pad = np.zeros(dimensions - vector.shape[0], dtype=np.float32)
    return np.asarray(np.concatenate([vector, pad]), dtype=np.float32)


class AnthropicSemanticProvider(
    SemanticProvider
):  # pragma: no cover - optional dependency
    """Anthropic semantic understanding adapter."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        if anthropic_module is None:
            msg = "anthropic package is not installed. Install optional dependency 'anthropic'."
            raise RuntimeError(msg)
        client_cls = getattr(anthropic_module, "Anthropic", None)
        if client_cls is None:
            msg = "anthropic.Anthropic client class is unavailable."
            raise RuntimeError(msg)
        self._client: Any = client_cls(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        self._model = model or os.getenv(
            "MDE_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"
        )

    def understand(self, event: RawEvent) -> SemanticUnderstanding:
        system_prompt, user_prompt = _semantic_prompts(event)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content_blocks = getattr(response, "content", [])
        output_text = "".join(
            str(getattr(block, "text", "")) for block in content_blocks
        )
        payload = _parse_json_object(output_text)
        return _semantic_from_payload(payload, event.content)


class AnthropicEmbeddingProvider(
    EmbeddingProvider
):  # pragma: no cover - optional dependency
    """
    Anthropic embedding adapter.

    Anthropic SDK may not expose a dedicated embeddings endpoint in all versions.
    This adapter uses `messages.create` with a constrained JSON schema response to
    produce a dense vector of the requested dimension.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        if anthropic_module is None:
            msg = "anthropic package is not installed. Install optional dependency 'anthropic'."
            raise RuntimeError(msg)
        client_cls = getattr(anthropic_module, "Anthropic", None)
        if client_cls is None:
            msg = "anthropic.Anthropic client class is unavailable."
            raise RuntimeError(msg)
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_key:
            msg = "ANTHROPIC_API_KEY is required for Anthropic embedding provider."
            raise RuntimeError(msg)
        self._client: Any = client_cls(api_key=resolved_key)
        self._model = model or os.getenv(
            "MDE_ANTHROPIC_EMBED_MODEL",
            os.getenv("MDE_ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        )
        self._dimensions = dimensions

    def embed(self, text: str) -> FloatArray:
        target_dimensions = self._dimensions or 384
        system_prompt = (
            "You are an embedding service. Produce a dense semantic vector from text.\n"
            'Return JSON only: {"embedding": [float, ...]}.\n'
            f"The embedding list must contain exactly {target_dimensions} floats.\n"
            "Each value should be between -1.0 and 1.0."
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max(2000, target_dimensions * 8),
            system=system_prompt,
            messages=[{"role": "user", "content": text}],
        )
        content_blocks = getattr(response, "content", [])
        output_text = "".join(
            str(getattr(block, "text", "")) for block in content_blocks
        )
        payload = _parse_json_object(output_text)
        values = payload.get("embedding")
        if not isinstance(values, list):
            msg = "Anthropic embedding response missing `embedding` list."
            raise RuntimeError(msg)
        vector = np.asarray(values, dtype=np.float32)
        vector = _coerce_embedding_dimensions(vector, target_dimensions)
        return to_unit_vector(vector)


class GeminiSemanticProvider(
    SemanticProvider
):  # pragma: no cover - optional dependency
    """Gemini semantic understanding adapter."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        if google_genai_module is None:
            msg = "google-genai package is not installed. Install optional dependency 'gemini'."
            raise RuntimeError(msg)
        client_cls = getattr(google_genai_module, "Client", None)
        if client_cls is None:
            msg = "google.genai.Client class is unavailable."
            raise RuntimeError(msg)
        self._client: Any = client_cls(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        self._model = model or os.getenv(
            "MDE_GEMINI_SEMANTIC_MODEL", "gemini-2.5-flash"
        )

    def understand(self, event: RawEvent) -> SemanticUnderstanding:
        system_prompt, user_prompt = _semantic_prompts(event)
        response = self._client.models.generate_content(
            model=self._model,
            contents=[system_prompt, user_prompt],
        )
        output_text = getattr(response, "text", "") or ""
        payload = _parse_json_object(output_text)
        return _semantic_from_payload(payload, event.content)


class GeminiEmbeddingProvider(
    EmbeddingProvider
):  # pragma: no cover - optional dependency
    """Gemini embedding adapter."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        if google_genai_module is None:
            msg = "google-genai package is not installed. Install optional dependency 'gemini'."
            raise RuntimeError(msg)
        client_cls = getattr(google_genai_module, "Client", None)
        if client_cls is None:
            msg = "google.genai.Client class is unavailable."
            raise RuntimeError(msg)
        self._client: Any = client_cls(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        self._model = model or os.getenv(
            "MDE_GEMINI_EMBEDDING_MODEL", "text-embedding-004"
        )
        self._dimensions = dimensions

    def embed(self, text: str) -> FloatArray:
        response = self._client.models.embed_content(model=self._model, contents=text)
        vector_data = getattr(response, "embeddings", None)
        if vector_data and len(vector_data) > 0:
            values = getattr(vector_data[0], "values", None)
            if values is not None:
                vector = np.asarray(values, dtype=np.float32)
                return to_unit_vector(
                    _coerce_embedding_dimensions(vector, self._dimensions)
                )
        single_embedding = getattr(response, "embedding", None)
        if single_embedding is not None:
            values = getattr(single_embedding, "values", None)
            if values is not None:
                vector = np.asarray(values, dtype=np.float32)
                return to_unit_vector(
                    _coerce_embedding_dimensions(vector, self._dimensions)
                )
        msg = "Unable to parse Gemini embedding response."
        raise RuntimeError(msg)


class OllamaSemanticProvider(
    SemanticProvider
):  # pragma: no cover - optional dependency
    """Ollama semantic understanding adapter."""

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        if ollama_module is None:
            msg = (
                "ollama package is not installed. Install optional dependency 'ollama'."
            )
            raise RuntimeError(msg)
        client_cls = getattr(ollama_module, "Client", None)
        if client_cls is None:
            msg = "ollama.Client class is unavailable."
            raise RuntimeError(msg)
        self._client: Any = client_cls(host=host or os.getenv("MDE_OLLAMA_HOST"))
        self._model = model or os.getenv("MDE_OLLAMA_SEMANTIC_MODEL", "llama3.1")

    def understand(self, event: RawEvent) -> SemanticUnderstanding:
        system_prompt, user_prompt = _semantic_prompts(event)
        response = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format="json",
        )
        message = response.get("message", {})
        output_text = str(message.get("content", ""))
        payload = _parse_json_object(output_text)
        return _semantic_from_payload(payload, event.content)


class OllamaEmbeddingProvider(
    EmbeddingProvider
):  # pragma: no cover - optional dependency
    """Ollama embedding adapter."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        if ollama_module is None:
            msg = (
                "ollama package is not installed. Install optional dependency 'ollama'."
            )
            raise RuntimeError(msg)
        client_cls = getattr(ollama_module, "Client", None)
        if client_cls is None:
            msg = "ollama.Client class is unavailable."
            raise RuntimeError(msg)
        self._client: Any = client_cls(host=host or os.getenv("MDE_OLLAMA_HOST"))
        self._model = model or os.getenv(
            "MDE_OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
        )
        self._dimensions = dimensions

    def embed(self, text: str) -> FloatArray:
        if hasattr(self._client, "embeddings"):
            response = self._client.embeddings(model=self._model, prompt=text)
            values = response.get("embedding")
        elif hasattr(self._client, "embed"):
            response = self._client.embed(model=self._model, input=text)
            embeddings = response.get("embeddings", [])
            values = embeddings[0] if embeddings else None
        else:
            msg = "No embedding method available on Ollama client."
            raise RuntimeError(msg)

        if values is None:
            msg = "Unable to parse Ollama embedding response."
            raise RuntimeError(msg)
        vector = np.asarray(values, dtype=np.float32)
        vector = _coerce_embedding_dimensions(vector, self._dimensions)
        return to_unit_vector(vector)
