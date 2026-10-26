"""Apply SQL migrations in order, once each, as the owner role.

Usage: python -m opendpo.migrate [--seed-demo]
"""
import sys
from pathlib import Path

import psycopg

from .config import settings

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def migrate(dsn: str, seed_demo: bool) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migration "
                     "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r[0] for r in conn.execute("SELECT name FROM schema_migration")}
        files = sorted(p for p in MIGRATIONS.glob("[0-9]*.sql"))
        if seed_demo:
            files += sorted(MIGRATIONS.glob("seed_demo*.sql"))
        for path in files:
            if path.name in done:
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO schema_migration (name) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied


if __name__ == "__main__":
    names = migrate(settings.owner_dsn, settings.seed_demo or "--seed-demo" in sys.argv)
    print("applied:", ", ".join(names) if names else "nothing new")
