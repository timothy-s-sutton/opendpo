#!/usr/bin/env bash
# Verify Harbor Staffing's audit chain from the command line.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec api python -m opendpo.audit verify --tenant ff3e39f3-ea89-5b8d-9af6-2638c94349e3
