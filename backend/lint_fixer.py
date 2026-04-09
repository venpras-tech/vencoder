import subprocess
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from config import WORKSPACE_ROOT


@dataclass
class LintIssue:
    file: str
    line: int
    column: Optional[int]
    rule: str
    message: str
    severity: str
    fixable: bool


@dataclass
class LintResult:
    passed: bool
    issues: List[LintIssue]
    output: str
    command: str
    fixed: bool = False


class LintFixer:
    LINTERS = {
        "python": {
            "ruff": {
                "ext": [".py"],
                "check": ["ruff", "check", "{{file}}"],
                "fix": ["ruff", "check", "--fix", "{{file}}"],
                "format": ["ruff", "format", "{{file}}"],
                "parse": r"(.+?):(\d+):(\d+):\s*(\w+)\s+(.+)",
            },
            "flake8": {
                "ext": [".py"],
                "check": ["flake8", "{{file}}"],
                "fix": ["autopep8", "--in-place", "--aggressive", "{{file}}"],
                "parse": r"(.+?):(\d+):(\d+):\s*(\w+)\s+(.+)",
            },
            "pylint": {
                "ext": [".py"],
                "check": ["pylint", "{{file}}", "--output-format=text"],
                "fix": None,
                "parse": r"(.+?):(\d+):\s*(\w+)\s*:\s*(.+)",
            },
            "black": {
                "ext": [".py"],
                "check": ["black", "--check", "--diff", "{{file}}"],
                "fix": ["black", "{{file}}"],
                "parse": r"Would reformatted (.+)",
            },
        },
        "javascript": {
            "eslint": {
                "ext": [".js", ".jsx", ".mjs"],
                "check": ["npx", "eslint", "{{file}}"],
                "fix": ["npx", "eslint", "--fix", "{{file}}"],
                "parse": r"(.+?):\s*line\s*(\d+)\s*col\s*(\d+)\s*(\w+)\s*/\s*(.+)",
            },
            "prettier": {
                "ext": [".js", ".jsx", ".ts", ".tsx", ".css", ".json"],
                "check": ["npx", "prettier", "--check", "{{file}}"],
                "fix": ["npx", "prettier", "--write", "{{file}}"],
                "parse": r"Checking\spattern\s*\.\.\.\s*(.+)",
            },
        },
        "typescript": {
            "eslint": {
                "ext": [".ts", ".tsx"],
                "check": ["npx", "eslint", "{{file}}"],
                "fix": ["npx", "eslint", "--fix", "{{file}}"],
                "parse": r"(.+?):\s*line\s*(\d+)\s*col\s*(\d+)\s*(\w+)\s*/\s*(.+)",
            },
            "prettier": {
                "ext": [".ts", ".tsx"],
                "check": ["npx", "prettier", "--check", "{{file}}"],
                "fix": ["npx", "prettier", "--write", "{{file}}"],
                "parse": r"Checking\spattern\s*\.\.\.\s*(.+)",
            },
        },
        "rust": {
            "clippy": {
                "ext": [".rs"],
                "check": ["cargo", "clippy", "--message-format=json", "-Z", "unstable-options"],
                "fix": ["cargo", "clippy", "--fix", "--allow-dirty"],
                "parse": r"(.+?)\((\d+)\s*\d+\):\s*(.+)",
            },
            "rustfmt": {
                "ext": [".rs"],
                "check": ["cargo", "fmt", "--check"],
                "fix": ["cargo", "fmt"],
                "parse": r"Diff\s*in\s*(.+?)\s*against",
            },
        },
        "go": {
            "gofmt": {
                "ext": [".go"],
                "check": ["gofmt", "-l", "{{file}}"],
                "fix": ["gofmt", "-w", "{{file}}"],
                "parse": r"(.+)",
            },
            "golangci-lint": {
                "ext": [".go"],
                "check": ["golangci-lint", "run", "{{file}}"],
                "fix": None,
                "parse": r"(.+?):(\d+):(\d+):\s*(.+)",
            },
        },
        "css": {
            "stylelint": {
                "ext": [".css", ".scss", ".less"],
                "check": ["npx", "stylelint", "{{file}}"],
                "fix": ["npx", "stylelint", "--fix", "{{file}}"],
                "parse": r"(.+?):(\d+):(\d+):\s*(\w+)\s*(.+)",
            },
        },
        "json": {
            "jsonlint": {
                "ext": [".json"],
                "check": ["npx", "jsonlint", "{{file}}"],
                "fix": ["npx", "jsonlint", "--in-place", "{{file}}"],
                "parse": r"(.+?):\s*line\s*(\d+)\s*col\s*(\d+)\s*(.+)",
            },
        },
        "yaml": {
            "yamllint": {
                "ext": [".yaml", ".yml"],
                "check": ["npx", "yamllint", "{{file}}"],
                "fix": None,
                "parse": r"(.+?):(\d+):(\d+):\s*\[?(\w+)\]?\s*(.+)",
            },
        },
        "markdown": {
            "markdownlint": {
                "ext": [".md"],
                "check": ["npx", "markdownlint", "{{file}}"],
                "fix": None,
                "parse": r"(.+?):(\d+)\s*(\w+)\s*(.+)",
            },
        },
        "shell": {
            "shellcheck": {
                "ext": [".sh", ".bash"],
                "check": ["shellcheck", "{{file}}"],
                "fix": None,
                "parse": r"(.+?):(\d+):(\d+):\s*(\w+):\s*(.+)",
            },
            "shfmt": {
                "ext": [".sh", ".bash"],
                "check": ["shfmt", "-d", "{{file}}"],
                "fix": ["shfmt", "-w", "{{file}}"],
                "parse": r"(.+)",
            },
        },
    }

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT

    def detect_language(self, file_path: Path) -> Optional[str]:
        ext = file_path.suffix.lower()
        for lang, linters in self.LINTERS.items():
            for linter_name, config in linters.items():
                if ext in config["ext"]:
                    return lang
        return None

    def get_available_linters(self) -> List[Tuple[str, str]]:
        available = []
        for lang, linters in self.LINTERS.items():
            for linter_name, config in linters.items():
                if config["fix"]:
                    try:
                        result = subprocess.run(
                            [config["fix"][0]],
                            capture_output=True,
                            timeout=5,
                        )
                        available.append((lang, linter_name))
                    except FileNotFoundError:
                        continue
                    except Exception:
                        available.append((lang, linter_name))
        return available

    def lint_file(self, file_path: str, linter: Optional[str] = None) -> LintResult:
        path = Path(file_path).resolve()
        if not path.exists():
            return LintResult(False, [], f"File not found: {file_path}", "")

        language = self.detect_language(path)
        if language is None:
            return LintResult(True, [], "Unknown file type", "")

        linters = self.LINTERS.get(language, {})
        if linter:
            linters = {linter: linters.get(linter)}
            linters = {k: v for k, v in linters.items() if v}

        if not linters:
            return LintResult(True, [], f"No linters for {language}", "")

        all_issues = []
        output_parts = []
        passed = True

        for linter_name, config in linters.items():
            cmd = [c.replace("{{file}}", str(path)) for c in config["check"]]
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                output = (result.stdout + result.stderr).strip()
                output_parts.append(f"[{linter_name}]\n{output}")

                issues = self._parse_issues(output, config["parse"], path.name)
                all_issues.extend(issues)
                if issues:
                    passed = False

            except subprocess.TimeoutExpired:
                output_parts.append(f"[{linter_name}] Timeout")
            except FileNotFoundError:
                output_parts.append(f"[{linter_name}] Not found")
            except Exception as e:
                output_parts.append(f"[{linter_name}] {e}")

        return LintResult(
            passed=passed,
            issues=all_issues,
            output="\n".join(output_parts),
            command=f"{linter_name}: {' '.join(cmd)}" if linters else "",
        )

    def fix_file(self, file_path: str, linter: Optional[str] = None) -> Tuple[bool, str]:
        path = Path(file_path).resolve()
        if not path.exists():
            return False, f"File not found: {file_path}"

        language = self.detect_language(path)
        if language is None:
            return False, "Unknown file type"

        linters = self.LINTERS.get(language, {})
        if linter:
            linters = {linter: linters.get(linter)}
            linters = {k: v for k, v in linters.items() if v and v.get("fix")}

        if not linters:
            return False, f"No fixable linters for {language}"

        fixed_any = False
        outputs = []

        for linter_name, config in linters.items():
            if not config["fix"]:
                continue

            cmd = [c.replace("{{file}}", str(path)) for c in config["fix"]]
            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                output = (result.stdout + result.stderr).strip()
                outputs.append(f"[{linter_name}]\n{output}")

                if result.returncode == 0:
                    fixed_any = True

            except subprocess.TimeoutExpired:
                outputs.append(f"[{linter_name}] Timeout")
            except FileNotFoundError:
                return False, f"{linter_name} not installed"
            except Exception as e:
                outputs.append(f"[{linter_name}] {e}")

        return fixed_any, "\n".join(outputs)

    def format_issues(self, result: LintResult) -> str:
        if result.passed:
            return "✅ No lint issues found."

        lines = [f"❌ Lint failed: {len(result.issues)} issue(s)"]

        if result.fixed:
            lines.append("   (Some issues were auto-fixed)")

        current_file = None
        for issue in result.issues:
            if issue.file != current_file:
                current_file = issue.file
                lines.append(f"\n📁 {issue.file}")

            col_ref = f":{issue.column}" if issue.column else ""
            fixable = " 🔧" if issue.fixable else ""
            lines.append(f"   {issue.line}{col_ref}: {issue.severity} {issue.rule}{fixable} {issue.message}")

        return "\n".join(lines)

    def _parse_issues(self, output: str, pattern: str, filename: str) -> List[LintIssue]:
        issues = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            match = re.match(pattern, line.strip())
            if match:
                groups = match.groups()
                try:
                    if len(groups) >= 5:
                        file, line_no, col, rule, msg = groups[0], groups[1], groups[2], groups[3], groups[4]
                        issues.append(LintIssue(
                            file=file or filename,
                            line=int(line_no) if line_no else 0,
                            column=int(col) if col else None,
                            rule=rule or "unknown",
                            message=msg or "",
                            severity="warning",
                            fixable=True,
                        ))
                    elif len(groups) >= 2:
                        file, msg = groups[0], groups[1]
                        issues.append(LintIssue(
                            file=file or filename,
                            line=0,
                            column=None,
                            rule="format",
                            message=msg or "",
                            severity="info",
                            fixable=True,
                        ))
                except (ValueError, IndexError):
                    continue
        return issues

    def lint_project(self, language: Optional[str] = None) -> List[LintResult]:
        results = []

        languages_to_check = {language: self.LINTERS[language]} if language and language in self.LINTERS else self.LINTERS

        for lang, linters in languages_to_check.items():
            for linter_name, config in linters.items():
                if not config.get("fix"):
                    continue

                files = []
                for ext in config["ext"]:
                    files.extend(self.workspace_root.rglob(f"*{ext}"))

                if not files:
                    continue

                all_issues = []
                output_parts = []
                passed = True
                fixed_any = False

                for file_path in files[:20]:
                    cmd = [c.replace("{{file}}", str(file_path)) for c in config["fix"]]
                    try:
                        result = subprocess.run(
                            cmd,
                            cwd=self.workspace_root,
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )

                        check_cmd = [c.replace("{{file}}", str(file_path)) for c in config["check"]]
                        check_result = subprocess.run(
                            check_cmd,
                            cwd=self.workspace_root,
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )

                        if check_result.stdout.strip():
                            issues = self._parse_issues(check_result.stdout, config["parse"], str(file_path))
                            all_issues.extend(issues)
                            if issues:
                                passed = False

                        if result.returncode == 0:
                            fixed_any = True

                    except Exception as e:
                        output_parts.append(f"{file_path}: {e}")

                results.append(LintResult(
                    passed=passed,
                    issues=all_issues,
                    output="\n".join(output_parts) if output_parts else f"{lang}/{linter_name}: Project checked",
                    command=f"{linter_name}: {' '.join(config['fix'])}",
                    fixed=fixed_any,
                ))

        return results

    def format_fix_result(self, fixed: bool, output: str) -> str:
        if fixed:
            return f"✅ Auto-fix applied:\n{output}"
        return f"⚠️ Could not auto-fix:\n{output}"


def lint_file(file_path: Optional[str] = None, linter: Optional[str] = None) -> str:
    fixer = LintFixer()
    if file_path:
        result = fixer.lint_file(file_path, linter)
        return fixer.format_issues(result)
    results = fixer.lint_project()
    if not results:
        return "No linters configured or no source files found."
    outputs = []
    for r in results:
        outputs.append(fixer.format_issues(r))
    return "\n".join(outputs)


def fix_file(file_path: str, linter: Optional[str] = None) -> str:
    fixer = LintFixer()
    fixed, output = fixer.fix_file(file_path, linter)
    return fixer.format_fix_result(fixed, output)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if "--fix" in sys.argv:
            print(fix_file(sys.argv[1]))
        else:
            print(lint_file(sys.argv[1]))
    else:
        print(lint_file())
