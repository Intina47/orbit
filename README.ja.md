# Orbit

開発者向けAIアプリのための記憶インフラストラクチャ。

Orbit は、適応的パーソナライズ、関連性ランク、フィードバック学習を通じて長期的なユーザーコンテキストを提供します。  
統一されたループ `ingest -> retrieve -> feedback` により、どこでも同じ手順で動作します。

プロジェクトステータス：`Alpha`（`0.1.x`）

## クイックスタート（5分）

### 1) インストール

```bash
pip install orbit-memory
```

ローカルリポジトリから試す場合：

```bash
pip install -e .
```

### 2) ローカルで Orbit API を立ち上げる

```bash
docker compose up --build
```

API、Postgres、Prometheus、Alertmanager、OpenTelemetry Collector をまとめて起動します。

### 3) JWT を発行する

```bash
python scripts/generate_jwt.py \
  --secret orbit-dev-secret-change-me \
  --issuer orbit \
  --audience orbit-api \
  --subject local-dev
```

### 4) SDK を使った統合

```python
from orbit import MemoryEngine

engine = MemoryEngine(api_key="<jwt-token>", base_url="http://localhost:8000")

engine.ingest(
    content="forループとwhileループをよく混同してしまう。",
    event_type="user_question",
    entity_id="alice",
)

retrieval = engine.retrieve(
    query="Aliceに回答する前に何を知っておくべき？",
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

## 統合パス

| モード | 最適な対象 | エントリ |
| --- | --- | --- |
| Python SDK | Pythonアプリで最速に統合したい場合 | `from orbit import MemoryEngine` |
| REST API | 非Python環境やサービス間連携 | `POST /v1/ingest`、`GET /v1/retrieve`、`POST /v1/feedback` |
| Node.js（SDKなし） | HTTP＋APIキーで動くJavaScript | `examples/nodejs_orbit_api_chatbot/` |
| OpenClawプラグイン | OpenClawのエージェントワークフロー向け | `integrations/openclaw-memory/` |

## コアコンセプト

| 概念 | 説明 |
| --- | --- |
| `entity_id` | ユーザー・エージェント・アカウントに対応する安定した識別子 |
| `ingest` | `user_question` や `assistant_response` などの記憶イベントを書き込み |
| `retrieve` | クエリに対してランキングされたコンテキストを取得 |
| `feedback` | 結果の質を `helpful`/`outcome_value` で表現 |
| 推論記憶 | 反復パターンやフィードバックから自動生成される記憶 |
| 推論の由来 | `why/when/type/derived_from` メタデータでトレース可能 |
