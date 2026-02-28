import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from config import WORKSPACE_ROOT

CODEC_DIR = ".codec-agent"
DB_NAME = "chat.db"


def _db_path() -> Path:
    root = WORKSPACE_ROOT.resolve()
    dir_path = root / CODEC_DIR
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path / DB_NAME


def _get_conn():
    path = _db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'New chat',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversation(id)
        );
        CREATE INDEX IF NOT EXISTS idx_message_conversation ON message(conversation_id);
    """)
    conn.commit()


def ensure_db() -> None:
    conn = _get_conn()
    try:
        _ensure_schema(conn)
    finally:
        conn.close()


def create_conversation(title: str = "New chat") -> int:
    ensure_db()
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO conversation (title, created_at) VALUES (?, ?)",
            (title, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def set_conversation_title(conversation_id: int, title: str) -> None:
    conn = _get_conn()
    try:
        conn.execute("UPDATE conversation SET title = ? WHERE id = ?", (title, conversation_id))
        conn.commit()
    finally:
        conn.close()


def add_message(conversation_id: int, role: str, content: str) -> None:
    ensure_db()
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO message (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def list_conversations(limit: int = 100, offset: int = 0) -> tuple[List[dict], int]:
    ensure_db()
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM conversation").fetchone()[0]
        rows = conn.execute(
            "SELECT id, title, created_at FROM conversation ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        items = [{"id": r["id"], "title": r["title"], "created_at": r["created_at"]} for r in rows]
        return items, total
    finally:
        conn.close()


def get_messages(conversation_id: int) -> List[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT role, content, created_at FROM message WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in rows]
    finally:
        conn.close()


def delete_conversations(ids: List[int]) -> int:
    if not ids:
        return 0
    ensure_db()
    conn = _get_conn()
    try:
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM message WHERE conversation_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM conversation WHERE id IN ({placeholders})", ids)
        conn.commit()
        return len(ids)
    finally:
        conn.close()
