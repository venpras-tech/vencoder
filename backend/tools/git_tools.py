import subprocess
import re
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
from langchain_core.tools import tool
from config import WORKSPACE_ROOT


@dataclass
class GitCommit:
    hash: str
    short_hash: str
    message: str
    author: str
    date: str
    files_changed: List[str]


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


def _is_git_repo() -> bool:
    out, code = _run_git(["rev-parse", "--is-inside-work-tree"])
    return code == 0 and "true" in out.lower()


@tool
def git_status() -> str:
    """Show git status: staged, unstaged, and untracked files. Use to see what has changed."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["status", "--short"])
    if code != 0:
        return out
    if not out:
        return "Working tree clean. No changes."
    return out[:8000]


@tool
def git_diff(ref: str = "HEAD") -> str:
    """Show git diff. ref: commit or 'HEAD' for working tree changes. Use to see exact code changes."""
    if not _is_git_repo():
        return "Not a git repository."
    if ref.upper() == "HEAD":
        out, code = _run_git(["diff", "HEAD"])
    else:
        out, code = _run_git(["diff", ref, "--"])
    if code != 0:
        return out
    if not out:
        return "No diff."
    return out[:15000]


@tool
def git_branch() -> str:
    """Show all git branches. Current branch is marked with asterisk."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["branch", "-a"])
    if code != 0:
        return out
    return out[:4000]


@tool
def git_log(n: int = 10, file_path: Optional[str] = None) -> str:
    """Show git commit history. n: number of commits to show. file_path: optionally filter by file."""
    if not _is_git_repo():
        return "Not a git repository."
    args = ["log", f"--oneline", f"-{n}", "--format=%h %s (%an) %ad", "--date=short"]
    if file_path:
        args.extend(["--", file_path])
    out, code = _run_git(args)
    if code != 0:
        return out
    if not out:
        return "No commits found."
    return out[:6000]


@tool
def git_show(commit_ref: str = "HEAD") -> str:
    """Show details of a specific commit including diff. commit_ref: commit hash or 'HEAD'."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["show", "--stat", "--patch", commit_ref])
    if code != 0:
        return out
    return out[:20000]


@tool
def git_stash(message: Optional[str] = None) -> str:
    """Stash current changes. message: optional description."""
    if not _is_git_repo():
        return "Not a git repository."
    if message:
        out, code = _run_git(["stash", "push", "-m", message])
    else:
        out, code = _run_git(["stash", "push"])
    if code != 0:
        return out
    return out or "Changes stashed."


@tool
def git_stash_list(n: int = 10) -> str:
    """List recent stashes."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["stash", "list", f"-{n}"])
    if code != 0:
        return out
    if not out:
        return "No stashes."
    return out[:4000]


@tool
def git_stash_pop() -> str:
    """Apply and remove the most recent stash."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["stash", "pop"])
    if code != 0:
        return out
    return out or "Stash applied."


@tool
def git_create_branch(branch_name: str, base: str = "HEAD") -> str:
    """Create a new git branch. branch_name: name for new branch. base: starting point (commit/branch)."""
    if not _is_git_repo():
        return "Not a git repository."
    if not re.match(r'^[a-zA-Z0-9_/-]+$', branch_name):
        return f"Invalid branch name: {branch_name}"
    out, code = _run_git(["checkout", "-b", branch_name, base])
    if code != 0:
        return out
    return f"Created and switched to branch: {branch_name}"


@tool
def git_switch_branch(branch_name: str) -> str:
    """Switch to an existing branch. branch_name: name of branch to switch to."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["checkout", branch_name])
    if code != 0:
        return out
    return f"Switched to branch: {branch_name}"


@tool
def git_delete_branch(branch_name: str, force: bool = False) -> str:
    """Delete a git branch. branch_name: branch to delete. force: force delete if not merged."""
    if not _is_git_repo():
        return "Not a git repository."
    flag = "-D" if force else "-d"
    out, code = _run_git(["branch", flag, branch_name])
    if code != 0:
        return out
    return f"Deleted branch: {branch_name}"


