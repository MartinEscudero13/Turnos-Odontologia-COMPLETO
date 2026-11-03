-- Development-only application role.
-- The migration 001 creates `turnos_app` if it does not exist and grants table privileges.
-- This init script makes it a login role for local Compose; never use these values outside local dev.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'turnos_app') THEN
    CREATE ROLE turnos_app LOGIN PASSWORD 'dev-only-app-password';
  ELSE
    ALTER ROLE turnos_app LOGIN PASSWORD 'dev-only-app-password';
  END IF;
END
$$;
