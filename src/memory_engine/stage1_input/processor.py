from __future__ import annotations

import re

from decision_engine.models import EncodedEvent, RawEvent, SemanticUnderstanding
from decision_engine.semantic_encoding import (
    EmbeddingProvider,
    SemanticEncoder,
    SemanticProvider,
)
from memory_engine.models.event import Event
from memory_engine.models.processed_event import ProcessedEvent


class InputProcessor:
    """Stage 1 input processor: schema validation + semantic encoding."""

    def __init__(
        self, embedding_provider: EmbeddingProvider, semantic_provider: SemanticProvider
    ) -> None:
        self.encoder = SemanticEncoder(embedding_provider, semantic_provider)

    def process(self, event: Event) -> ProcessedEvent:
        raw_event = self.to_raw_event(event)
        encoded = self.encoder.encode_event(raw_event)
        entity_references = list(
            dict.fromkeys([event.entity_id] + encoded.understanding.entities)
        )
        return ProcessedEvent(
            event_id=raw_event.event_id,
            timestamp=raw_event.timestamp,
            entity_id=event.entity_id,
            event_type=event.event_type,
            description=event.description,
            entity_references=entity_references,
            embedding=encoded.raw_embedding,
            semantic_embedding=encoded.semantic_embedding,
            intent=encoded.understanding.intent,
            semantic_key=encoded.semantic_key,
            semantic_summary=encoded.understanding.summary,
            context=event.metadata,
        )

    def to_encoded_event(self, processed: ProcessedEvent) -> EncodedEvent:
        raw_event = RawEvent(
            event_id=processed.event_id,
            timestamp=processed.timestamp,
            content=processed.description,
            context={
                "summary": processed.semantic_summary,
                "intent": processed.intent,
                "entities": processed.entity_references,
                "relationships": processed.context.get("relationships", []),
                "event_type": processed.event_type,
                **processed.context,
            },
        )
        understanding = SemanticUnderstanding(
            summary=processed.semantic_summary,
            entities=processed.entity_references,
            relationships=[
                str(value) for value in processed.context.get("relationships", [])
            ],
            intent=processed.intent,
        )
        return EncodedEvent(
            event=raw_event,
            raw_embedding=processed.embedding,
            semantic_embedding=processed.semantic_embedding,
            understanding=understanding,
            semantic_key=processed.semantic_key,
        )

    @staticmethod
    def to_raw_event(event: Event) -> RawEvent:
        summary_value = event.metadata.get("summary")
        if summary_value is None:
            summary = InputProcessor._default_summary(event.description, event.event_type)
        else:
            summary = str(summary_value).strip() or InputProcessor._default_summary(
                event.description, event.event_type
            )
        context = {
            "summary": summary,
            "intent": str(event.metadata.get("intent", event.event_type)),
            "entities": [
                event.entity_id,
                *[str(item) for item in event.metadata.get("entities", [])],
            ],
            "relationships": [
                str(item) for item in event.metadata.get("relationships", [])
            ],
            "event_type": event.event_type,
            **event.metadata,
        }
        return RawEvent(
            timestamp=event.as_datetime(), content=event.description, context=context
        )

    @staticmethod
    def _default_summary(description: str, event_type: str) -> str:
        normalized = " ".join(description.split())
        if event_type.strip().lower() == "assistant_response":
            normalized = re.sub(
                r"^\s*assistant\s+response\s*:\s*",
                "",
                normalized,
                flags=re.IGNORECASE,
            )
        if not normalized:
            return ""
        first_sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0]
        candidate = first_sentence if first_sentence else normalized
        words = candidate.split()
        if len(words) > 32:
            candidate = " ".join(words[:32]).rstrip(".,;:") + "..."
        if len(candidate) > 220:
            candidate = candidate[:217].rstrip() + "..."
        return candidate
