PYTHON ?= python

.PHONY: test test-cov test-coverage lint type-check format-check migrate run-api

test:
	$(PYTHON) -m pytest

test-cov:
	$(PYTHON) -m pytest --cov=src --cov-report=term-missing

test-coverage: test-cov

lint:
	$(PYTHON) -m ruff check src tests

type-check:
	$(PYTHON) -m mypy src

format-check:
	$(PYTHON) -m black --check src tests

migrate:
	$(PYTHON) -m alembic upgrade head

run-api:
	$(PYTHON) -m orbit_api
