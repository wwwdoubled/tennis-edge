"""
Database connection helper.

Uses psycopg (v3) for both serverless functions and batch scripts.
Reads DATABASE_URL from environment. Works with Neon, Supabase, or local Postgres.

In serverless contexts (Vercel functions), prefer Neon's pooled connection string
(host like `*-pooler.neon.tech`) to avoid connection storms.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
            "or set it as an environment variable in Vercel/GitHub."
        )
    return url


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """
    Open a connection. Use as:

        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    conn = psycopg.connect(database_url(), row_factory=dict_row, autocommit=False)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    """Convenience: open a connection, run query, return list of dict rows."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def fetch_one(query: str, params: tuple = ()) -> dict | None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()
