FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock README.md BUILD_AND_SPEC.md /app/
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY src /app/src
COPY scripts/docker-entrypoint.sh /app/scripts/docker-entrypoint.sh

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple \
      ".[ollama]"

RUN chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
