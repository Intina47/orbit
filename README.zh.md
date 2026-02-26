# Orbit

面向开发者的 AI 应用的长时记忆基础设施。

Orbit 负责将事件持久化、语义排序、适应性推理以及反馈闭环融入到一个统一的流程：`ingest -> retrieve -> feedback`。

项目状态：`Alpha`（`0.1.x`）

## 快速开始（5 分钟）

### 1）安装

```bash
pip install orbit-memory
```

如果你在本地开发：

```bash
pip install -e .
```

### 2）在本地启动 Orbit API

建议启动完整堆栈（API、Postgres、Prometheus、Alertmanager、OpenTelemetry Collector）：

```bash
docker compose up --build
```

### 3）生成本地 JWT

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

### 4）使用 SDK

```python
from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt>", base_url="http://localhost:8000")

engine.ingest(content="我经常分不清 for 循环和 while 循环。", event_type="user_question", entity_id="alice")

retrieval = engine.retrieve(query="在回应 Alice 之前我需要知道什么？", entity_id="alice", limit=5)

if retrieval.memories:
    engine.feedback(memory_id=retrieval.memories[0].memory_id, helpful=True, outcome_value=1.0)
```

## 集成路径

| 方式 | 适用场景 | 接入入口 |
| --- | --- | --- |
| Python SDK | 希望在 Python 项目中最快集成 | `from orbit import MemoryEngine` |
| REST API | 非 Python 平台或服务对服务请求 | `POST /v1/ingest`、`GET /v1/retrieve`、`POST /v1/feedback` |
| Node.js（无 SDK） | 使用 HTTP + API Key 的 JavaScript 应用 | `examples/nodejs_orbit_api_chatbot/` |
| OpenClaw 插件 | 在 OpenClaw 代理工作流中使用 | `integrations/openclaw-memory/` |

## 核心概念

| 概念 | 说明 |
| --- | --- |
| `entity_id` | 用于用户/代理/客户的稳定身份键 |
| `ingest` | 发送记忆事件（`user_question`、`assistant_response` 等） |
| `retrieve` | 获取经过排序的上下文 |
| `feedback` | 传递质量反馈（`helpful`、`outcome_value`） |
| 推理记忆 | 由重复模式/反馈生成的自动记忆 |
| 推理溯源 | `why/when/type/derived_from` 元数据，便于排查 |
