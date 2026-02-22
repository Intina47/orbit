from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from orbit import MemoryEngine

try:
    from ollama import Client as OllamaClient
except ImportError as exc:  # pragma: no cover - optional local runtime dependency
    raise RuntimeError(
        "Install ollama Python package to run live chatbot example."
    ) from exc

app = FastAPI(title="Orbit + Ollama Coding Tutor")
UI_FILE = Path(__file__).with_name("index.html")

ORBIT_TOKEN = os.getenv("ORBIT_JWT_TOKEN", "")
if not ORBIT_TOKEN:
    raise RuntimeError("Set ORBIT_JWT_TOKEN to a valid Orbit JWT token.")

orbit = MemoryEngine(
    api_key=ORBIT_TOKEN,
    base_url=os.getenv("ORBIT_API_BASE_URL", "http://localhost:8000"),
)
ollama_client = OllamaClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    response: str
    context_items: int
    memory_ids: list[str]


class FeedbackRequest(BaseModel):
    memory_id: str = Field(min_length=1)
    helpful: bool
    outcome_value: float | None = None


class ContextRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class ContextMemory(BaseModel):
    memory_id: str
    rank_position: int
    rank_score: float
    importance_score: float
    intent: str
    summary: str
    content: str


class ContextResponse(BaseModel):
    total_candidates: int
    query_execution_time_ms: float
    memories: list[ContextMemory]


@app.get("/", response_class=HTMLResponse)
def ui() -> str:
    if not UI_FILE.exists():
        msg = f"UI file not found: {UI_FILE}"
        raise HTTPException(status_code=500, detail=msg)
    return UI_FILE.read_text(encoding="utf-8")


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    orbit.ingest(
        content=payload.message,
        event_type="user_question",
        entity_id=payload.user_id,
    )

    memories = orbit.retrieve(
        query=f"What should I know about {payload.user_id} to answer: {payload.message}",
        entity_id=payload.user_id,
        limit=5,
    )
    memory_lines = "\n".join(f"- {item.content}" for item in memories.memories)
    system_prompt = (
        "You are a coding tutor.\n"
        "Use the user memory context to personalize teaching style.\n\n"
        f"Memory context:\n{memory_lines}\n"
    )
    ollama_response: dict[str, Any] = ollama_client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.message},
        ],
    )
    answer = str(ollama_response.get("message", {}).get("content", "")).strip()
    if not answer:
        raise HTTPException(status_code=502, detail="Ollama returned empty response.")

    orbit.ingest(
        content=f"Assistant response: {answer}",
        event_type="assistant_response",
        entity_id=payload.user_id,
        metadata={"model": OLLAMA_MODEL},
    )

    return ChatResponse(
        response=answer,
        context_items=len(memories.memories),
        memory_ids=[item.memory_id for item in memories.memories],
    )


@app.post("/feedback")
def feedback(payload: FeedbackRequest) -> dict[str, bool]:
    orbit.feedback(
        memory_id=payload.memory_id,
        helpful=payload.helpful,
        outcome_value=payload.outcome_value,
    )
    return {"recorded": True}


@app.post("/context", response_model=ContextResponse)
def context(payload: ContextRequest) -> ContextResponse:
    results = orbit.retrieve(
        query=payload.query,
        entity_id=payload.user_id,
        limit=payload.limit,
    )
    output = []
    for item in results.memories:
        output.append(
            ContextMemory(
                memory_id=item.memory_id,
                rank_position=item.rank_position,
                rank_score=item.rank_score,
                importance_score=item.importance_score,
                intent=str(item.metadata.get("intent", "unknown")),
                summary=str(item.metadata.get("summary", "")),
                content=item.content,
            )
        )
    return ContextResponse(
        total_candidates=results.total_candidates,
        query_execution_time_ms=results.query_execution_time_ms,
        memories=output,
    )
