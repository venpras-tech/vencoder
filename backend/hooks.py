import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from config import WORKSPACE_ROOT


class HookEvent(Enum):
    BEFORE_EDIT = "before_edit"
    AFTER_EDIT = "after_edit"
    BEFORE_SHELL = "before_shell"
    AFTER_SHELL = "after_shell"
    BEFORE_COMMIT = "before_commit"
    AFTER_COMMIT = "after_commit"
    BEFORE_TEST = "before_test"
    AFTER_TEST = "after_test"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    MESSAGE_SENT = "message_sent"
    TOOL_CALLED = "tool_called"


@dataclass
class Hook:
    name: str
    event: str
    command: Optional[str] = None
    script: Optional[str] = None
    condition: Optional[str] = None
    enabled: bool = True
    timeout: int = 30
    description: str = ""
    priority: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Hook':
        return cls(**data)

    def matches_event(self, event: HookEvent) -> bool:
        return self.event == event.value


@dataclass
class HookResult:
    success: bool
    output: str
    error: Optional[str] = None
    hook_name: str = ""
    event: str = ""
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class HookContext:
    workspace_root: Path
    session_id: Optional[str] = None
    user_message: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict] = None
    file_path: Optional[str] = None
    command: Optional[str] = None
    commit_message: Optional[str] = None
    test_output: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class HookManager:
    TRIGGERS = {
        HookEvent.BEFORE_EDIT: ["before_file_edit", "pre_edit"],
        HookEvent.AFTER_EDIT: ["after_file_edit", "post_edit"],
        HookEvent.BEFORE_SHELL: ["before_shell_command", "pre_shell"],
        HookEvent.AFTER_SHELL: ["after_shell_command", "post_shell"],
        HookEvent.BEFORE_COMMIT: ["pre_commit", "before_git_commit"],
        HookEvent.AFTER_COMMIT: ["post_commit", "after_git_commit"],
        HookEvent.BEFORE_TEST: ["pre_test", "before_running_tests"],
        HookEvent.AFTER_TEST: ["post_test", "after_running_tests"],
        HookEvent.SESSION_START: ["session_start", "on_start"],
        HookEvent.SESSION_END: ["session_end", "on_exit"],
        HookEvent.MESSAGE_SENT: ["on_message", "message_sent"],
        HookEvent.TOOL_CALLED: ["tool_called", "on_tool_call"],
    }

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT
        self.hooks_dir = self.workspace_root / ".vencoder" / "hooks"
        self.hooks_dir.mkdir(parents=True, exist_ok=True)
        self._hooks_cache: Dict[str, List[Hook]] = {}
        self._load_builtin_hooks()
        self._load_user_hooks()

    def _load_builtin_hooks(self):
        builtin_hooks_path = Path(__file__).parent / "builtin_hooks.json"
        if builtin_hooks_path.exists():
            try:
                data = json.loads(builtin_hooks_path.read_text())
                for hook_data in data.get("hooks", []):
                    hook = Hook.from_dict(hook_data)
                    self._hooks_cache.setdefault(hook.event, []).append(hook)
            except Exception:
                pass

    def _load_user_hooks(self):
        for hook_file in self.hooks_dir.glob("*.json"):
            try:
                data = json.loads(hook_file.read_text())
                hook = Hook.from_dict(data)
                self._hooks_cache.setdefault(hook.event, []).append(hook)
            except Exception:
                pass

    def get_hooks_for_event(self, event: HookEvent) -> List[Hook]:
        hooks = self._hooks_cache.get(event.value, [])
        return sorted([h for h in hooks if h.enabled], key=lambda x: x.priority, reverse=True)

    def get_all_hooks(self) -> Dict[str, List[Hook]]:
        return self._hooks_cache.copy()

    def register_hook(self, hook: Hook) -> bool:
        try:
            hook_file = self.hooks_dir / f"{hook.name}.json"
            hook_file.write_text(json.dumps(hook.to_dict(), indent=2))
            self._hooks_cache.setdefault(hook.event, []).append(hook)
            return True
        except Exception:
            return False

    def unregister_hook(self, hook_name: str) -> bool:
        for event, hooks in self._hooks_cache.items():
            for hook in hooks:
                if hook.name == hook_name:
                    hooks.remove(hook)
                    hook_file = self.hooks_dir / f"{hook_name}.json"
                    if hook_file.exists():
                        hook_file.unlink()
                    return True
        return False

    def enable_hook(self, hook_name: str) -> bool:
        for event, hooks in self._hooks_cache.items():
            for hook in hooks:
                if hook.name == hook_name:
                    hook.enabled = True
                    return self.register_hook(hook)
        return False

    def disable_hook(self, hook_name: str) -> bool:
        for event, hooks in self._hooks_cache.items():
            for hook in hooks:
                if hook.name == hook_name:
                    hook.enabled = False
                    return self.register_hook(hook)
        return False

    def run_hooks(self, event: HookEvent, context: HookContext) -> List[HookResult]:
        results = []
        hooks = self.get_hooks_for_event(event)

        for hook in hooks:
            result = self._execute_hook(hook, event, context)
            results.append(result)

        return results

    def _execute_hook(self, hook: Hook, event: HookEvent, context: HookContext) -> HookResult:
        if hook.condition:
            if not self._evaluate_condition(hook.condition, context):
                return HookResult(
                    success=True,
                    output="",
                    hook_name=hook.name,
                    event=hook.event,
                    skipped=True,
                    skip_reason="Condition not met",
                )

        if hook.script:
            return self._run_script_hook(hook, event, context)
        elif hook.command:
            return self._run_command_hook(hook, event, context)
        else:
            return HookResult(
                success=False,
                output="",
                error="Hook has no command or script",
                hook_name=hook.name,
                event=hook.event,
            )

    def _run_command_hook(self, hook: Hook, event: HookEvent, context: HookContext) -> HookResult:
        command = self._interpolate_command(hook.command, context)

        env = os.environ.copy()
        env["HOOK_EVENT"] = hook.event
        env["HOOK_NAME"] = hook.name
        env["HOOK_WORKSPACE"] = str(self.workspace_root)
        if context.session_id:
            env["HOOK_SESSION_ID"] = context.session_id
        if context.user_message:
            env["HOOK_USER_MESSAGE"] = context.user_message[:500]
        if context.tool_name:
            env["HOOK_TOOL_NAME"] = context.tool_name
        if context.file_path:
            env["HOOK_FILE_PATH"] = context.file_path
        if context.command:
            env["HOOK_COMMAND"] = context.command

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                env=env,
            )

            if result.returncode == 0:
                return HookResult(
                    success=True,
                    output=result.stdout.strip(),
                    hook_name=hook.name,
                    event=hook.event,
                )
            else:
                return HookResult(
                    success=False,
                    output=result.stdout.strip(),
                    error=result.stderr.strip() or f"Hook exited with code {result.returncode}",
                    hook_name=hook.name,
                    event=hook.event,
                )
        except subprocess.TimeoutExpired:
            return HookResult(
                success=False,
                output="",
                error=f"Hook '{hook.name}' timed out after {hook.timeout}s",
                hook_name=hook.name,
                event=hook.event,
            )
        except Exception as e:
            return HookResult(
                success=False,
                output="",
                error=str(e),
                hook_name=hook.name,
                event=hook.event,
            )

    def _run_script_hook(self, hook: Hook, event: HookEvent, context: HookContext) -> HookResult:
        script_content = hook.script

        script_file = self.hooks_dir / f"_{hook.name}_temp.py"
        try:
            script_file.write_text(script_content)

            env = os.environ.copy()
            env["HOOK_EVENT"] = hook.event
            env["HOOK_NAME"] = hook.name

            result = subprocess.run(
                ["python", str(script_file)],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                env=env,
            )

            if result.returncode == 0:
                return HookResult(
                    success=True,
                    output=result.stdout.strip(),
                    hook_name=hook.name,
                    event=hook.event,
                )
            else:
                return HookResult(
                    success=False,
                    output=result.stdout.strip(),
                    error=result.stderr.strip() or f"Script exited with code {result.returncode}",
                    hook_name=hook.name,
                    event=hook.event,
                )
        except Exception as e:
            return HookResult(
                success=False,
                output="",
                error=str(e),
                hook_name=hook.name,
                event=hook.event,
            )
        finally:
            if script_file.exists():
                script_file.unlink()

    def _evaluate_condition(self, condition: str, context: HookContext) -> bool:
        try:
            local_vars = {
                "workspace": str(self.workspace_root),
                "session_id": context.session_id,
                "user_message": context.user_message,
                "tool_name": context.tool_name,
                "file_path": context.file_path,
                "command": context.command,
                "commit_message": context.commit_message,
                "metadata": context.metadata,
            }

            condition_clean = condition.strip()
            if condition_clean.startswith("return "):
                return eval(condition_clean, {"__builtins__": {}}, local_vars)
            else:
                return eval(condition_clean, {"__builtins__": {}}, local_vars)
        except Exception:
            return True

    def _interpolate_command(self, command: str, context: HookContext) -> str:
        result = command

        replacements = {
            "{workspace}": str(self.workspace_root),
            "{file}": context.file_path or "",
            "{command}": context.command or "",
            "{tool}": context.tool_name or "",
            "{message}": context.user_message or "",
            "{session}": context.session_id or "",
        }

        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        return result

    def list_hooks(self) -> List[Dict]:
        hooks = []
        for event, event_hooks in self._hooks_cache.items():
            for hook in event_hooks:
                hooks.append({
                    "name": hook.name,
                    "event": hook.event,
                    "description": hook.description,
                    "command": hook.command[:50] + "..." if hook.command and len(hook.command) > 50 else hook.command,
                    "enabled": hook.enabled,
                    "priority": hook.priority,
                    "condition": hook.condition,
                })
        return hooks

    def create_hook_from_template(self, template_name: str) -> Optional[Hook]:
        templates = {
            "pre-commit-lint": Hook(
                name="pre-commit-lint",
                event=HookEvent.BEFORE_COMMIT.value,
                command="npm run lint 2>/dev/null || ruff check .",
                description="Run linter before commit",
                priority=10,
            ),
            "pre-commit-test": Hook(
                name="pre-commit-test",
                event=HookEvent.BEFORE_COMMIT.value,
                command="npm test 2>/dev/null || pytest",
                description="Run tests before commit",
                priority=5,
            ),
            "pre-edit-format": Hook(
                name="pre-edit-format",
                event=HookEvent.BEFORE_EDIT.value,
                command="ruff format {file}",
                description="Format file before editing",
                priority=0,
            ),
            "post-edit-format": Hook(
                name="post-edit-format",
                event=HookEvent.AFTER_EDIT.value,
                command="ruff format {file}",
                description="Format file after editing",
                priority=0,
            ),
            "post-test-coverage": Hook(
                name="post-test-coverage",
                event=HookEvent.AFTER_TEST.value,
                command="python -m coverage report --fail-under=80",
                description="Check test coverage after tests",
                priority=0,
                condition="'fail' not in str(context.metadata.get('test_result', '')).lower()",
            ),
        }

        template = templates.get(template_name)
        if template:
            self.register_hook(template)
        return template

    def get_available_templates(self) -> List[str]:
        return [
            "pre-commit-lint",
            "pre-commit-test",
            "pre-edit-format",
            "post-edit-format",
            "post-test-coverage",
        ]


def run_hooks(event: HookEvent, context: HookContext) -> List[HookResult]:
    manager = HookManager()
    return manager.run_hooks(event, context)


if __name__ == "__main__":
    manager = HookManager()
    print("=== Available Hooks ===")
    for hook in manager.list_hooks():
        print(f"  {hook['name']}: {hook['description']}")
        print(f"     Event: {hook['event']}")
        print(f"     Command: {hook['command']}")
        print(f"     Enabled: {hook['enabled']}")
        print()
