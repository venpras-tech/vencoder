import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_settings_db_path: Path = None
_settings_db_initialized: bool = False


def _get_settings_path() -> Path:
    global _settings_db_path
    if _settings_db_path is not None:
        return _settings_db_path
    
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent
    
    _settings_db_path = app_dir / "settings.db"
    return _settings_db_path


def _get_conn():
    path = _get_settings_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_info (
            id INTEGER PRIMARY KEY,
            version TEXT,
            first_run TEXT
        );
    """)
    
    row = conn.execute("SELECT id FROM app_info WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO app_info (id, version, first_run) VALUES (1, ?, ?)",
            ("1.0.0", datetime.now(timezone.utc).isoformat())
        )
    
    conn.commit()


def init_settings_db() -> None:
    global _settings_db_initialized
    if _settings_db_initialized:
        return
    
    path = _get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = _get_conn()
    try:
        _ensure_schema(conn)
        _settings_db_initialized = True
    finally:
        conn.close()


def is_initialized() -> bool:
    return _settings_db_initialized


def get_setting(key: str, default: Any = None) -> Any:
    init_settings_db()
    conn = _get_conn()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]
    finally:
        conn.close()


def set_setting(key: str, value: Any) -> None:
    init_settings_db()
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_settings() -> Dict[str, Any]:
    init_settings_db()
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        result = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                result[row["key"]] = row["value"]
        return result
    finally:
        conn.close()


def delete_setting(key: str) -> bool:
    init_settings_db()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_mcp_settings() -> dict:
    servers = get_setting("external_mcp_servers", [])
    return {"servers": servers}


def set_mcp_setting(key: str, value: Any) -> None:
    if key == "external_servers":
        set_setting("external_mcp_servers", value)
    else:
        set_setting(f"mcp_{key}", value)
