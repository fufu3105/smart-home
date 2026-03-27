from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

try:
    import mysql.connector
except Exception:  # pragma: no cover - depends on local env
    mysql = None
else:
    mysql = mysql.connector

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in local setups
    def load_dotenv(*_args, **_kwargs):
        return False

ENV_FILE = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(ENV_FILE, override=True)

DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'smart_home')


def get_connection():
    if mysql is None:
        raise RuntimeError(
            "Thiếu package 'mysql-connector-python'. "
            "Hãy cài dependency trước khi chạy backend với MySQL."
        )

    return mysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )


@contextmanager
def get_cursor():
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            cur.close()
        finally:
            conn.close()
