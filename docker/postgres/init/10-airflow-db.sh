#!/bin/sh
set -eu

: "${AIRFLOW_POSTGRES_PASSWORD:?AIRFLOW_POSTGRES_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=airflow_password="$AIRFLOW_POSTGRES_PASSWORD" <<'EOSQL'
CREATE USER airflow_user WITH PASSWORD :'airflow_password';
EOSQL

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE DATABASE airflow_db OWNER airflow_user;
EOSQL
