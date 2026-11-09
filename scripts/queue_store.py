"""SQLite-backed persistence for the transcription queue.

The legacy queue.json remains an import/export backup. SQLite is the primary store,
using WAL and per-task hashes so unchanged task payloads are not rewritten every time
one segment or progress value changes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger("processing.queue_store")


class QueueStore:
    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @contextmanager
    def _connect(self):
        """Yield a configured SQLite connection and always close it.

        sqlite3.Connection's context manager commits/rolls back transactions but
        does not close the connection. Explicit closure matters on Windows, where
        an open handle can prevent database replacement or directory cleanup.
        """
        connection = sqlite3.connect(str(self.path), timeout=15.0)
        try:
            connection.execute("PRAGMA busy_timeout=15000")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute(
                """CREATE TABLE IF NOT EXISTS queue_tasks (
                    task_id TEXT PRIMARY KEY,
                    task_path TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'queued',
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS queue_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )"""
            )
            db.execute(
                "INSERT INTO queue_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(self.SCHEMA_VERSION),),
            )

    def has_records(self) -> bool:
        with self._connect() as db:
            row = db.execute("SELECT 1 FROM queue_tasks LIMIT 1").fetchone()
        return row is not None

    def load_tasks(self) -> list[dict]:
        tasks: list[dict] = []
        with self._connect() as db:
            rows = db.execute(
                "SELECT task_id, payload_json FROM queue_tasks ORDER BY rowid"
            ).fetchall()
        for task_id, payload in rows:
            try:
                item = json.loads(payload)
                if isinstance(item, dict):
                    item.setdefault("id", task_id)
                    tasks.append(item)
            except (TypeError, json.JSONDecodeError):
                LOGGER.exception("Skipping invalid SQLite queue row: %s", task_id)
        return tasks

    def save_tasks(self, tasks: Iterable[dict]) -> tuple[int, int]:
        """Persist only changed task rows; return (inserted_or_updated, deleted)."""
        prepared: list[tuple[str, str, str, str, str]] = []
        ids: list[str] = []
        for item in tasks:
            if not isinstance(item, dict):
                continue
            task_id = str(item.get("id") or "").strip()
            if not task_id:
                continue
            payload = json.dumps(item, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            prepared.append((task_id, str(item.get("path") or ""), str(item.get("status") or "queued"), payload, digest))
            ids.append(task_id)

        changed = 0
        deleted = 0
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for task_id, task_path, status, payload, digest in prepared:
                old = db.execute(
                    "SELECT payload_hash FROM queue_tasks WHERE task_id=?", (task_id,)
                ).fetchone()
                if old and old[0] == digest:
                    continue
                db.execute(
                    """INSERT INTO queue_tasks(task_id, task_path, status, payload_json, payload_hash, updated_at)
                       VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                       ON CONFLICT(task_id) DO UPDATE SET
                         task_path=excluded.task_path,
                         status=excluded.status,
                         payload_json=excluded.payload_json,
                         payload_hash=excluded.payload_hash,
                         updated_at=CURRENT_TIMESTAMP""",
                    (task_id, task_path, status, payload, digest),
                )
                changed += 1
            # A TEMP table avoids SQLite's host-parameter limit for large queues.
            db.execute("CREATE TEMP TABLE IF NOT EXISTS incoming_queue_ids (task_id TEXT PRIMARY KEY)")
            db.execute("DELETE FROM incoming_queue_ids")
            if ids:
                db.executemany(
                    "INSERT OR IGNORE INTO incoming_queue_ids(task_id) VALUES(?)",
                    ((task_id,) for task_id in ids),
                )
                cursor = db.execute(
                    "DELETE FROM queue_tasks WHERE task_id NOT IN "
                    "(SELECT task_id FROM incoming_queue_ids)"
                )
            else:
                cursor = db.execute("DELETE FROM queue_tasks")
            deleted = max(0, int(cursor.rowcount or 0))
            db.execute("DELETE FROM incoming_queue_ids")
            db.commit()
        return changed, deleted

    def checkpoint(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def integrity_check(self) -> bool:
        with self._connect() as db:
            row = db.execute("PRAGMA quick_check").fetchone()
        return bool(row and row[0] == "ok")
