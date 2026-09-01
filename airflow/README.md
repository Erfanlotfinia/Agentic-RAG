# Falco Ingestion Pipeline

This directory contains the Apache Airflow runtime used by Falco Agentic RAG to discover, parse, store, and index research papers.

## Production DAG

`arxiv_paper_ingestion.py` is the scheduled ingestion workflow. By default it runs Monday through Friday at 06:00 UTC.

```text
setup_environment
      ↓
fetch_daily_papers
      ↓
index_papers_hybrid
      ↓
generate_daily_report
      ↓
cleanup_temp_files
```

### `setup_environment`

Verifies PostgreSQL and OpenSearch connectivity and ensures the hybrid index and RRF search pipeline exist.

### `fetch_daily_papers`

Retrieves the target arXiv papers, downloads and parses PDFs with Docling, and persists canonical paper data to PostgreSQL.

### `index_papers_hybrid`

Reads recently stored papers, creates section-aware chunks, generates Jina passage embeddings, and updates the OpenSearch retrieval index.

### `generate_daily_report`

Collects ingestion and indexing statistics and records an operational summary through Airflow XCom/logging.

### `cleanup_temp_files`

Removes old temporary PDFs from the container filesystem.

## Runtime integration

Airflow mounts the Falco `src/` directory and uses the same application services and environment configuration as the API stack. Core dependencies are:

- PostgreSQL for canonical paper data;
- OpenSearch for the retrieval index;
- Jina for passage embeddings;
- arXiv for source discovery;
- Docling for PDF parsing.

## Web interface

Default local URL: `http://localhost:8080`

Airflow credentials are generated/configured by the container runtime. Treat the web UI as an administrative surface and restrict it appropriately in production.

## Configuration

Important settings are defined in the root `.env` file. Examples:

```text
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://rag_user:rag_password@postgres:5432/rag_db
POSTGRES_DATABASE_URL=postgresql+psycopg2://rag_user:rag_password@postgres:5432/rag_db
OPENSEARCH__HOST=http://opensearch:9200
JINA_API_KEY=...
```

See [`../docs/CONFIGURATION.md`](../docs/CONFIGURATION.md) for the complete product configuration model.

## Operations

Use the Airflow UI and task logs to inspect pipeline failures and retries. The DAG uses bounded retries and reports pipeline statistics after normal runs.

For deployment, backup, recovery, and hardening guidance see:

- [`../docs/OPERATIONS.md`](../docs/OPERATIONS.md)
- [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md)
- [`../SECURITY.md`](../SECURITY.md)
