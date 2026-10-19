"""Database access. Every tenant-scoped transaction sets app.tenant_id first,
so PostgreSQL row-level security filters every query (PLT-01)."""
from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(settings.app_dsn, min_size=1, max_size=5,
                               kwargs={"row_factory": dict_row}, open=True)
    return _pool


@contextmanager
def tenant_tx(tenant_id: UUID) -> Iterator[psycopg.Connection]:
    """A transaction in which only this tenant's rows are visible."""
    with pool().connection() as conn, conn.transaction():
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
        yield conn


@contextmanager
def global_tx() -> Iterator[psycopg.Connection]:
    """A transaction with no tenant set: tenant-scoped tables return nothing."""
    with pool().connection() as conn, conn.transaction():
        yield conn
