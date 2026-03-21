"""Database connection layer using pg8000 (pure Python Postgres driver).

Uses pg8000's DB-API 2.0 interface which supports %s parameter style,
keeping SQL queries compatible with the psycopg2 convention.
"""

import ssl
from urllib.parse import urlparse

import pg8000.dbapi

from config import SUPABASE_DB_URL

_conn = None


def _parse_dsn(dsn: str) -> dict:
    """Parse a Postgres DSN into pg8000 connect kwargs."""
    parsed = urlparse(dsn)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }


def _get_conn() -> pg8000.dbapi.Connection:
    """Lazy-initialize and return a pg8000 DB-API connection."""
    global _conn
    if _conn is None:
        params = _parse_dsn(SUPABASE_DB_URL)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        _conn = pg8000.dbapi.connect(**params, ssl_context=ssl_context)
        _conn.autocommit = True
    return _conn


def _reset_conn():
    """Reset connection on error."""
    global _conn
    try:
        if _conn:
            _conn.close()
    except Exception:
        pass
    _conn = None


def execute_query(sql: str, params: tuple | None = None) -> list[dict]:
    """Execute a read query and return rows as list of dicts."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception:
        _reset_conn()
        raise


def execute_write(sql: str, params: tuple | None = None) -> dict | None:
    """Execute a write query (INSERT/UPDATE) with RETURNING and return the row."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            row = cur.fetchone()
            if row:
                return dict(zip(columns, row))
        return None
    except Exception:
        _reset_conn()
        raise
