# Orbit

Gedächtnisinfrastruktur für Entwickler-centrische KI-Anwendungen.

Orbit liefert langzeitiges Nutzergedächtnis über adaptive Personalisierung, Relevanzrankings und Feedback.
Der Loop bleibt überall gleich: `ingest -> retrieve -> feedback`.

Projektstatus: `Alpha` (`0.1.x`)

## Schnellstart (5 Minuten)

### 1) Installieren

```bash
pip install orbit-memory
```

oder für lokale Entwicklung:

```bash
pip install -e .
```

### 2) Lokale Orbit API starten

```bash
docker compose up --build
```

Damit laufen API, Postgres, Prometheus, Alertmanager und OpenTelemetry.

### 3) Lokalen JWT erzeugen

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

### 4) SDK integrieren

```python
from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>", base_url="http://localhost:8000")

engine.ingest(
    content="Ich verwechsle immer noch for-Schleifen mit while-Schleifen.",
    event_type="user_question",
    entity_id="alice",
)

retrieval = engine.retrieve(
    query="Was muss ich über Alice wissen, bevor ich antworte?",
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

## Integrationswege

| Modus | Besonders geeignet für | Einstieg |
| --- | --- | --- |
| Python SDK | Python-Apps, die schnell integrieren wollen | `from orbit import MemoryEngine` |
| REST API | Andere Laufzeiten oder serviceübergreifende Integration | `POST /v1/ingest`, `GET /v1/retrieve`, `POST /v1/feedback` |
| Node.js (ohne SDK) | JavaScript-Apps mit direktem HTTP + API-Key | `examples/nodejs_orbit_api_chatbot/` |
| OpenClaw Plugin | Agenten-Workflows in OpenClaw | `integrations/openclaw-memory/` |

## Kernkonzepte

| Konzept | Beschreibung |
| --- | --- |
| `entity_id` | Stabiler Identifikator für Nutzer/Agenten/Konten |
| `ingest` | Fügt ein Erinnerungsereignis hinzu (`user_question`, `assistant_response` usw.) |
| `retrieve` | Holt den sortierten Kontext zu einer Anfrage |
| `feedback` | Liefert Qualitätswerte (`helpful`, `outcome_value`) |
| inferierte Erinnerung | Automatisch erzeugte Erinnerung aus Mustern/Feedback |
| Inferenz-Provenienz | `why/when/type/derived_from`-Metadaten zur Nachverfolgung |
