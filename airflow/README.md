# Falco Ingestion Pipeline

This directory contains the Apache Airflow runtime used by Falco Agentic RAG to discover, parse, store, and index research papers.

## Ingestion DAG

`arxiv_paper_ingestion.py` is the scheduled ingestion workflow. By default it runs daily at 06:00 UTC and targets the previous calendar date. A daily schedule avoids intentionally skipping Friday/weekend target dates; production operators should still define a backfill/checkpoint strategy for multi-day scheduler outages.

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

Verifies PostgreSQL connectivity, requires OpenSearch cluster health to be green or yellow, and ensures the hybrid index and RRF search pipeline exist.

### `fetch_daily_papers`

Retrieves the target arXiv papers, downloads and parses PDFs with Docling, and persists canonical paper data to PostgreSQL.

### `index_papers_hybrid`

Reads recently stored papers, creates configured chunks, generates Jina passage embeddings, and updates the OpenSearch retrieval index.

### `generate_daily_report`

Collects ingestion and indexing statistics and records an operational summary through Airflow XCom/logging.

### `cleanup_temp_files`

Removes cached PDFs older than the retention window from the path configured by `ARXIV__PDF_CACHE_DIR`.

## Runtime integration

Airflow mounts the Falco `src/` directory and uses the same application services and environment configuration as the API stack. Core dependencies are:

- PostgreSQL for canonical paper data;
- OpenSearch for the retrieval index;
- Jina for passage embeddings;
- arXiv for source discovery;
- Docling for PDF parsing.

The Airflow image installs the Python packages imported by these shared Falco modules separately from the API image. Keep `airflow/requirements-airflow.txt` aligned with imports used by ingestion code.

## Web interface

Default local URL: `http://localhost:8080`

Airflow credentials are generated/configured by the container runtime. Treat the web UI as an administrative surface and restrict it appropriately in production.

## Configuration

Important settings are defined in the root `.env` file. Examples:

```text
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://rag_user:<password>@postgres:5432/rag_db
POSTGRES_DATABASE_URL=postgresql+psycopg2://rag_user:<password>@postgres:5432/rag_db
OPENSEARCH__HOST=http://opensearch:9200
ARXIV__PDF_CACHE_DIR=./data/arxiv_pdfs
JINA_API_KEY=...
```

The reference Compose stack overrides/constructs connection values from shared secret variables where appropriate. See [`../docs/CONFIGURATION.md`](../docs/CONFIGURATION.md) for the complete product configuration model.

## Operations

Use the Airflow UI and task logs to inspect pipeline failures and retries. The DAG uses bounded retries and reports pipeline statistics after normal runs.

The current reference topology shares the Falco PostgreSQL database with Airflow metadata. Isolate Airflow metadata into a separate database and credentials for a hardened production deployment; see the deployment guide for this explicit architecture decision.

For deployment, backup, recovery, and hardening guidance see:

- [`../docs/OPERATIONS.md`](../docs/OPERATIONS.md)
- [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md)
- [`../SECURITY.md`](../SECURITY.md)
