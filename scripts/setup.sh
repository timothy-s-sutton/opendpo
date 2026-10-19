#!/usr/bin/env bash
# Creates .env with a fresh random password for every service (threat model T-09).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then
  echo ".env already exists; leaving it alone."
else
  gen() { head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20; }
  {
    echo "POSTGRES_PASSWORD=$(gen)"
    echo "OPENDPO_OWNER_PASSWORD=$(gen)"
    echo "OPENDPO_APP_PASSWORD=$(gen)"
    echo "KEYCLOAK_DB_PASSWORD=$(gen)"
    echo "KEYCLOAK_ADMIN_PASSWORD=$(gen)"
    echo "OPENDPO_DEMO_PASSWORD=$(gen)"
  } > .env
  chmod 600 .env
  echo "Created .env with random passwords."
fi
echo
echo "Demo user password: $(grep '^OPENDPO_DEMO_PASSWORD=' .env | cut -d= -f2)"
echo "Keycloak admin password: $(grep '^KEYCLOAK_ADMIN_PASSWORD=' .env | cut -d= -f2)"
