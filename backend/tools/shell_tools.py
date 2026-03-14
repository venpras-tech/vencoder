import json
import re
import subprocess
import threading
import time
from langchain_core.tools import tool
from config import WORKSPACE_ROOT

_UI_MARKER = "\n__UI__\n"
_shell_cancel_event = threading.Event()


def request_shell_cancel():
    _shell_cancel_event.set()


_BLOCKED_PATTERNS = [
    re.compile(r"rm\s+-rf\s+/(\s|$)", re.I),
    re.compile(r"rm\s+-rf\s+\*", re.I),
    re.compile(r"\|\s*(bash|sh)\s*$", re.I),
    re.compile(r">\s*/dev/sd", re.I),
    re.compile(r"mkfs\.", re.I),
    re.compile(r":\s*\(\s*\)\s*\{", re.I),
]


def _validate_shell_command(cmd: str) -> str | None:
    stripped = cmd.strip()
    for pat in _BLOCKED_PATTERNS:
        if pat.search(stripped):
            return f"Blocked: command matches dangerous pattern"
    return None


def _read_pipe(pipe, buf):
    try:
        for line in pipe:
            buf.append(line)
    except (ValueError, OSError):
        pass


@tool
def shell_command(command: str, timeout_seconds: int = 120) -> str:
    """Run a shell command in the workspace directory. Use for listing files, running scripts, etc. Timeout in seconds."""
    err = _validate_shell_command(command)
    if err:
        return f"Error: {err}"
    _shell_cancel_event.clear()
    stdout_buf, stderr_buf = [], []
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        t_out = threading.Thread(target=_read_pipe, args=(proc.stdout, stdout_buf), daemon=True)
        t_err = threading.Thread(target=_read_pipe, args=(proc.stderr, stderr_buf), daemon=True)
        t_out.start()
        t_err.start()
        start = time.monotonic()
        cancelled = False
        while proc.poll() is None:
            if _shell_cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                cancelled = True
                break
            if timeout_seconds and (time.monotonic() - start) >= timeout_seconds:
                proc.terminate()
                time.sleep(1)
                if proc.poll() is None:
                    proc.kill()
                raise subprocess.TimeoutExpired(command, timeout_seconds)
            time.sleep(0.2)
        t_out.join(timeout=2)
        t_err.join(timeout=2)
        out = "".join(stdout_buf)
        err_out = "".join(stderr_buf)
        exit_code = proc.returncode if proc.returncode is not None else (-9 if cancelled else -1)
        if cancelled:
            err_out = (err_out + "\n" if err_out else "") + "cancelled by user"
        if err_out:
            summary = out + "\n[stderr]\n" + err_out
        else:
            summary = out
        if exit_code != 0:
            summary = f"[exit code {exit_code}]\n" + summary
        summary = summary.strip() or "(no output)"
        ui = {"type": "shell_run", "command": command, "stdout": out, "stderr": err_out, "exit_code": exit_code}
        return f"{summary}{_UI_MARKER}{json.dumps(ui)}"
    except subprocess.TimeoutExpired:
        ui = {"type": "shell_run", "command": command, "stdout": "", "stderr": "command timed out", "exit_code": -1}
        return f"Error: command timed out{_UI_MARKER}{json.dumps(ui)}"
    except Exception as e:
        ui = {"type": "shell_run", "command": command, "stdout": "", "stderr": str(e), "exit_code": -1}
        return f"Error: {e}{_UI_MARKER}{json.dumps(ui)}"


@tool
def run_tests(command: str = "pytest", timeout_seconds: int = 120) -> str:
    """Run tests. Default: pytest. Use npm test, cargo test, etc. based on project. Returns output and exit code."""
    return shell_command.invoke({"command": command, "timeout_seconds": timeout_seconds})
