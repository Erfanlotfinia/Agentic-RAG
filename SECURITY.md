# Security

Falco Agentic RAG is designed for self-hosted deployments. The included Docker Compose stack is a reference environment and must be hardened before exposure outside a trusted network.

## Built-in API protection

Falco provides optional Bearer-token authentication for `/api/*` endpoints. `/api/v1/health` and `/api/v1/ready` are intentionally public for infrastructure probes.

For remotely reachable deployments, enable authentication with a unique random key of at least 32 characters:

```text
AUTH__ENABLED=true
AUTH__API_KEY=<strong-random-key>
```

Clients then send:

```text
Authorization: Bearer <strong-random-key>
```

Falco compares credentials using constant-time comparison. Do not share one production key across unrelated tenants/security domains when stronger identity isolation is required; put Falco behind an identity-aware ingress/API gateway for per-user/per-tenant authorization, audit policy, key rotation, or SSO requirements.

Optional Redis-backed rate limiting can be enabled with:

```text
AUTH__RATE_LIMIT_ENABLED=true
AUTH__RATE_LIMIT_REQUESTS=60
AUTH__RATE_LIMIT_WINDOW_SECONDS=60
```

When rate limiting is enabled, Redis unavailability causes protected requests to fail with HTTP 503 rather than bypassing the limit. Rate-limit identities are stored as truncated SHA-256 hashes of the supplied API key, not the raw credential.

## Deployment requirements

- Do not expose PostgreSQL, Redis, OpenSearch, Ollama, ClickHouse, MinIO, or internal Langfuse stores directly to the public Internet.
- Keep published Compose ports on loopback unless remote exposure is intentional and protected.
- Put externally reachable Falco endpoints behind TLS.
- Enable built-in API authentication or an equivalent stronger authenticated network/ingress boundary before remote use.
- Replace every placeholder/default credential before deployment.
- Store production secrets in a secret manager or protected deployment environment, not in source control.
- Keep `DEBUG=false` in production.
- Restrict administrative interfaces such as Airflow, OpenSearch Dashboards, and Langfuse to authorized operators.

## OpenSearch

The reference local Compose configuration disables the OpenSearch security plugin for convenience, but Falco's OpenSearch client supports username/password, TLS, certificate verification, and an explicit CA bundle through `OPENSEARCH__*` settings. Do not expose a security-disabled OpenSearch node to an untrusted network. Use secured OpenSearch or keep it entirely private behind a network boundary.

## Database isolation and schema changes

Falco canonical data lives in `rag_db`; Airflow metadata is isolated in `airflow_db` under separate credentials in the reference topology. Preserve those boundaries in backups, restores, and access policy.

Canonical Falco schema changes are managed by Alembic. Test migrations against staging/restored data and back up before production upgrades. The API does not create canonical tables at startup.

## Ingestion safety

Keep `ARXIV__FAIL_ON_TRUNCATION=true` when completeness matters. If the upstream result count exceeds `ARXIV__MAX_RESULTS`, Falco fails visibly before expensive PDF processing rather than silently accepting an incomplete day.

PDF downloads are bounded by `PDF_PARSER__MAX_FILE_SIZE_MB`, streamed to temporary `.part` files, and atomically renamed only after success. This reduces the risk of oversized or partial remote content being mistaken for a valid cached PDF. Source content is still untrusted input; keep parser/runtime dependencies patched and apply resource limits appropriate to the deployment.

## Langfuse and infrastructure secrets

Generate unique values for the Langfuse authentication secret, salt, encryption key, Redis password, MinIO credentials, initialization user credentials, Airflow database credentials, and canonical database credentials.

Use a cryptographically secure generator for encryption material. Rotate any secret that may have been exposed.

## External integrations

Protect Jina API keys, Telegram bot tokens, and any future provider credentials. Scope and rotate credentials according to the provider's capabilities.

Telegram is disabled by default in the product example configuration and should be enabled only after a valid bot token is configured.

## User and conversation data

Agentic session history is stored in Redis when a caller supplies a `session_id`. Treat session identifiers and conversation data according to your organization's privacy and retention requirements. Configure TTLs accordingly and restrict Redis access.

Langfuse traces may contain prompts, retrieval context, metadata, or generated output depending on instrumentation. Apply appropriate access controls and retention settings.

## Dependency and image security

For commercial releases:

- run dependency and container-image vulnerability scans;
- keep Python and service images patched;
- review release notes before upgrading stateful infrastructure;
- pin or control image versions in your deployment process;
- require locked dependency validation, tests, migrations, static checks, and image builds before publishing artifacts.

## Reporting security issues

For a commercial distribution, provide customers with a private support/security contact and a documented process for receiving vulnerability reports. Do not ask customers to publish sensitive vulnerability details in a public issue tracker.
