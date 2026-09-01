# Deployment

Falco Agentic RAG ships with a Docker Compose reference stack for self-hosted deployment.

## Local deployment

```bash
cp .env.example .env
# Configure required keys and replace every change-me value.

uv sync
docker compose up --build -d
curl http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/ready
```

The Compose stack starts Falco API, PostgreSQL, OpenSearch, OpenSearch Dashboards, Airflow, Ollama, Redis, and the self-hosted Langfuse dependencies.

Published ports bind to `127.0.0.1` by default through `FALCO_BIND_ADDRESS`. This keeps local operation convenient while avoiding accidental exposure on all interfaces. Do not change this to `0.0.0.0` unless the host firewall, TLS termination, authentication, and ingress design have been intentionally configured.

## Before production

The reference Compose file is convenient for a trusted local/private environment. It is not a complete Internet-facing security perimeter.

Production deployments should:

1. Set `ENVIRONMENT=production` and `DEBUG=false`.
2. Generate unique credentials and encryption secrets for PostgreSQL, Redis, Airflow, Langfuse, MinIO, and any external API keys.
3. Put the Falco API behind TLS and an authenticated reverse proxy/API gateway when access is not strictly private.
4. Keep PostgreSQL, Redis, OpenSearch, Ollama, ClickHouse, MinIO, and internal Langfuse databases private. Prefer no host publication at all for infrastructure services in a production orchestrator.
5. Enable appropriate OpenSearch security instead of relying on the local Compose security-disabled configuration.
6. Protect Airflow, OpenSearch Dashboards, and Langfuse with strong authentication and network policy.
7. Set `LANGFUSE_PUBLIC_URL` and `LANGFUSE_MEDIA_PUBLIC_ENDPOINT` to externally correct URLs when Langfuse is accessed through a non-local ingress.
8. Pull and validate the configured Ollama model before accepting traffic.
9. Define persistent-volume backup and restore procedures.
10. Configure monitoring and alerting for Falco readiness, Airflow DAG failures, storage capacity, and dependency availability.
11. Run the automated test suite, locked dependency validation, Docker/Compose smoke tests, and image/security scans in CI before publishing a release.

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

- PostgreSQL: canonical documents;
- OpenSearch: retrieval index;
- Redis: response cache and Agentic sessions;
- Airflow metadata/logs: orchestration state;
- Langfuse stores: observability data;
- Ollama volume: model data.

This separation allows API containers to be replaced without losing user sessions or indexed knowledge when external stateful services remain intact.

## Upgrades

Before upgrading:

- back up stateful stores;
- review `CHANGELOG.md`;
- verify index/schema compatibility;
- validate environment variables against `.env.example`;
- regenerate/validate the dependency lock when project metadata or dependencies change;
- run tests against the target release;
- deploy to a staging environment before production.

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

Use `/health` for diagnostic status reporting. Use `/ready` for load-balancer/orchestrator readiness because it returns HTTP 503 when a dependency required for core RAG serving is degraded.

## Known production architecture decision

The reference Compose stack currently uses the same PostgreSQL database service/database for both Falco's canonical document tables and Airflow metadata. For a hardened commercial deployment, isolate Airflow metadata into a separate database (and ideally separate credentials) before treating the reference stack as a production topology. That separation should be implemented and migration-tested as an explicit deployment change rather than silently changing an existing database layout.
