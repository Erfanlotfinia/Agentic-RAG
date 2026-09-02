# Deployment

Falco Agentic RAG ships with a Docker Compose reference stack for self-hosted deployment.

## Local deployment

```bash
cp .env.example .env
# Configure required keys and replace every change-me value.

uv sync --locked
docker compose up --build -d
curl http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/ready
```

The Compose stack starts Falco API, PostgreSQL, OpenSearch, OpenSearch Dashboards, Airflow, Ollama, Redis, and the self-hosted Langfuse dependencies. Before the API starts, the one-shot `migrate` service applies `alembic upgrade head`. Before Airflow starts, `airflow-db-init` idempotently prepares the isolated `airflow_user` / `airflow_db` metadata store.

Published ports bind to `127.0.0.1` by default through `FALCO_BIND_ADDRESS`. This keeps local operation convenient while avoiding accidental exposure on all interfaces. Do not change this to `0.0.0.0` unless the host firewall, TLS termination, authentication, and ingress design have been intentionally configured.

## API authentication

Trusted local development can keep built-in API authentication disabled. For a remotely reachable deployment, enable it and generate a strong random key:

```text
AUTH__ENABLED=true
AUTH__API_KEY=<at-least-32-random-characters>
AUTH__RATE_LIMIT_ENABLED=true
AUTH__RATE_LIMIT_REQUESTS=60
AUTH__RATE_LIMIT_WINDOW_SECONDS=60
```

Protected `/api/*` calls must send `Authorization: Bearer <key>`. Health and readiness remain public. If the Research Console is used against a protected API, set `FALCO_API_KEY` to the same key. An ingress/API gateway can add stronger identity, tenant, and authorization policy, but it is no longer the only authentication layer available in Falco.

## Before production

The reference Compose file is convenient for a trusted local/private environment. It is not a complete Internet-facing security perimeter.

Production deployments should:

1. Set `ENVIRONMENT=production` and `DEBUG=false`.
2. Enable built-in API authentication for remotely reachable Falco API traffic unless an equivalent stronger deployment policy makes the API inaccessible without authentication.
3. Generate unique credentials and encryption secrets for PostgreSQL, Airflow PostgreSQL, Redis, Langfuse, MinIO, and external API keys.
4. Put public Falco endpoints behind TLS and an authenticated ingress/reverse proxy where appropriate.
5. Keep PostgreSQL, Redis, OpenSearch, Ollama, ClickHouse, MinIO, and internal Langfuse databases private. Prefer no host publication at all for infrastructure services in a production orchestrator.
6. Enable OpenSearch authentication/TLS and certificate verification instead of relying on the local security-disabled Compose configuration.
7. Protect Airflow, OpenSearch Dashboards, and Langfuse with strong authentication and network policy.
8. Set `LANGFUSE_PUBLIC_URL` and `LANGFUSE_MEDIA_PUBLIC_ENDPOINT` to externally correct URLs when Langfuse is accessed through a non-local ingress.
9. Pull and validate the configured Ollama model before accepting traffic.
10. Define persistent-volume backup and restore procedures for both canonical `rag_db` and Airflow `airflow_db`.
11. Configure monitoring and alerting for Falco readiness, Airflow DAG failures, ingestion truncation failures, storage capacity, and dependency availability.
12. Require locked dependency validation, Ruff, unit/API tests, migration round-trip checks, Compose DB bootstrap smoke, and image builds before publishing a release.

## Ports

The reference stack publishes local operational ports on the address configured by `FALCO_BIND_ADDRESS`, which defaults to loopback. In a hardened deployment, expose only required public surfaces and route administrative UIs through protected ingress. Service-to-service traffic should remain on the private container/orchestrator network.

## Langfuse networking

The self-hosted Langfuse stack distinguishes public and internal object-storage endpoints:

- `LANGFUSE_MEDIA_PUBLIC_ENDPOINT` is browser/SDK reachable and defaults to `http://localhost:9090` for the local reference stack.
- Falco Compose configures Langfuse's internal media-upload endpoint as `http://langfuse-minio:9000` for container-to-container access.
- `LANGFUSE_PUBLIC_URL` is used as the Langfuse public/auth URL and must match the URL used by operators when deployed behind ingress.

The reference bootstrap creates the Falco organization and configured admin user. Create a Langfuse project/API keys separately before enabling Falco tracing.

## Stateless and stateful components

The FastAPI workers are application processes. Persistent state lives outside them:

- PostgreSQL `rag_db`: canonical Falco documents and Alembic schema state;
- PostgreSQL `airflow_db`: isolated Airflow metadata under separate credentials;
- OpenSearch: derived retrieval index;
- Redis: response cache, Agentic sessions, and optional API rate-limit counters;
- Airflow logs: orchestration logs;
- Langfuse stores: observability data;
- Ollama volume: model data.

This separation allows API containers to be replaced without losing indexed knowledge or external state when the stateful services remain intact.

## Upgrades

Before upgrading:

- back up `rag_db`, `airflow_db`, and other required stateful stores;
- review `CHANGELOG.md`;
- validate environment variables against `.env.example`;
- run `uv lock --check` and install with `uv sync --locked`;
- test `alembic upgrade head` on a copy/staging database and verify the documented rollback boundary;
- verify OpenSearch index/mapping compatibility and perform a planned reindex when vector/chunk mapping changes require it;
- run the CI release gates and deploy to staging before production.

Do not depend on application startup to create canonical tables. Schema upgrades are explicit Alembic operations. The reference Compose stack applies them through the `migrate` service and blocks API/Airflow startup when migration fails.

Falco Redis cache/session keys are versioned so incompatible storage formats can move to a new namespace without colliding with older transient keys.

## Health verification

Diagnostic health:

```bash
curl http://localhost:8000/api/v1/health
```

Readiness:

```bash
curl -f http://localhost:8000/api/v1/ready
```

Use `/health` for diagnostic status reporting. Use `/ready` for load-balancer/orchestrator readiness because it returns HTTP 503 when a dependency required for core RAG serving is degraded. These two probe endpoints intentionally remain outside built-in Bearer authentication.
