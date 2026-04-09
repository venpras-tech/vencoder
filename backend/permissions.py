import json
import re
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass, field
from contextvars import ContextVar

class PermissionMode(Enum):
    ASK = "ask"
    AUTO_EDIT = "auto_edit"
    PLAN = "plan"
    AUTO = "auto"

class ActionType(Enum):
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    FILE_DELETE = "file_delete"
    FILE_RENAME = "file_rename"
    COMMAND_EXEC = "command_exec"
    SHELL_COMMAND = "shell_command"
    WEB_REQUEST = "web_request"
    MCP_TOOL = "mcp_tool"
    GIT_OPERATION = "git_operation"

@dataclass
class Action:
    type: ActionType
    target: str
    details: Optional[Dict] = None
    requires_confirmation: bool = True
    
@dataclass
class PendingConfirmation:
    action: Action
    timestamp: str
    response_callback: Optional[Callable] = None

_current_mode: ContextVar[PermissionMode] = ContextVar('current_mode', default=PermissionMode.ASK)
_pending_confirmations: ContextVar[List[PendingConfirmation]] = ContextVar('pending_confirmations', default_factory=list)

DANGEROUS_PATTERNS = [
    (r'rm\s+-rf\s+/', "Deleting root directory"),
    (r'rm\s+-rf\s+/[^\s]+', "Recursive force delete from root"),
    (r'dd\s+if=', "Direct disk write"),
    (r'mkfs', "Filesystem format"),
    (r':\(\)\{', "Fork bomb"),
    (r'curl\s+.*\|\s*sh', "Pipe to shell"),
    (r'wget\s+.*\|\s*sh', "Download and pipe to shell"),
]

DANGEROUS_COMMANDS = {
    'sudo', 'su', 'passwd', 'chmod', 'chown', 'useradd', 'userdel',
    'shutdown', 'reboot', 'halt', 'init', 'systemctl', 'service',
    'killall', 'pkill', 'fdisk', 'parted', 'lvdisplay', 'vgdisplay',
    'mount', 'umount', 'cryptsetup', 'luksformat',
}

SAFE_COMMANDS = {
    'git', 'npm', 'npx', 'yarn', 'pnpm', 'node', 'python', 'python3',
    'pip', 'pip3', 'poetry', 'uv', 'cargo', 'rustc', 'go', 'java',
    'javac', 'make', 'cmake', 'gcc', 'g++', 'clang', 'clang++',
    'pytest', 'unittest', 'jest', 'vitest', 'mypy', 'ruff', 'eslint',
    'prettier', 'black', 'ruff', 'ruff', 'format', 'build', 'test',
    'run', 'dev', 'start', 'serve', 'build', 'typecheck', 'lint',
}

