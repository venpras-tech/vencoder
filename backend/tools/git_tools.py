import subprocess
from langchain_core.tools import tool
from config import WORKSPACE_ROOT


def _run_git(args: list[str], timeout: int = 30) -> tuple[str, int]:
    root = WORKSPACE_ROOT.resolve()
    if not root.exists():
        return "Workspace not found.", -1
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode != 0 and not out:
            return err or f"git exited {result.returncode}", result.returncode
        return out or "(no output)", result.returncode
    except FileNotFoundError:
        return "Git is not installed or not in PATH.", -1
    except subprocess.TimeoutExpired:
        return "Git command timed out.", -1
    except Exception as e:
        return str(e), -1


@tool
def git_status() -> str:
    """Show git status: staged, unstaged, and untracked files. Use to see what has changed."""
    out, code = _run_git(["status", "--short"])
    if code != 0:
        return out
    if not out:
        return "Working tree clean. No changes."
    return out[:8000]


@tool
def git_diff(ref: str = "HEAD") -> str:
    """Show git diff. ref: commit or 'HEAD' for working tree changes. Use to see exact code changes."""
    if ref.upper() == "HEAD":
        out, code = _run_git(["diff", "HEAD"])
    else:
        out, code = _run_git(["diff", ref, "--"])
    if code != 0:
        return out
    if not out:
        return "No diff."
    return out[:15000]
