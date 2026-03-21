import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

from config import SUPABASE_DB_URL

_pool = None


def get_pool() -> SimpleConnectionPool:
    """Lazy-initialize and return the connection pool."""
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(minconn=1, maxconn=5, dsn=SUPABASE_DB_URL)
    return _pool


def execute_query(sql: str, params: tuple | None = None) -> list[dict]:
    """Execute a read query and return rows as list of dicts."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        pool.putconn(conn)


def execute_write(sql: str, params: tuple | None = None) -> dict | None:
    """Execute a write query (INSERT/UPDATE) with RETURNING and return the row."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            conn.commit()
            try:
                return dict(cur.fetchone())
            except (psycopg2.ProgrammingError, TypeError):
                return None
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
