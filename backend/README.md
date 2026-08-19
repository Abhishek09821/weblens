# WebLens backend

FastAPI service that collects observable evidence from a target website and runs deterministic
analyzers over it. Detection never involves an AI model.

Project overview and setup: [../README.md](../README.md).
Architecture: [../docs/blueprint/03-backend-architecture.md](../docs/blueprint/03-backend-architecture.md).

## Layout

```
src/weblens/
├── api/            HTTP shape, problem+json, SSE framing
├── orchestration/  stage sequencing, job lifecycle, analyzer isolation
├── collection/     the only code that touches the network
├── analyzers/      pure functions from evidence to findings
├── domain/         types and invariants (imports nothing above it)
├── ai/             optional presentation layer, disabled by default
└── utils/          ids, urls, text, timing
```

The import arrow points one way: `api → orchestration → {collection, analyzers} → domain → utils`.
Analyzers cannot import `collection`, which is what guarantees they perform no I/O and makes them
testable offline from committed evidence fixtures.

## Commands

Run from the repository root:

```bash
make setup-backend      # venv (python3.12) + deps + Chromium
make dev-backend        # uvicorn on 127.0.0.1:8000, docs at /docs
make check-backend      # ruff + mypy + pytest (offline)
make test-live          # opt-in network tests
```

Python 3.12 is required: Playwright does not yet publish support for 3.14, and `pyproject.toml`
enforces the range so the mismatch fails at install time rather than at first scan.

## Configuration

Every tunable lives in `src/weblens/config.py` and is settable with a `WEBLENS_`-prefixed
environment variable. See `.env.example`.

Two settings deserve care:

- `WEBLENS_ALLOW_PRIVATE_TARGETS` — test-only. Disables the guard that rejects loopback and
  private addresses. Never enable it on a reachable deployment.
- `WEBLENS_CORS_ORIGINS` — exact origins only. The API has no authentication in V1.
