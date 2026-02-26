# Orbit

Infraestrutura de memória para aplicações de IA focadas em desenvolvedores.

Orbit preserva sinais do usuário a longo prazo com personalização adaptativa, ranking relevante e aprendizado por feedback.  
O fluxo padrão é `ingest -> retrieve -> feedback`, regardless da plataforma.

Status do projeto: `Alpha` (`0.1.x`)

## Início rápido (5 minutos)

### 1) Instalar

```bash
pip install orbit-memory
```

Para desenvolvimento local:

```bash
pip install -e .
```

### 2) Subir a API localmente

```bash
docker compose up --build
```

Executa API, Postgres, Prometheus, Alertmanager e o coletor OpenTelemetry.

### 3) Gerar um JWT local

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

### 4) Integrar com o SDK

```python
from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>", base_url="http://localhost:8000")

engine.ingest(
    content="Eu ainda confundo for loops com while loops.",
    event_type="user_question",
    entity_id="alice",
)

retrieval = engine.retrieve(
    query="O que devo saber sobre Alice antes de responder?",
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

## Caminhos de integração

| Modo | Melhor para | Entrada |
| --- | --- | --- |
| SDK Python | Apps Python querendo integração rápida | `from orbit import MemoryEngine` |
| API REST | Outras linguagens ou serviços | `POST /v1/ingest`, `GET /v1/retrieve`, `POST /v1/feedback` |
| Node.js (sem SDK) | Apps JavaScript com HTTP direto + chave | `examples/nodejs_orbit_api_chatbot/` |
| Plugin OpenClaw | Fluxos de agentes dentro do OpenClaw | `integrations/openclaw-memory/` |

## Conceitos-chave

| Conceito | Descrição |
| --- | --- |
| `entity_id` | Identificador estável para usuário, agente ou conta |
| `ingest` | Adiciona um evento de memória (`user_question`, `assistant_response`, etc.) |
| `retrieve` | Recupera contexto classificado para uma pergunta |
| `feedback` | Envia sinal de qualidade (`helpful`, `outcome_value`) |
| memória inferida | Memória gerada automaticamente a partir de padrões repetidos |
| proveniência inferencial | Metadados `why/when/type/derived_from` para rastreamento |
