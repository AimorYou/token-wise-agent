"""SQLite connection manager."""

from __future__ import annotations

import sqlite3
from typing import Optional


class ConnectionManager:
    """Thin wrapper around a SQLite connection."""

    _instance: Optional["ConnectionManager"] = None
    _conn: Optional[sqlite3.Connection] = None

    @classmethod
    def get(cls, db: str = ":memory:") -> "ConnectionManager":
        if cls._instance is None or cls._conn is None:
            cls._instance = cls()
            cls._conn = sqlite3.connect(db)
            cls._conn.row_factory = sqlite3.Row
            cls._conn.execute("PRAGMA foreign_keys = ON")
        return cls._instance

    @classmethod
    def reset(cls):
        if cls._conn:
            cls._conn.close()
        cls._conn = None
        cls._instance = None

    @property
    def conn(self) -> sqlite3.Connection:
        assert self._conn is not None
        return self._conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_seq) -> sqlite3.Cursor:
        return self.conn.executemany(sql, params_seq)

    def commit(self):
        self.conn.commit()

    def create_table(self, table_name: str, columns: dict[str, str]):
        cols = ", ".join(f"{name} {typ}" for name, typ in columns.items())
        self.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({cols})")
        self.commit()
