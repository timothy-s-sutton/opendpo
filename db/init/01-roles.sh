#!/bin/sh
# Runs once, when the database volume is first created.
# opendpo_owner owns the schema and runs migrations.
# opendpo_app is what the API uses: no superuser, no BYPASSRLS, so row-level
# security applies to every query it makes (PLT-01).
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE opendpo_owner LOGIN PASSWORD '${OPENDPO_OWNER_PASSWORD}';
CREATE ROLE opendpo_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '${OPENDPO_APP_PASSWORD}';
CREATE ROLE keycloak LOGIN PASSWORD '${KEYCLOAK_DB_PASSWORD}';
CREATE DATABASE opendpo OWNER opendpo_owner;
CREATE DATABASE keycloak OWNER keycloak;
REVOKE ALL ON DATABASE opendpo FROM PUBLIC;
GRANT CONNECT ON DATABASE opendpo TO opendpo_app;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname opendpo <<SQL
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO opendpo_app;
CREATE EXTENSION IF NOT EXISTS vector;
SQL