@tool
def git_commit(message: str, amend: bool = False) -> str:
    """Commit staged changes. message: commit message. amend: amend to previous commit."""
    if not _is_git_repo():
        return "Not a git repository."
    if amend:
        out, code = _run_git(["commit", "--amend", "--no-edit"])
    else:
        out, code = _run_git(["commit", "-m", message])
    if code != 0:
        return out
    return out or f"Committed: {message[:100]}"


@tool
def git_commit_all(message: str, amend: bool = False) -> str:
    """Commit all changes (staged + unstaged). message: commit message. amend: amend to previous commit."""
    if not _is_git_repo():
        return "Not a git repository."
    if amend:
        out, code = _run_git(["commit", "-am", message, "--amend", "--no-edit"])
    else:
        out, code = _run_git(["commit", "-am", message])
    if code != 0:
        return out
    return out or f"Committed all: {message[:100]}"


@tool
def git_add(files: str = ".") -> str:
    """Stage files for commit. files: file(s) to stage, defaults to all."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["add", files])
    if code != 0:
        return out
    return out or f"Staged: {files}"


@tool
def git_reset(file: Optional[str] = None, soft: bool = False) -> str:
    """Unstage files or reset HEAD. file: file to unstage, or None for all. soft: use soft reset."""
    if not _is_git_repo():
        return "Not a git repository."
    if file:
        out, code = _run_git(["reset", "HEAD", "--", file])
    elif soft:
        out, code = _run_git(["reset", "--soft", "HEAD~1"])
    else:
        out, code = _run_git(["reset", "HEAD"])
    if code != 0:
        return out
    return out or "Reset complete."


@tool
def git_revert(commit_ref: str) -> str:
    """Revert a commit by creating a new one. commit_ref: commit hash to revert."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["revert", "--no-edit", commit_ref])
    if code != 0:
        return out
    return f"Reverted: {commit_ref}"


@tool
def git_merge(branch: str, no_ff: bool = False, message: Optional[str] = None) -> str:
    """Merge a branch into current branch. branch: branch to merge. no_ff: force merge commit."""
    if not _is_git_repo():
        return "Not a git repository."
    args = ["merge"]
    if no_ff:
        args.append("--no-ff")
    if message:
        args.extend(["-m", message])
    args.append(branch)
    out, code = _run_git(args)
    if code != 0:
        return f"Merge failed:\n{out}"
    return f"Merged {branch} into current branch"


@tool
def git_rebase(branch: str, interactive: bool = False) -> str:
    """Rebase current branch onto another. branch: branch to rebase onto."""
    if not _is_git_repo():
        return "Not a git repository."
    if interactive:
        out, code = _run_git(["rebase", "-i", branch])
    else:
        out, code = _run_git(["rebase", branch])
    if code != 0:
        return f"Rebase failed:\n{out}"
    return f"Rebased onto {branch}"


@tool
def git_fetch(all_remotes: bool = False) -> str:
    """Fetch updates from remote. all_remotes: fetch from all remotes."""
    if not _is_git_repo():
        return "Not a git repository."
    args = ["fetch"]
    if all_remotes:
        args.append("--all")
    out, code = _run_git(args)
    if code != 0:
        return out
    return out or "Fetch complete."


@tool
def git_pull(rebase: bool = False) -> str:
    """Pull remote changes. rebase: use rebase instead of merge."""
    if not _is_git_repo():
        return "Not a git repository."
    if rebase:
        out, code = _run_git(["pull", "--rebase"])
    else:
        out, code = _run_git(["pull"])
    if code != 0:
        return out
    return out or "Pull complete."


@tool
def git_push(force: bool = False, set_upstream: bool = False, remote: str = "origin") -> str:
    """Push commits to remote. force: force push. set_upstream: set upstream branch."""
    if not _is_git_repo():
        return "Not a git repository."
    args = ["push"]
    if force:
        args.append("--force-with-lease")
    if set_upstream:
        args.append("-u")
    args.append(remote)
    out, code = _run_git(args)
    if code != 0:
        return out
    return out or "Push complete."


