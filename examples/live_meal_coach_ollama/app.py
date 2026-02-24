from __future__ import annotations

import os
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from examples._env import load_env_file
from orbit import MemoryEngine

try:
    from ollama import Client as OllamaClient
except ImportError as exc:  # pragma: no cover - optional runtime dependency
    raise RuntimeError("Install 'ollama' package to run meal coach example.") from exc


class ChatMode(str, Enum):
    BASELINE = "baseline"
    ORBIT = "orbit"


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    mode: ChatMode = ChatMode.ORBIT


class ChatResponse(BaseModel):
    mode: ChatMode
    response: str
    context_items: int
    context_preview: list[str]
    memory_ids: list[str]
    note: str | None = None


class FeedbackRequest(BaseModel):
    memory_id: str = Field(min_length=1)
    helpful: bool
    outcome_value: float | None = None


class SeedProfileRequest(BaseModel):
    user_id: str = Field(min_length=1)
    goals: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    preferred_cuisines: list[str] = Field(default_factory=list)
    budget: str | None = None
    cooking_level: str | None = None
    extra_notes: str | None = None


class SeedProfileResponse(BaseModel):
    events_written: int


class ContextRequest(BaseModel):
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class ContextMemory(BaseModel):
    memory_id: str
    event_type: str
    rank_position: int
    rank_score: float
    importance_score: float
    intent: str
    summary: str
    content: str
    inference_provenance: dict[str, Any] | None = None


class ContextResponse(BaseModel):
    total_candidates: int
    query_execution_time_ms: float
    memories: list[ContextMemory]


class ResetRequest(BaseModel):
    user_id: str = Field(min_length=1)


class ResetResponse(BaseModel):
    baseline_cleared: bool
    note: str


APP_TITLE = "Orbit + Ollama Personalized Meal Coach"
UI_FILE = Path(__file__).with_name("index.html")
load_env_file(start=Path(__file__).resolve().parent)

ORBIT_TOKEN = os.getenv("ORBIT_JWT_TOKEN", "")
ORBIT_API_BASE_URL = os.getenv("ORBIT_API_BASE_URL", "http://localhost:8000")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
BASELINE_HISTORY_MAX_ITEMS = int(os.getenv("MEAL_COACH_BASELINE_ITEMS", "12"))
ORBIT_RETRIEVE_LIMIT = int(os.getenv("MEAL_COACH_ORBIT_LIMIT", "5"))


orbit: MemoryEngine | None = None
if ORBIT_TOKEN:
    orbit = MemoryEngine(api_key=ORBIT_TOKEN, base_url=ORBIT_API_BASE_URL)

ollama_client = OllamaClient(host=OLLAMA_HOST)
baseline_history: dict[str, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=BASELINE_HISTORY_MAX_ITEMS)
)

app = FastAPI(title=APP_TITLE)


def _require_orbit() -> MemoryEngine:
    if orbit is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Orbit mode is not configured. Set ORBIT_JWT_TOKEN in .env "
                "(and optionally ORBIT_API_BASE_URL) to enable memory mode."
            ),
        )
    return orbit


def _ask_ollama(system_prompt: str, message: str) -> str:
    response: dict[str, Any] = ollama_client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )
    answer = str(response.get("message", {}).get("content", "")).strip()
    if not answer:
        raise HTTPException(status_code=502, detail="Ollama returned an empty response.")
    return answer


def _build_baseline_prompt(user_id: str) -> tuple[str, list[str]]:
    history = list(baseline_history[user_id])
    snippets = [f"{entry['role'].title()}: {entry['content']}" for entry in history[-6:]]
    system_prompt = (
        "You are a practical meal coach for everyday users. "
        "Give clear meal ideas, quick recipes, and shopping tips. "
        "Ask one clarifying question when needed."
    )
    if snippets:
        system_prompt += "\n\nRecent chat context:\n" + "\n".join(snippets)
    return system_prompt, snippets


def _build_orbit_prompt(user_id: str, message: str) -> tuple[str, list[str], list[str]]:
    engine = _require_orbit()

    engine.ingest(
        content=message,
        event_type="user_question",
        entity_id=user_id,
        metadata={"domain": "meal_coach", "model": OLLAMA_MODEL},
    )

    retrieval = engine.retrieve(
        query=(
            f"What should I know about {user_id} to personalize meal coaching for: {message}"
        ),
        entity_id=user_id,
        limit=max(1, ORBIT_RETRIEVE_LIMIT),
    )

    context_lines: list[str] = []
    context_preview: list[str] = []
    memory_ids: list[str] = []
    for item in retrieval.memories:
        metadata = dict(item.metadata or {})
        intent = str(metadata.get("intent", item.event_type))
        summary = str(metadata.get("summary", "")).strip()
        rendered = f"[{intent}] {item.content}"
        context_lines.append(f"- {rendered}")
        context_preview.append(summary or item.content)
        memory_ids.append(item.memory_id)

    system_prompt = (
        "You are a practical meal coach for everyday users. "
        "Use memory context to personalize recommendations. "
        "Honor allergies and dislikes strictly."
    )
    if context_lines:
        system_prompt += "\n\nUser memory context:\n" + "\n".join(context_lines)

    return system_prompt, context_preview, memory_ids


