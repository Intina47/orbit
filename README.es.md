# Orbit

Infraestructura de memoria para aplicaciones de IA dirigidas a desarrolladores.

Orbit guarda tus señales de usuario a largo plazo mediante personalización adaptativa, ranking relevante y aprendizaje a través de feedback.  
El flujo esencial se mantiene: `ingest -> retrieve -> feedback`.

Estado del proyecto: `Alpha` (`0.1.x`)

## Inicio rápido (5 minutos)

### 1) Instalar

```bash
pip install orbit-memory
```

También puedes instalar desde el repositorio local:

```bash
pip install -e .
```

### 2) Levantar la API localmente

```bash
docker compose up --build
```

Esto arranca API, Postgres, Prometheus, Alertmanager y el colector OpenTelemetry.

### 3) Generar un JWT local

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

### 4) Integrar con el SDK

```python
from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>", base_url="http://localhost:8000")

engine.ingest(
    content="Sigo confundiendo los for loops con los while loops.",
    event_type="user_question",
    entity_id="alice",
)

retrieval = engine.retrieve(
    query="¿Qué debo saber sobre Alice antes de responderle?",
    entity_id="alice",
    limit=5,
)

if retrieval.memories:
    engine.feedback(
        memory_id=retrieval.memories[0].memory_id,
        helpful=True,
        outcome_value=1.0,
    )
```

## Caminos de integración

| Modo | Ideal para | Entrada |
| --- | --- | --- |
| SDK Python | Aplicaciones Python que buscan la ruta más rápida | `from orbit import MemoryEngine` |
| API REST | Integraciones en otros idiomas o servicios | `POST /v1/ingest`, `GET /v1/retrieve`, `POST /v1/feedback` |
| Node.js (sin SDK) | Apps JavaScript usando HTTP directo y llaves | `examples/nodejs_orbit_api_chatbot/` |
| Plugin OpenClaw | Flujos de agentes en OpenClaw | `integrations/openclaw-memory/` |

## Conceptos clave

| Concepto | Descripción |
| --- | --- |
| `entity_id` | Identificador estable de usuario, agente o cuenta |
| `ingest` | Agrega una señal de memoria (`user_question`, `assistant_response`, etc.) |
| `retrieve` | Recupera contexto ordenado para una consulta |
| `feedback` | Envía la calidad del resultado (`helpful`, `outcome_value`) |
| memoria inferida | Memoria generada automáticamente por patrones repetidos |
| procedencia inferencial | Metadatos `why/when/type/derived_from` para trazabilidad |
