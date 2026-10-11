"""Repair SQLite tables whose `created_at` column lost its DEFAULT in an older migration.

Such tables reject every INSERT that relies on the default; with INSERT OR IGNORE the
failure was silent (memory "saved" nothing, chats were not archived). The rebuild keeps
all rows and indexes.
"""
from __future__ import annotations

import re
import sqlite3

DEFAULT = "DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"


def ensure_created_at_default(db: sqlite3.Connection, table: str) -> bool:
    columns = db.execute(f'PRAGMA table_info("{table}")').fetchall()
    column = next((row for row in columns if row[1] == "created_at"), None)
    if column is None or column[4] is not None:
        return False
    row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if row is None:
        return False
    create_sql = re.sub(r"(created_at\s+TEXT\s+NOT\s+NULL)(?!\s+DEFAULT)", rf"\1 {DEFAULT}", row[0], count=1, flags=re.I)
    indexes = [r[0] for r in db.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (table,))]
    temp = f"{table}__repair"
    create_temp = re.sub(r'^\s*CREATE\s+TABLE\s+("?)' + re.escape(table) + r'\1', f'CREATE TABLE "{temp}"',
                         create_sql, count=1, flags=re.I)
    names = ",".join(f'"{c[1]}"' for c in columns)
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(create_temp)
        db.execute(f'INSERT INTO "{temp}"({names}) SELECT {names} FROM "{table}"')
        db.execute(f'DROP TABLE "{table}"')
        db.execute(f'ALTER TABLE "{temp}" RENAME TO "{table}"')
        for index_sql in indexes:
            db.execute(index_sql)
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return True
