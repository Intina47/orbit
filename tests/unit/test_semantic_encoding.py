from __future__ import annotations

import numpy as np

from decision_engine.models import RawEvent
from decision_engine.semantic_encoding import (
    ContextSemanticProvider,
    DeterministicEmbeddingProvider,
    SemanticEncoder,
)


def test_semantic_encoder_outputs_expected_shapes() -> None:
    embedding_provider = DeterministicEmbeddingProvider(embedding_dim=16)
    semantic_provider = ContextSemanticProvider()
    encoder = SemanticEncoder(embedding_provider, semantic_provider)

    event = RawEvent(
        content="User reported latency spike in checkout API",
        context={
            "summary": "Latency spike report",
            "intent": "incident_report",
            "entities": ["service:checkout"],
            "relationships": ["user->service:checkout"],
        },
    )

    encoded = encoder.encode_event(event)
    assert len(encoded.raw_embedding) == 16
    assert len(encoded.semantic_embedding) == 16
    assert encoded.understanding.intent == "incident_report"
    assert encoded.understanding.entities == ["service:checkout"]

    query_embedding = encoder.encode_query("checkout latency")
    assert isinstance(query_embedding, np.ndarray)
    assert query_embedding.shape == (16,)
