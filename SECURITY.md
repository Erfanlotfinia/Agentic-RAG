# Security

Falco Agentic RAG is designed for self-hosted deployments, but the included Docker Compose stack is a reference environment and must be hardened before exposure outside a trusted network.

## Deployment requirements

- Do not expose PostgreSQL, Redis, OpenSearch, Ollama, ClickHouse, MinIO, or internal Langfuse stores directly to the public Internet.
- Put externally reachable Falco endpoints behind TLS and appropriate authentication/authorization controls.
- Replace every placeholder/default credential before deployment.
- Store production secrets in a secret manager or protected deployment environment, not in source control.
- Keep `DEBUG=false` in production.
- Restrict administrative interfaces such as Airflow, OpenSearch Dashboards, and Langfuse to authorized operators.

## OpenSearch

The reference Compose configuration disables the OpenSearch security plugin for local convenience. Do not use that exposure model on an untrusted network. Enable authentication/TLS or keep OpenSearch entirely private behind a network boundary.

## Langfuse and infrastructure secrets

Generate unique values for the Langfuse authentication secret, salt, encryption key, Redis password, MinIO credentials, initialization user credentials, and database credentials.

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
- run automated tests before publishing artifacts.

## Reporting security issues

For a commercial distribution, provide customers with a private support/security contact and a documented process for receiving vulnerability reports. Do not ask customers to publish sensitive vulnerability details in a public issue tracker.
