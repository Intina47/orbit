# Orbit Direct API Clients (No SDK)

This folder contains language-specific scripts that call Orbit directly over HTTP using an API key.

Supported scripts:

- `node_fetch.mjs` (Node.js + fetch)
- `python_http.py` (Python + requests)
- `go_http.go` (Go + net/http)

Each script performs:

1. `POST /v1/ingest`
2. `GET /v1/retrieve`
3. prints returned memory snippets

## Setup

1. Copy `.env.example` to `.env`.
2. Set `ORBIT_API_BASE_URL` and `ORBIT_API_KEY`.

```bash
cp .env.example .env
```

## Run: Node.js

```bash
cd examples/http_api_clients
npm install
npm run node-example
```

## Run: Python

```bash
cd examples/http_api_clients
python -m pip install requests
python python_http.py
```

## Run: Go

```bash
cd examples/http_api_clients
go run go_http.go
```
