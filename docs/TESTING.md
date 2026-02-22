# Testing Strategy

## Layers

1. Unit tests (`tests/unit`)
- Validate model behavior and deterministic module logic.

2. Integration tests (`tests/integration`)
- Validate end-to-end workflow across Stage 1/2/3 and storage.

3. Benchmark tests (`tests/benchmarks`)
- Validate throughput/latency envelopes on local hardware.

4. Lab tests (`tests/lab`)
- Validate learning and behavioral convergence patterns.

## Commands

```bash
pytest -q
```

```bash
mypy src
```

Optional (requires local tools installed):

```bash
pytest --cov=src --cov-report=term-missing
ruff check src tests
```

## Non-Flaky Constraint

- Tests use deterministic providers by default.
- No network calls are required for default test runs.
