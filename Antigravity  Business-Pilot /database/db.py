"""
Database connection and session manager for BusinessPilot.
Provides thread-safe connections, automated migrations, and multi-tenant query helpers.
"""
import sqlite3
import os
import uuid
from contextlib import contextmanager
from typing import Generator, Any, List, Dict, Optional

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(DB_DIR, "business_pilot.db")
SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")


def get_db_path() -> str:
    env_path = os.environ.get("BUSINESS_PILOT_DB")
    if env_path:
        return env_path
    if os.environ.get("VERCEL"):
        tmp_path = "/tmp/business_pilot.db"
        if not os.path.exists(tmp_path) and os.path.exists(DEFAULT_DB_PATH):
            import shutil
            try:
                shutil.copy2(DEFAULT_DB_PATH, tmp_path)
            except Exception:
                pass
        return tmp_path
    return DEFAULT_DB_PATH


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database and run schema migrations."""
    target_path = db_path or get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    
    with sqlite3.connect(target_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connection with Row factory and Foreign Keys enabled."""
    target_path = db_path or get_db_path()
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_all(sql: str, params: tuple = (), db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Execute SQL query and return results as list of dictionaries."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def query_one(sql: str, params: tuple = (), db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Execute SQL query and return a single row as dictionary."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None


def execute_write(sql: str, params: tuple = (), db_path: Optional[str] = None) -> int:
    """Execute INSERT/UPDATE/DELETE and return rowcount."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.rowcount


def generate_uuid() -> str:
    """Generate a clean UUID string."""
    return str(uuid.uuid4())
