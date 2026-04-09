import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict

MAX_MEMORY_LINES = 200
MAX_MEMORY_CHARS = 25 * 1024

@dataclass
class MemoryEntry:
    category: str
    content: str
    created_at: str
    source: str = "auto"

class MemoryManager:
    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self.vencoder_dir = self.workspace_root / ".vencoder"
        self.memory_file = self.vencoder_dir / "memory.md"
        self.conventions_file = self.vencoder_dir / "conventions.md"
        self.auto_memory_file = self.vencoder_dir / "auto_memory.json"
        self.settings_file = self.vencoder_dir / "settings.json"
        self._ensure_vencoder_dir()
        
    def _ensure_vencoder_dir(self):
        self.vencoder_dir.mkdir(parents=True, exist_ok=True)
        self._init_memory_file()
        self._init_auto_memory()
        self._init_settings()
        
    def _init_memory_file(self):
        if not self.memory_file.exists():
            self.memory_file.write_text("# Memory\n\n# Project Overview\n\n# Current Task Focus\n\n")
            
    def _init_auto_memory(self):
        if not self.auto_memory_file.exists():
            self.auto_memory_file.write_text(json.dumps({"entries": []}, indent=2))
            
    def _init_settings(self):
        if not self.settings_file.exists():
            self._default_settings().to_file(self.settings_file)
            
    def _default_settings(self) -> 'MemorySettings':
        return MemorySettings()
    
    def get_session_context(self) -> str:
        context_parts = []
        
        conventions = self._load_conventions()
        if conventions:
            context_parts.append(f"## Project Conventions\n{conventions}\n")
        
        memory_content = self._load_memory_content()
        if memory_content:
            context_parts.append(f"## Project Memory\n{memory_content}\n")
            
        auto_memory = self._load_auto_memory()
        if auto_memory:
            context_parts.append(f"## Learned Context\n{auto_memory}\n")
            
        return "\n".join(context_parts) if context_parts else ""
    
    def _load_memory_content(self) -> str:
        if not self.memory_file.exists():
            return ""
        content = self.memory_file.read_text()
        lines = content.split("\n")
        if len(lines) > MAX_MEMORY_LINES:
            lines = lines[:MAX_MEMORY_LINES]
        content = "\n".join(lines)
        if len(content) > MAX_MEMORY_CHARS:
            content = content[:MAX_MEMORY_CHARS]
        return content
    
    def _load_conventions(self) -> str:
        if not self.conventions_file.exists():
            return ""
        return self.conventions_file.read_text().strip()
    
    def _load_auto_memory(self) -> str:
        try:
            data = json.loads(self.auto_memory_file.read_text())
            entries = data.get("entries", [])
            if not entries:
                return ""
            lines = ["# Auto-learned Information"]
            for entry in entries[-20:]:
                lines.append(f"- [{entry['category']}] {entry['content']}")
            return "\n".join(lines)
        except (json.JSONDecodeError, KeyError):
            return ""
    
    def save_learning(self, category: str, content: str, source: str = "auto"):
        try:
            data = json.loads(self.auto_memory_file.read_text())
            entries = data.get("entries", [])
            
            entry = MemoryEntry(
                category=category,
                content=content,
                created_at=datetime.now().isoformat(),
                source=source
            )
            entries.append(asdict(entry))
            
            if len(entries) > 100:
                entries = entries[-100:]
                
            data["entries"] = entries
            self.auto_memory_file.write_text(json.dumps(data, indent=2))
            return True
        except Exception:
            return False
    
    def learn_project_structure(self, structure_summary: str):
        self.save_learning("structure", structure_summary, "auto")
        
    def learn_code_pattern(self, pattern: str, context: str):
        self.save_learning("pattern", f"{pattern}: {context}", "auto")
        
    def learn_user_preference(self, preference: str):
        self.save_learning("preference", preference, "user")
    
    def get_project_conventions(self) -> str:
        return self._load_conventions()
    
    def set_project_conventions(self, content: str):
        self.conventions_file.write_text(content)
        
    def get_memory_content(self) -> str:
        return self._load_memory_content()
    
    def set_memory_content(self, content: str):
        self.memory_file.write_text(content)
    
    def append_to_memory(self, section: str, content: str):
        current = self._load_memory_content()
        marker = f"# {section}"
        if marker in current:
            parts = current.split(marker)
            before = parts[0]
            after_marker = parts[1].split("\n# ")
            after = "\n# ".join(after_marker[1:]) if len(after_marker) > 1 else ""
            new_content = f"{before}{marker}\n{content}\n"
            if after:
                new_content += f"# {after}"
        else:
            new_content = current + f"\n{marker}\n{content}\n"
        self.memory_file.write_text(new_content)
        
    def get_all_auto_entries(self) -> List[Dict]:
        try:
            data = json.loads(self.auto_memory_file.read_text())
            return data.get("entries", [])
        except json.JSONDecodeError:
            return []
    
    def clear_auto_memory(self):
        self.auto_memory_file.write_text(json.dumps({"entries": []}, indent=2))
        
    def get_settings(self) -> Dict:
        try:
            return json.loads(self.settings_file.read_text())
        except json.JSONDecodeError:
            return {}
    
    def update_settings(self, updates: Dict):
        current = self.get_settings()
        current.update(updates)
        self.settings_file.write_text(json.dumps(current, indent=2))
        
    def get_memory_stats(self) -> Dict:
        memory_lines = len(self._load_memory_content().split("\n"))
        convention_lines = len(self._load_conventions().split("\n"))
        auto_entries = len(self.get_all_auto_entries())
        return {
            "memory_lines": memory_lines,
            "convention_lines": convention_lines,
            "auto_entries": auto_entries,
            "total_entries": memory_lines + convention_lines + auto_entries
        }


class MemorySettings:
    def __init__(self):
        self.permission_mode = "ask"
        self.allowed_commands = []
        self.max_history = 50
        self.auto_memory_enabled = True
        self.hooks_enabled = True
        
    def to_dict(self) -> Dict:
        return {
            "permission_mode": self.permission_mode,
            "allowed_commands": self.allowed_commands,
            "max_history": self.max_history,
            "auto_memory_enabled": self.auto_memory_enabled,
            "hooks_enabled": self.hooks_enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemorySettings':
        settings = cls()
        settings.permission_mode = data.get("permission_mode", "ask")
        settings.allowed_commands = data.get("allowed_commands", [])
        settings.max_history = data.get("max_history", 50)
        settings.auto_memory_enabled = data.get("auto_memory_enabled", True)
        settings.hooks_enabled = data.get("hooks_enabled", True)
        return settings
    
    def to_file(self, path: Path):
        path.write_text(json.dumps(self.to_dict(), indent=2))
        
    @classmethod
    def from_file(cls, path: Path) -> 'MemorySettings':
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return cls.from_dict(data)
            except json.JSONDecodeError:
                pass
        return cls()