@tool
def git_blame(file: str, n: int = 20) -> str:
    """Show blame information for a file. file: file to blame. n: number of lines."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["blame", f"-L1,{n}", file])
    if code != 0:
        return out
    return out[:8000]


@tool
def git_grep(pattern: str, case_sensitive: bool = False, files: str = ".") -> str:
    """Search for pattern in tracked files. pattern: regex to search. case_sensitive: match case."""
    if not _is_git_repo():
        return "Not a git repository."
    args = ["grep"]
    if not case_sensitive:
        args.append("-i")
    args.append(pattern)
    args.extend(["--", files])
    out, code = _run_git(args)
    if code != 0:
        if "no matches" in out.lower():
            return "No matches found."
        return out
    return out[:10000]


@tool
def git_diff_staged(ref: str = "HEAD") -> str:
    """Show diff of staged changes. ref: base commit for comparison."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["diff", "--staged", ref])
    if code != 0:
        return out
    if not out:
        return "No staged changes."
    return out[:15000]


@tool
def git_undo_last_commit(keep_changes: bool = True) -> str:
    """Undo the last commit. keep_changes: preserve changes in working tree."""
    if not _is_git_repo():
        return "Not a git repository."
    if keep_changes:
        out, code = _run_git(["reset", "--soft", "HEAD~1"])
    else:
        out, code = _run_git(["reset", "--hard", "HEAD~1"])
    if code != 0:
        return out
    return "Last commit undone." + (" Changes preserved." if keep_changes else " Changes discarded.")


@tool
def git_clean(dry_run: bool = True, directories: bool = False, force: bool = False) -> str:
    """Remove untracked files. dry_run: show what would be removed. directories: include directories."""
    if not _is_git_repo():
        return "Not a git repository."
    args = ["clean"]
    if dry_run:
        args.append("-n")
    else:
        args.append("-f")
    if directories:
        args.append("-d")
    out, code = _run_git(args)
    if code != 0:
        return out
    if dry_run:
        if not out:
            return "Nothing to clean."
        return f"Would remove:\n{out}"
    return f"Removed:\n{out}"


@tool
def git_remote() -> str:
    """Show git remotes."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["remote", "-v"])
    if code != 0:
        return out
    if not out:
        return "No remotes configured."
    return out[:2000]


@tool
def git_current_branch() -> str:
    """Get the current branch name."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if code != 0:
        return out
    return out.strip()


@tool
def git_tag(tag_name: str, message: Optional[str] = None, annotate: bool = True) -> str:
    """Create a git tag. tag_name: name of tag. message: optional tag message."""
    if not _is_git_repo():
        return "Not a git repository."
    args = ["tag"]
    if message and annotate:
        args.extend(["-a", tag_name, "-m", message])
    else:
        args.append(tag_name)
    out, code = _run_git(args)
    if code != 0:
        return out
    return f"Created tag: {tag_name}"


@tool
def git_list_tags(pattern: Optional[str] = None) -> str:
    """List git tags. pattern: optional filter pattern."""
    if not _is_git_repo():
        return "Not a git repository."
    args = ["tag", "-l"]
    if pattern:
        args.append(pattern)
    out, code = _run_git(args)
    if code != 0:
        return out
    if not out:
        return "No tags found."
    return out[:4000]


@tool
def git_short_status() -> str:
    """Show compact git status: just file names with change indicators."""
    if not _is_git_repo():
        return "Not a git repository."
    out, code = _run_git(["status", "--porcelain"])
    if code != 0:
        return out
    if not out:
        return "Clean working tree"
    files = []
    for line in out.split("\n"):
        if line:
            status = line[:2]
            path = line[3:]
            files.append(f"{status} {path}")
    return "\n".join(files[:50])


@tool
def git_changed_files(ref1: str = "HEAD", ref2: str = "") -> str:
    """List files changed between commits. ref1: first commit. ref2: second commit or empty for working tree."""
    if not _is_git_repo():
        return "Not a git repository."
    if ref2:
        out, code = _run_git(["diff", "--name-only", ref1, ref2])
    else:
        out, code = _run_git(["diff", "--name-only", "--staged", ref1])
    if code != 0:
        return out
    if not out:
        return "No files changed."
    return out[:4000]
