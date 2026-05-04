"""
Apply the database schema (idempotent — uses CREATE IF NOT EXISTS everywhere).

Usage:
    DATABASE_URL=postgres://... python -m scripts.init_db
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")

from api._lib.db import connect


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def main() -> int:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
    print("✅ schema applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
