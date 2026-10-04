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

# The function below is for detecting if the environment is serverless or read-only (such as Vercel)
def is_serverless_or_readonly() -> bool:
    if any(os.environ.get(k) for k in ("VERCEL", "VERCEL_ENV", "AWS_LAMBDA_FUNCTION_NAME", "LAMBDA_TASK_ROOT")):
        return True
    try:
        test_file = os.path.join(DB_DIR, ".write_test")
        with open(test_file, "w") as f:
            f.write("1")
        os.remove(test_file)
        return False
    except (OSError, PermissionError):
        return True

# The function below is for resolving the active SQLite database path with serverless fallback
def get_db_path() -> str:
    env_path = os.environ.get("BUSINESS_PILOT_DB")
    if env_path:
        return env_path
    if is_serverless_or_readonly():
        tmp_path = "/tmp/business_pilot.db"
        if not os.path.exists(tmp_path):
            if os.path.exists(DEFAULT_DB_PATH):
                import shutil
                try:
                    shutil.copy2(DEFAULT_DB_PATH, tmp_path)
                except Exception as e:
                    print(f"Warning: could not copy default DB to /tmp: {e}")
            else:
                try:
                    init_db(tmp_path)
                except Exception as e:
                    print(f"Warning: could not initialize database at {tmp_path}: {e}")
        return tmp_path
    return DEFAULT_DB_PATH

# The function below is for initializing the SQLite database tables and executing schema migrations
def init_db(db_path: Optional[str] = None) -> None:
    try:
        target_path = db_path or get_db_path()
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with sqlite3.connect(target_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            if os.path.exists(SCHEMA_PATH):
                with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                conn.executescript(schema_sql)
                conn.commit()
    except Exception as e:
        print(f"Warning: init_db encountered an issue ({e}). Continuing.")

# The function below is for providing a safe context-managed SQLite connection with foreign keys enabled
@contextmanager
def get_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
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

# The function below is for executing a SELECT query and returning all rows as a list of dictionaries
def query_all(sql: str, params: tuple = (), db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

# The function below is for executing a SELECT query and returning a single row as a dictionary
def query_one(sql: str, params: tuple = (), db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

# The function below is for executing INSERT, UPDATE, or DELETE SQL statements and returning the affected row count
def execute_write(sql: str, params: tuple = (), db_path: Optional[str] = None) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.rowcount

# The function below is for generating clean UUID strings for primary keys
def generate_uuid() -> str:
    return str(uuid.uuid4())
