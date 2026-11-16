#!/bin/sh
# Creates/updates the application role with the password provided by the
# environment. Runs only on a fresh PostgreSQL volume (docker-entrypoint-initdb.d).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_password="$POSTGRES_APP_PASSWORD" <<'EOSQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'turnos_app') THEN
    CREATE ROLE turnos_app NOLOGIN;
  END IF;
END
$$;

ALTER ROLE turnos_app LOGIN PASSWORD :'app_password';
GRANT USAGE ON SCHEMA public TO turnos_app;
EOSQL
