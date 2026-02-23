import json
import subprocess
from pathlib import Path
from langchain_core.tools import tool
from config import WORKSPACE_ROOT

_UI_MARKER = "\n__UI__\n"


@tool
def shell_command(command: str, timeout_seconds: int = 120) -> str:
    """Run a shell command in the workspace directory. Use for listing files, running scripts, etc. Timeout in seconds."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )
        out = result.stdout or ""
        err = result.stderr or ""
        exit_code = result.returncode
        if err:
            summary = out + "\n[stderr]\n" + err
        else:
            summary = out
        if exit_code != 0:
            summary = f"[exit code {exit_code}]\n" + summary
        summary = summary.strip() or "(no output)"
        ui = {"type": "shell_run", "command": command, "stdout": result.stdout or "", "stderr": result.stderr or "", "exit_code": exit_code}
        return f"{summary}{_UI_MARKER}{json.dumps(ui)}"
    except subprocess.TimeoutExpired:
        ui = {"type": "shell_run", "command": command, "stdout": "", "stderr": "command timed out", "exit_code": -1}
        return f"Error: command timed out{_UI_MARKER}{json.dumps(ui)}"
    except Exception as e:
        ui = {"type": "shell_run", "command": command, "stdout": "", "stderr": str(e), "exit_code": -1}
        return f"Error: {e}{_UI_MARKER}{json.dumps(ui)}"