@app.get("/", response_class=HTMLResponse)
def ui() -> str:
    if not UI_FILE.exists():
        raise HTTPException(status_code=500, detail=f"UI file not found: {UI_FILE}")
    return UI_FILE.read_text(encoding="utf-8")


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    if payload.mode == ChatMode.BASELINE:
        system_prompt, preview = _build_baseline_prompt(payload.user_id)
        answer = _ask_ollama(system_prompt=system_prompt, message=payload.message)
        baseline_history[payload.user_id].append({"role": "user", "content": payload.message})
        baseline_history[payload.user_id].append({"role": "assistant", "content": answer})
        return ChatResponse(
            mode=payload.mode,
            response=answer,
            context_items=len(preview),
            context_preview=preview,
            memory_ids=[],
            note="Baseline mode only uses local recent chat context.",
        )

    system_prompt, preview, memory_ids = _build_orbit_prompt(
        user_id=payload.user_id,
        message=payload.message,
    )
    answer = _ask_ollama(system_prompt=system_prompt, message=payload.message)

    engine = _require_orbit()
    engine.ingest(
        content=answer,
        event_type="assistant_response",
        entity_id=payload.user_id,
        metadata={"domain": "meal_coach", "model": OLLAMA_MODEL, "mode": payload.mode.value},
    )

    return ChatResponse(
        mode=payload.mode,
        response=answer,
        context_items=len(preview),
        context_preview=preview,
        memory_ids=memory_ids,
        note="Orbit mode uses persistent memory retrieval.",
    )


@app.post("/feedback")
def feedback(payload: FeedbackRequest) -> dict[str, bool]:
    engine = _require_orbit()
    engine.feedback(
        memory_id=payload.memory_id,
        helpful=payload.helpful,
        outcome_value=payload.outcome_value,
    )
    return {"recorded": True}


@app.post("/seed-profile", response_model=SeedProfileResponse)
def seed_profile(payload: SeedProfileRequest) -> SeedProfileResponse:
    engine = _require_orbit()
    facts: list[str] = []

    facts.extend(f"Goal: {goal.strip()}" for goal in payload.goals if goal.strip())
    facts.extend(f"Allergy: {allergy.strip()}" for allergy in payload.allergies if allergy.strip())
    facts.extend(f"Dislike: {dislike.strip()}" for dislike in payload.dislikes if dislike.strip())
    facts.extend(
        f"Preferred cuisine: {cuisine.strip()}"
        for cuisine in payload.preferred_cuisines
        if cuisine.strip()
    )
    if payload.budget and payload.budget.strip():
        facts.append(f"Budget preference: {payload.budget.strip()}")
    if payload.cooking_level and payload.cooking_level.strip():
        facts.append(f"Cooking level: {payload.cooking_level.strip()}")
    if payload.extra_notes and payload.extra_notes.strip():
        facts.append(f"Note: {payload.extra_notes.strip()}")

    for fact in facts:
        engine.ingest(
            content=fact,
            event_type="preference_stated",
            entity_id=payload.user_id,
            metadata={"source": "seed_profile", "domain": "meal_coach"},
        )

    return SeedProfileResponse(events_written=len(facts))


@app.post("/context", response_model=ContextResponse)
def context(payload: ContextRequest) -> ContextResponse:
    engine = _require_orbit()
    results = engine.retrieve(
        query=payload.query,
        entity_id=payload.user_id,
        limit=payload.limit,
    )

    output: list[ContextMemory] = []
    for item in results.memories:
        metadata = dict(item.metadata or {})
        output.append(
            ContextMemory(
                memory_id=item.memory_id,
                event_type=item.event_type,
                rank_position=item.rank_position,
                rank_score=item.rank_score,
                importance_score=item.importance_score,
                intent=str(metadata.get("intent", item.event_type)),
                summary=str(metadata.get("summary", "")),
                content=item.content,
                inference_provenance=metadata.get("inference_provenance"),
            )
        )

    return ContextResponse(
        total_candidates=results.total_candidates,
        query_execution_time_ms=results.query_execution_time_ms,
        memories=output,
    )


@app.post("/reset", response_model=ResetResponse)
def reset(payload: ResetRequest) -> ResetResponse:
    cleared = payload.user_id in baseline_history
    baseline_history.pop(payload.user_id, None)
    return ResetResponse(
        baseline_cleared=cleared,
        note=(
            "Baseline chat history cleared. Orbit memories persist in the Orbit store; "
            "clear them via database reset if needed."
        ),
    )
