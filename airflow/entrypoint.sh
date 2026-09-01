#!/bin/bash
set -e

: "${AIRFLOW_ADMIN_USERNAME:?AIRFLOW_ADMIN_USERNAME must be set}"
: "${AIRFLOW_ADMIN_FIRSTNAME:?AIRFLOW_ADMIN_FIRSTNAME must be set}"
: "${AIRFLOW_ADMIN_LASTNAME:?AIRFLOW_ADMIN_LASTNAME must be set}"
: "${AIRFLOW_ADMIN_EMAIL:?AIRFLOW_ADMIN_EMAIL must be set}"
: "${AIRFLOW_ADMIN_PASSWORD:?AIRFLOW_ADMIN_PASSWORD must be set}"

echo "Cleaning up any existing Airflow processes..."
pkill -f "airflow webserver" || true
pkill -f "airflow scheduler" || true
rm -f /opt/airflow/airflow-webserver.pid
rm -f /opt/airflow/airflow-scheduler.pid

sleep 2

echo "Initializing Airflow database..."
airflow db init

echo "Ensuring the configured Airflow admin user exists..."
airflow users create \
    --username "${AIRFLOW_ADMIN_USERNAME}" \
    --firstname "${AIRFLOW_ADMIN_FIRSTNAME}" \
    --lastname "${AIRFLOW_ADMIN_LASTNAME}" \
    --role Admin \
    --email "${AIRFLOW_ADMIN_EMAIL}" \
    --password "${AIRFLOW_ADMIN_PASSWORD}" || echo "Configured Airflow admin user already exists"

echo "Starting Airflow webserver and scheduler..."
airflow webserver --port 8080 --daemon &
airflow scheduler
