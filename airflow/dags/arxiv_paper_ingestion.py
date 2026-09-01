from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from arxiv_ingestion.fetching import fetch_daily_papers
from arxiv_ingestion.indexing import index_papers_hybrid
from arxiv_ingestion.reporting import generate_daily_report
from arxiv_ingestion.setup import setup_environment


default_args = {
    "owner": "falco",
    "depends_on_past": False,
    "start_date": datetime(2025, 8, 8),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=30),
}


dag = DAG(
    "arxiv_paper_ingestion",
    default_args=default_args,
    description="Falco research ingestion: arXiv fetch → PostgreSQL canonical storage → chunking, embeddings, and OpenSearch indexing",
    schedule="0 6 * * 1-5",
    max_active_runs=1,
    catchup=False,
    tags=["falco", "arxiv", "ingestion", "hybrid-search", "embeddings"],
)

setup_task = PythonOperator(
    task_id="setup_environment",
    python_callable=setup_environment,
    dag=dag,
)

fetch_task = PythonOperator(
    task_id="fetch_daily_papers",
    python_callable=fetch_daily_papers,
    dag=dag,
)

index_hybrid_task = PythonOperator(
    task_id="index_papers_hybrid",
    python_callable=index_papers_hybrid,
    dag=dag,
)

report_task = PythonOperator(
    task_id="generate_daily_report",
    python_callable=generate_daily_report,
    dag=dag,
)

cleanup_task = BashOperator(
    task_id="cleanup_temp_files",
    bash_command="""
    set -e
    cache_dir="${ARXIV__PDF_CACHE_DIR:-/tmp/falco-arxiv-pdfs}"
    echo "Cleaning cached PDFs older than 30 days from ${cache_dir}..."
    if [ -d "${cache_dir}" ]; then
      find "${cache_dir}" -type f -name "*.pdf" -mtime +30 -delete
    fi
    echo "Cleanup completed"
    """,
    dag=dag,
)

setup_task >> fetch_task >> index_hybrid_task >> report_task >> cleanup_task
