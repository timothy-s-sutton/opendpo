#!/usr/bin/env bash
# Demonstrates tamper evidence. Acting as the database superuser, which
# bypasses every application control, it edits one audit event in place.
# Then click "Verify chain" in the app, or run ./scripts/verify-audit.sh.
#   ./scripts/tamper-demo.sh          edit an event
#   ./scripts/tamper-demo.sh restore  put it back
set -euo pipefail
cd "$(dirname "$0")/.."
psql() { docker compose exec -T db psql -U postgres -d opendpo -v ON_ERROR_STOP=1 -qtA -c "$1"; }
if [ "${1:-}" = "restore" ]; then
  psql "ALTER TABLE audit_event DISABLE TRIGGER audit_event_no_update;
        UPDATE audit_event SET action = replace(action, ' [edited]', '') WHERE action LIKE '% [edited]';
        ALTER TABLE audit_event ENABLE TRIGGER audit_event_no_update;"
  echo "Restored. Verify again and the chain is intact."
else
  seq=$(psql "SELECT min(seq) FROM audit_event")
  psql "ALTER TABLE audit_event DISABLE TRIGGER audit_event_no_update;
        UPDATE audit_event SET action = action || ' [edited]' WHERE seq = $seq AND action NOT LIKE '% [edited]';
        ALTER TABLE audit_event ENABLE TRIGGER audit_event_no_update;"
  echo "Edited audit event #$seq as the database superuser. Now verify the chain."
fi
