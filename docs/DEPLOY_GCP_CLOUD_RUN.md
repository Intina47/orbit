# Orbit Deployment: Google Cloud Run

This runbook deploys Orbit API on Google Cloud Run with Artifact Registry and Secret Manager.

## 1) Prerequisites

- Google Cloud project with billing enabled.
- APIs enabled:
  - `run.googleapis.com`
  - `cloudbuild.googleapis.com`
  - `artifactregistry.googleapis.com`
  - `secretmanager.googleapis.com`
  - `sqladmin.googleapis.com` (if using Cloud SQL)
- `gcloud` CLI installed and authenticated.

## 2) One-time setup

1. Set project and region:

```bash
gcloud config set project <PROJECT_ID>
gcloud config set run/region <REGION>
```

2. Create Artifact Registry repo:

```bash
gcloud artifacts repositories create orbit \
  --repository-format=docker \
  --location=<REGION> \
  --description="Orbit API images"
```

3. Create secrets:

```bash
printf '%s' 'postgresql+psycopg://<user>:<password>@/<db>?host=/cloudsql/<PROJECT_ID>:<REGION>:<INSTANCE>' \
  | gcloud secrets create orbit-db-url --data-file=-

printf '%s' '<strong-random-jwt-secret>' \
  | gcloud secrets create orbit-jwt-secret --data-file=-
```

If secret already exists, add new versions:

```bash
printf '%s' '<new-value>' | gcloud secrets versions add orbit-jwt-secret --data-file=-
```

## 3) Deploy via Cloud Build (CI-friendly)

From repo root:

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=_REGION=<REGION>,_AR_REPOSITORY=orbit,_SERVICE_NAME=orbit-api,_CLOUDSQL_INSTANCE=<PROJECT_ID>:<REGION>:<INSTANCE>,_ORBIT_CORS_ALLOW_ORIGINS=https://<frontend-domain>
```

The build will:
- build Docker image
- push to Artifact Registry
- deploy Cloud Run service via `scripts/deploy_gcp_cloud_run.sh`

## 4) Deploy directly with script (manual)

Build and push image:

```bash
IMAGE_URI="<REGION>-docker.pkg.dev/<PROJECT_ID>/orbit/orbit-api:manual-$(date +%Y%m%d-%H%M%S)"
gcloud builds submit --tag "${IMAGE_URI}" .
```

Deploy:

```bash
PROJECT_ID=<PROJECT_ID> \
REGION=<REGION> \
SERVICE_NAME=orbit-api \
IMAGE_URI="${IMAGE_URI}" \
CLOUDSQL_INSTANCE=<PROJECT_ID>:<REGION>:<INSTANCE> \
ORBIT_CORS_ALLOW_ORIGINS=https://<frontend-domain> \
bash scripts/deploy_gcp_cloud_run.sh
```

## 5) Smoke checks

1. Health:

```bash
curl https://<cloud-run-url>/v1/health
```

2. Generate local token for manual check:

```bash
python scripts/generate_jwt.py \
  --secret "<same secret as orbit-jwt-secret>" \
  --issuer orbit \
  --audience orbit-api \
  --subject smoke-user
```

3. Ingest:

```bash
curl -X POST "https://<cloud-run-url>/v1/ingest" \
  -H "Authorization: Bearer <jwt>" \
  -H "Idempotency-Key: smoke-ingest-1" \
  -H "Content-Type: application/json" \
  -d '{"content":"Cloud Run smoke memory","event_type":"user_question","entity_id":"smoke-user"}'
```

## 6) Env matrix

Use `docs/GCP_ENV_MATRIX.md` as the source of truth for all app and infra settings.
