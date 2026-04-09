import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config import WORKSPACE_ROOT
from chat_db import (
    create_conversation,
    set_conversation_title,
    add_message,
    list_conversations,
    get_messages,
    delete_conversations,
)

CODEC_DIR = ".vencoder"


class SessionState(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SessionStats:
    session_id: int
    total_messages: int = 0
    total_tokens: int = 0
    tools_used: int = 0
    files_created: int = 0
    files_modified: int = 0
    commands_executed: int = 0
    duration_seconds: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None


@dataclass
class Session:
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    state: SessionState = SessionState.ACTIVE
    mode: str = "agent"
    model: Optional[str] = None
    stats: SessionStats = None
    tags: List[str] = field(default_factory=list)
    parent_id: Optional[int] = None
    fork_count: int = 0
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = SessionStats(session_id=self.id)


class SessionManager:
    def __init__(self, workspace_root: Path = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT.resolve()
        self.sessions_dir = self.workspace_root / CODEC_DIR / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: Dict[int, Session] = {}
        self._session_metadata: Dict[int, Dict[str, Any]] = {}
        self._load_metadata()
    
    def _load_metadata(self):
        metadata_file = self.sessions_dir / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    self._session_metadata = json.load(f)
            except Exception:
                pass
    
    def _save_metadata(self):
        metadata_file = self.sessions_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(self._session_metadata, f, indent=2)
    
    def create_session(self, title: str = "New Chat", mode: str = "agent", model: str = None) -> Session:
        db_id = create_conversation(title)
        
        session = Session(
            id=db_id,
            title=title,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            mode=mode,
            model=model,
        )
        
        self._active_sessions[db_id] = session
        self._session_metadata[str(db_id)] = {
            "title": title,
            "mode": mode,
            "model": model,
            "state": SessionState.ACTIVE.value,
            "tags": [],
            "parent_id": None,
            "fork_count": 0,
        }
        self._save_metadata()
        
        return session
    
    def get_session(self, session_id: int) -> Optional[Session]:
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]
        
        metadata = self._session_metadata.get(str(session_id))
        if metadata:
            messages = get_messages(session_id)
            return Session(
                id=session_id,
                title=metadata.get("title", "Untitled"),
                created_at=datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat())),
                updated_at=datetime.fromisoformat(metadata.get("updated_at", datetime.now().isoformat())),
                state=SessionState(metadata.get("state", "active")),
                mode=metadata.get("mode", "agent"),
                model=metadata.get("model"),
                tags=metadata.get("tags", []),
                parent_id=metadata.get("parent_id"),
                fork_count=metadata.get("fork_count", 0),
            )
        
        return None
    
    def update_session(self, session_id: int, **kwargs):
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            session.updated_at = datetime.now()
        
        metadata = self._session_metadata.get(str(session_id), {})
        metadata.update(kwargs)
        metadata["updated_at"] = datetime.now().isoformat()
        self._session_metadata[str(session_id)] = metadata
        self._save_metadata()
    
    def set_session_title(self, session_id: int, title: str):
        set_conversation_title(session_id, title)
        self.update_session(session_id, title=title)
    
    def add_message(self, session_id: int, role: str, content: str):
        add_message(session_id, role, content)
        self.update_session(session_id, updated_at=datetime.now().isoformat())
        
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            session.stats.total_messages += 1
    
    def get_messages(self, session_id: int) -> List[Dict[str, Any]]:
        return get_messages(session_id)
    
    def list_sessions(self, limit: int = 100, offset: int = 0, state: SessionState = None) -> List[Session]:
        sessions, _ = list_conversations(limit, offset)
        
        result = []
        for s in sessions:
            session = self.get_session(s["id"])
            if session:
                if state is None or session.state == state:
                    result.append(session)
        
        return result
    
    def search_sessions(self, query: str) -> List[Session]:
        results = []
        for session_id_str, metadata in self._session_metadata.items():
            session_id = int(session_id_str)
            
            title_match = query.lower() in metadata.get("title", "").lower()
            
            messages = get_messages(session_id)
            content_match = any(
                query.lower() in msg.get("content", "").lower()
                for msg in messages
            )
            
            if title_match or content_match:
                session = self.get_session(session_id)
                if session:
                    results.append(session)
        
        return results
    
    def fork_session(self, session_id: int, title: str = None) -> Optional[Session]:
        original = self.get_session(session_id)
        if not original:
            return None
        
        original.fork_count += 1
        self.update_session(session_id, fork_count=original.fork_count)
        
        new_title = title or f"{original.title} (fork)"
        new_session = self.create_session(
            title=new_title,
            mode=original.mode,
            model=original.model,
        )
        
        new_session.parent_id = session_id
        self.update_session(
            new_session.id,
            parent_id=session_id,
            tags=original.tags.copy(),
        )
        
        messages = get_messages(session_id)
        for msg in messages:
            add_message(new_session.id, msg["role"], msg["content"])
        
        return new_session
    
    def export_session(self, session_id: int, format: str = "markdown") -> str:
        session = self.get_session(session_id)
        if not session:
            return ""
        
        messages = get_messages(session_id)
        
        if format == "markdown":
            lines = [
                f"# {session.title}",
                "",
                f"**Date:** {session.created_at.strftime('%Y-%m-%d %H:%M')}",
                f"**Mode:** {session.mode}",
                "",
                "## Conversation",
                "",
            ]
            
            for msg in messages:
                role = msg["role"].capitalize()
                content = msg["content"]
                timestamp = msg.get("created_at", "")[:16]
                lines.append(f"### {role} ({timestamp})")
                lines.append("")
                lines.append(content)
                lines.append("")
            
            return "\n".join(lines)
        
        elif format == "json":
            return json.dumps({
                "session": {
                    "id": session.id,
                    "title": session.title,
                    "created_at": session.created_at.isoformat(),
                    "mode": session.mode,
                    "model": session.model,
                },
                "messages": messages,
            }, indent=2)
        
        return ""
    
    def import_session(self, content: str, format: str = "markdown") -> Optional[Session]:
        if format == "markdown":
            lines = content.split("\n")
            title = "Imported Session"
            if lines and lines[0].startswith("# "):
                title = lines[0][2:].strip()
            
            session = self.create_session(title=title)
            
            current_role = "user"
            current_content = []
            
            for line in lines[1:]:
                if line.startswith("### "):
                    if current_content:
                        add_message(session.id, current_role, "\n".join(current_content))
                        current_content = []
                    
                    if "User" in line:
                        current_role = "user"
                    else:
                        current_role = "assistant"
                elif current_content or line.strip():
                    current_content.append(line)
            
            if current_content:
                add_message(session.id, current_role, "\n".join(current_content))
            
            return session
        
        elif format == "json":
            data = json.loads(content)
            session_data = data.get("session", {})
            messages_data = data.get("messages", [])
            
            session = self.create_session(
                title=session_data.get("title", "Imported Session"),
                mode=session_data.get("mode", "agent"),
                model=session_data.get("model"),
            )
            
            for msg in messages_data:
                add_message(session.id, msg.get("role", "user"), msg.get("content", ""))
            
            return session
        
        return None
    
    def delete_session(self, session_id: int) -> bool:
        count = delete_conversations([session_id])
        
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
        
        if str(session_id) in self._session_metadata:
            del self._session_metadata[str(session_id)]
            self._save_metadata()
        
        return count > 0
    
    def get_session_stats(self, session_id: int) -> Optional[SessionStats]:
        session = self.get_session(session_id)
        if not session:
            return None
        
        stats = session.stats
        stats.total_messages = len(get_messages(session_id))
        
        if stats.ended_at is None and stats.started_at:
            stats.duration_seconds = int((datetime.now() - stats.started_at).total_seconds())
        
        return stats
    
    def tag_session(self, session_id: int, tag: str):
        metadata = self._session_metadata.get(str(session_id), {})
        tags = metadata.get("tags", [])
        if tag not in tags:
            tags.append(tag)
            metadata["tags"] = tags
            self._session_metadata[str(session_id)] = metadata
            self._save_metadata()
    
    def untag_session(self, session_id: int, tag: str):
        metadata = self._session_metadata.get(str(session_id), {})
        tags = metadata.get("tags", [])
        if tag in tags:
            tags.remove(tag)
            metadata["tags"] = tags
            self._session_metadata[str(session_id)] = metadata
            self._save_metadata()
    
    def get_sessions_by_tag(self, tag: str) -> List[Session]:
        results = []
        for session_id_str, metadata in self._session_metadata.items():
            if tag in metadata.get("tags", []):
                session = self.get_session(int(session_id_str))
                if session:
                    results.append(session)
        return results
    
    def archive_old_sessions(self, days: int = 30) -> int:
        cutoff = datetime.now() - timedelta(days=days)
        archived = 0
        
        for session_id_str, metadata in list(self._session_metadata.items()):
            created_at = datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat()))
            if created_at < cutoff:
                metadata["state"] = SessionState.COMPLETED.value
                archived += 1
        
        self._save_metadata()
        return archived
    
    def get_recent_sessions(self, limit: int = 10) -> List[Session]:
        return self.list_sessions(limit=limit)
    
    def get_active_sessions(self) -> List[Session]:
        return self.list_sessions(state=SessionState.ACTIVE)
    
    def get_total_stats(self) -> Dict[str, int]:
        total_messages = 0
        total_sessions = len(self._session_metadata)
        total_tags = set()
        
        for session_id_str, metadata in self._session_metadata.items():
            session = self.get_session(int(session_id_str))
            if session:
                total_messages += session.stats.total_messages
                total_tags.update(metadata.get("tags", []))
        
        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "total_tags": len(total_tags),
            "active_sessions": len(self.get_active_sessions()),
        }