class PermissionManager:
    def __init__(self, settings_path: Optional[Path] = None):
        self.settings_path = settings_path
        self._mode = PermissionMode.ASK
        self._allowed_commands: List[str] = []
        self._denied_commands: List[str] = []
        self._allowed_paths: List[str] = []
        self._denied_paths: List[str] = []
        self._auto_memory_enabled = True
        self._load_settings()
        
    def _load_settings(self):
        if self.settings_path and self.settings_path.exists():
            try:
                data = json.loads(self.settings_path.read_text())
                mode_str = data.get("permission_mode", "ask")
                self._mode = PermissionMode(mode_str)
                self._allowed_commands = data.get("allowed_commands", [])
                self._denied_commands = data.get("denied_commands", [])
                self._allowed_paths = data.get("allowed_paths", [])
                self._denied_paths = data.get("denied_paths", [])
                self._auto_memory_enabled = data.get("auto_memory_enabled", True)
            except (json.JSONDecodeError, ValueError):
                pass
                
    def _save_settings(self):
        if self.settings_path:
            data = {
                "permission_mode": self._mode.value,
                "allowed_commands": self._allowed_commands,
                "denied_commands": self._denied_commands,
                "allowed_paths": self._allowed_paths,
                "denied_paths": self._denied_paths,
                "auto_memory_enabled": self._auto_memory_enabled,
            }
            self.settings_path.write_text(json.dumps(data, indent=2))
            
    def get_mode(self) -> PermissionMode:
        return self._mode
        
    def set_mode(self, mode: PermissionMode):
        self._mode = mode
        _current_mode.set(mode)
        self._save_settings()
        
    def cycle_mode(self) -> PermissionMode:
        modes = list(PermissionMode)
        current_idx = modes.index(self._mode)
        next_idx = (current_idx + 1) % len(modes)
        self.set_mode(modes[next_idx])
        return self._mode
        
    def allow_command(self, command: str):
        if command not in self._allowed_commands:
            self._allowed_commands.append(command)
            self._save_settings()
            
    def deny_command(self, command: str):
        if command in self._allowed_commands:
            self._allowed_commands.remove(command)
        if command not in self._denied_commands:
            self._denied_commands.append(command)
        self._save_settings()
            
    def allow_path(self, path: str):
        if path not in self._allowed_paths:
            self._allowed_paths.append(path)
            self._save_settings()
            
    def deny_path(self, path: str):
        if path not in self._denied_paths:
            self._denied_paths.append(path)
            self._save_settings()
            
    def can_execute(self, action: Action) -> bool:
        if self._mode == PermissionMode.AUTO:
            return True
            
        if self._mode == PermissionMode.PLAN:
            return action.type in [
                ActionType.FILE_READ,
                ActionType.WEB_REQUEST,
                ActionType.COMMAND_EXEC,
            ]
            
        if self._mode == PermissionMode.AUTO_EDIT:
            allowed_types = [
                ActionType.FILE_READ,
                ActionType.FILE_EDIT,
                ActionType.FILE_WRITE,
                ActionType.GIT_OPERATION,
            ]
            if action.type in allowed_types:
                return True
                
        if action.type in [ActionType.FILE_READ, ActionType.WEB_REQUEST]:
            return True
            
        return False
        
    def should_ask(self, action: Action) -> bool:
        if self._mode == PermissionMode.AUTO:
            return False
        if self._mode == PermissionMode.PLAN:
            return True
        if self._mode == PermissionMode.AUTO_EDIT:
            return action.type not in [
                ActionType.FILE_READ,
                ActionType.FILE_EDIT,
                ActionType.FILE_WRITE,
            ]
        return True
        
    def check_dangerous_command(self, command: str) -> Optional[str]:
        command_lower = command.lower().strip()
        
        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, command_lower):
                return f"Dangerous pattern detected: {description}"
                
        parts = command_lower.split()
        if parts and parts[0] in DANGEROUS_COMMANDS:
            if parts[0] not in self._allowed_commands and parts[0] not in SAFE_COMMANDS:
                return f"Potentially dangerous command: {parts[0]}"
                
        return None
        
    def check_path_safety(self, path: str) -> bool:
        path_obj = Path(path).resolve()
        
        for denied in self._denied_paths:
            if str(path_obj).startswith(denied):
                return False
                
        return True
        
    def validate_shell_command(self, command: str) -> tuple[bool, Optional[str]]:
        danger = self.check_dangerous_command(command)
        if danger:
            return False, danger
            
        parts = command.strip().split()
        if not parts:
            return False, "Empty command"
            
        cmd = parts[0]
        
        if cmd in self._denied_commands:
            return False, f"Command '{cmd}' is explicitly denied"
            
        if cmd in self._allowed_commands:
            return True, None
            
        if self._mode == PermissionMode.AUTO:
            return True, None
            
        return False, f"Command '{cmd}' requires explicit permission"
        
    def validate_file_operation(self, path: str, operation: ActionType) -> tuple[bool, Optional[str]]:
        if not self.check_path_safety(path):
            return False, f"Path is in denied list: {path}"
            
        path_obj = Path(path)
        if operation in [ActionType.FILE_DELETE, ActionType.FILE_RENAME]:
            if not path_obj.exists():
                return True, None
                
            parent = path_obj.parent
            test_file = parent / ".vencoder_protected"
            if test_file.exists():
                return False, "Cannot modify files in protected directory"
                
        return True, None
        
    def get_permission_summary(self) -> Dict:
        return {
            "mode": self._mode.value,
            "mode_description": self._get_mode_description(),
            "allowed_commands_count": len(self._allowed_commands),
            "denied_commands_count": len(self._denied_commands),
            "allowed_paths_count": len(self._allowed_paths),
            "denied_paths_count": len(self._denied_paths),
        }
        
    def _get_mode_description(self) -> str:
        descriptions = {
            PermissionMode.ASK: "Ask before file edits and shell commands",
            PermissionMode.AUTO_EDIT: "Auto-edit files, ask for commands",
            PermissionMode.PLAN: "Read-only mode, creates plans only",
            PermissionMode.AUTO: "Full autonomy with safety checks",
        }
        return descriptions.get(self._mode, "Unknown")
        
    def reset_to_defaults(self):
        self._mode = PermissionMode.ASK
        self._allowed_commands = []
        self._denied_commands = []
        self._allowed_paths = []
        self._denied_paths = []
        self._save_settings()
        
    def get_allowed_commands(self) -> List[str]:
        return self._allowed_commands.copy()
        
    def get_denied_commands(self) -> List[str]:
        return self._denied_commands.copy()
