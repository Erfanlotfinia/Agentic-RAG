# Deployment

Falco Agentic RAG ships with a Docker Compose reference stack for self-hosted deployment.

## Local deployment

```bash
cp .env.example .env
# Configure required keys and replace every change-me value.

uv sync
docker compose up --build -d
curl http://localhost:8000/api/v1/health
```

The Compose stack starts Falco API, PostgreSQL, OpenSearch, OpenSearch Dashboards, Airflow, Ollama, Redis, and the self-hosted Langfuse dependencies.

## Before production

The reference Compose file is convenient for a trusted local/private environment. It is not intended to be exposed directly to the public Internet without a hardened deployment layer.

Production deployments should:

1. Set `ENVIRONMENT=production` and `DEBUG=false`.
2. Generate unique credentials and encryption secrets for PostgreSQL, Redis, Airflow, Langfuse, MinIO, and any external API keys.
3. Put the Falco API behind TLS and an authenticated reverse proxy/API gateway when access is not strictly private.
4. Restrict infrastructure ports. PostgreSQL, Redis, OpenSearch, Ollama, ClickHouse, MinIO, and internal Langfuse databases should not be publicly reachable.
5. Enable appropriate OpenSearch security instead of relying on the local Compose security-disabled configuration.
6. Protect Airflow, OpenSearch Dashboards, and Langfuse with strong authentication and network policy.
7. Pull and validate the configured Ollama model before accepting traffic.
8. Define persistent-volume backup and restore procedures.
9. Configure monitoring and alerting for the Falco health endpoint, Airflow DAG failures, storage capacity, and dependency availability.
10. Run the automated test suite and image/security scans in CI before publishing a release.

## Ports

The default Compose file maps several service ports for local operations. Production environments should expose only the surfaces they require. In most deployments this means the Falco API and, optionally, selected administrative UIs through a protected ingress.

## Stateless and stateful components

The FastAPI workers are application processes. Persistent state lives outside them:

- PostgreSQL: canonical documents;
- OpenSearch: retrieval index;
- Redis: response cache and Agentic sessions;
- Airflow storage/database: orchestration state and logs;
- Langfuse stores: observability data;
- Ollama volume: model data.

This separation allows API containers to be replaced without losing user sessions or indexed knowledge when external stateful services remain intact.

## Upgrades

Before upgrading:

- back up stateful stores;
- review `CHANGELOG.md`;
- verify index/schema compatibility;
- validate environment variables against `.env.example`;
- run tests against the target release;
- deploy to a staging environment before production.

## Health verification

```bash
curl -f http://localhost:8000/api/v1/health
```

Use the health endpoint for readiness monitoring, but also monitor the individual infrastructure services because a degraded dependency can reduce retrieval/generation capability.
