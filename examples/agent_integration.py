"""FastAPI + Orbit integration example."""

from __future__ import annotations

from fastapi import FastAPI
from openai import OpenAI

from orbit import MemoryEngine

app = FastAPI()
orbit = MemoryEngine(api_key="<jwt-token>")
openai_client = OpenAI(api_key="sk-your-key")


@app.post("/chat")
async def chat(user_id: str, message: str) -> dict[str, str]:
    orbit.ingest(
        content=message,
        event_type="user_question",
        entity_id=user_id,
    )
    memories = orbit.retrieve(
        query=f"What should I know about {user_id} to help with: {message}?",
        entity_id=user_id,
        limit=5,
    )
    memory_lines = "\n".join(f"- {memory.content}" for memory in memories.memories)
    system_prompt = (
        "You are a coding tutor. Here is what you know about this user:\n"
        f"{memory_lines}\n\n"
        f"Help with: {message}"
    )
    response = openai_client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    )
    answer = response.output_text
    orbit.ingest(
        content=f"Assistant response to '{message}': {answer}",
        event_type="assistant_response",
        entity_id=user_id,
        metadata={"model": "gpt-4.1-mini"},
    )
    return {"response": answer}
