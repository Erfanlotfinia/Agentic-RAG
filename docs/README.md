# Falco Agentic RAG Documentation

This directory contains the product documentation for Falco Agentic RAG.

## Start here

- [Architecture](ARCHITECTURE.md) — platform components, data flow, storage responsibilities, retrieval, and the Agentic workflow.
- [API](API.md) — HTTP endpoints, request behavior, sessions, and integration examples.
- [Configuration](CONFIGURATION.md) — environment variables and service configuration.
- [Deployment](DEPLOYMENT.md) — local deployment and production-readiness checklist.
- [Operations](OPERATIONS.md) — health checks, ingestion operations, logs, recovery, and backups.
- [Security](../SECURITY.md) — deployment security requirements and secret handling.
- [Changelog](../CHANGELOG.md) — product release history.

## Product scope

The included reference configuration is optimized for arXiv computer-science research. Falco keeps source ingestion, parsing, indexing, retrieval, generation, session storage, and observability as separate services so the document source or model layer can be adapted without redesigning the full platform.

For the current runtime behavior, treat `src/`, `airflow/dags/`, `.env.example`, `compose.yml`, and `uv.lock` as authoritative.
