import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from config import WORKSPACE_ROOT


@dataclass
class TypeError:
    file: str
    line: int
    column: Optional[int]
    message: str
    severity: str
    code: Optional[str] = None


@dataclass
class CheckResult:
    passed: bool
    errors: List[TypeError]
    output: str
    command: str


class TypeChecker:
    LANGUAGES = {
        "python": {
            "ext": [".py"],
            "checker": "mypy",
            "command": ["mypy", "{{file}}", "--no-error-summary", "--output-format=text"],
            "project_command": ["mypy", "."],
            "parse_pattern": r"(.+?):(\d+):(?:(\d+):)?\s*(error|warning):\s*(.+)",
        },
        "typescript": {
            "ext": [".ts", ".tsx"],
            "checker": "tsc",
            "command": ["npx", "tsc", "--noEmit", "{{file}}"],
            "project_command": ["npx", "tsc", "--noEmit"],
            "parse_pattern": r"(.+?)\((\d+)(?:,(\d+))?\):\s*(error|warning)\s*(TS\d+)?:\s*(.+)",
        },
        "javascript": {
            "ext": [".js", ".jsx", ".mjs"],
            "checker": "eslint",
            "command": ["npx", "eslint", "{{file}}"],
            "project_command": ["npx", "eslint", "."],
            "parse_pattern": r"(.+?):\s*line\s*(\d+)(?:\s*col\s*(\d+))?\s*(?:✖|\|)\s*(?:(\d+):)?\s*(error|warning)\s*(.+)",
        },
        "rust": {
            "ext": [".rs"],
            "checker": "cargo check",
            "command": ["cargo", "check", "--message-format=json", "{{file}}"],
            "project_command": ["cargo", "check", "--message-format=json"],
            "parse_pattern": r"(.+?)\((\d+)\s*\d+\):\s*(error|warning):\s*(.+)",
        },
        "go": {
            "ext": [".go"],
            "checker": "go vet",
            "command": ["go", "vet", "{{file}}"],
            "project_command": ["go", "vet", "./..."],
            "parse_pattern": r"(.+?):(\d+):\s*(.+)",
        },
        "java": {
            "ext": [".java"],
            "checker": "javac",
            "command": ["javac", "{{file}}"],
            "project_command": ["javac", "**/*.java"],
            "parse_pattern": r"(.+?):(\d+):\s*(error|warning):\s*(.+)",
        },
        "kotlin": {
            "ext": [".kt", ".kts"],
            "checker": "ktlint",
            "command": ["npx", "ktlint", "{{file}}"],
            "project_command": ["npx", "ktlint", "."],
            "parse_pattern": r"(.+?):(\d+):\s*(error|warning):\s*(.+)",
        },
        "scala": {
            "ext": [".scala"],
            "checker": "scalac",
            "command": ["scalac", "{{file}}"],
            "project_command": ["scalac", "**/*.scala"],
            "parse_pattern": r"(.+?):(\d+):\s*(error|warning):\s*(.+)",
        },
        "c": {
            "ext": [".c", ".h"],
            "checker": "gcc",
            "command": ["gcc", "-fsyntax-only", "-Wall", "{{file}}"],
            "project_command": ["gcc", "-fsyntax-only", "-Wall", "*.c"],
            "parse_pattern": r"(.+?):(\d+):\d+:\s*(error|warning):\s*(.+)",
        },
        "cpp": {
            "ext": [".cpp", ".cc", ".hpp", ".h"],
            "checker": "g++",
            "command": ["g++", "-fsyntax-only", "-Wall", "{{file}}"],
            "project_command": ["g++", "-fsyntax-only", "-Wall", "*.cpp"],
            "parse_pattern": r"(.+?):(\d+):\d+:\s*(error|warning):\s*(.+)",
        },
        "csharp": {
            "ext": [".cs"],
            "checker": "dotnet",
            "command": ["dotnet", "build", "--no-restore", "{{file}}"],
            "project_command": ["dotnet", "build", "--no-restore"],
            "parse_pattern": r"(.+?)\((\d+)(?:,(\d+))?:\s*(error|warning)\s*(CS\d+)?:\s*(.+)",
        },
    }

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT

    def detect_language(self, file_path: Path) -> Optional[str]:
        ext = file_path.suffix.lower()
        for lang, config in self.LANGUAGES.items():
            if ext in config["ext"]:
                return lang
        return None

    def get_language_config(self, language: str) -> Optional[Dict]:
        return self.LANGUAGES.get(language)

    def check_file(self, file_path: str, language: Optional[str] = None) -> CheckResult:
        path = Path(file_path).resolve()
        if not path.exists():
            return CheckResult(False, [], f"File not found: {file_path}", "")

        if language is None:
            language = self.detect_language(path)
        if language is None:
            return CheckResult(True, [], "Unknown file type", "")

        config = self.get_language_config(language)
        if config is None:
            return CheckResult(True, [], f"No checker for {language}", "")

        cmd = [c.replace("{{file}}", str(path)) for c in config["command"]]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = (result.stdout + result.stderr).strip()
            errors = self._parse_errors(output, config["parse_pattern"], language)

            return CheckResult(
                passed=len(errors) == 0,
                errors=errors,
                output=output,
                command=" ".join(cmd),
            )
        except subprocess.TimeoutExpired:
            return CheckResult(False, [], "Type check timed out", " ".join(cmd))
        except FileNotFoundError as e:
            return CheckResult(
                False, [], f"Checker not found: {config['checker']}. Install: {e}", ""
            )
        except Exception as e:
            return CheckResult(False, [], str(e), " ".join(cmd))

    def check_project(self, language: Optional[str] = None) -> List[CheckResult]:
        results = []

        if language:
            config = self.get_language_config(language)
            if config:
                cmd = config["project_command"]
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=self.workspace_root,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    output = (result.stdout + result.stderr).strip()
                    errors = self._parse_errors(output, config["parse_pattern"], language)

                    results.append(CheckResult(
                        passed=len(errors) == 0,
                        errors=errors,
                        output=output,
                        command=" ".join(cmd),
                    ))
                except Exception as e:
                    results.append(CheckResult(False, [], str(e), " ".join(cmd)))
            return results

        for lang, config in self.LANGUAGES.items():
            files = []
            for ext in config["ext"]:
                files.extend(self.workspace_root.rglob(f"*{ext}"))

            if not files:
                continue

            if len(files) == 1:
                result = self.check_file(str(files[0]), lang)
                results.append(result)
            else:
                cmd = config["project_command"]
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=self.workspace_root,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    output = (result.stdout + result.stderr).strip()
                    errors = self._parse_errors(output, config["parse_pattern"], lang)

                    results.append(CheckResult(
                        passed=len(errors) == 0,
                        errors=errors,
                        output=output,
                        command=" ".join(cmd),
                    ))
                except Exception as e:
                    results.append(CheckResult(False, [], str(e), " ".join(cmd)))

        return results

    def _parse_errors(self, output: str, pattern: str, language: str) -> List[TypeError]:
        errors = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            match = re.match(pattern, line.strip())
            if match:
                groups = match.groups()
                try:
                    if language == "typescript" and len(groups) >= 6:
                        file, line_no, col, severity, code, msg = groups
                        errors.append(TypeError(
                            file=file or "",
                            line=int(line_no) if line_no else 0,
                            column=int(col) if col else None,
                            message=msg or "",
                            severity=severity or "error",
                            code=code or None,
                        ))
                    elif language == "csharp" and len(groups) >= 6:
                        file, line_no, col, severity, code, msg = groups
                        errors.append(TypeError(
                            file=file or "",
                            line=int(line_no) if line_no else 0,
                            column=int(col) if col else None,
                            message=msg or "",
                            severity=severity or "error",
                            code=code or None,
                        ))
                    elif language == "go":
                        file, line_no, msg = groups
                        errors.append(TypeError(
                            file=file or "",
                            line=int(line_no) if line_no else 0,
                            column=None,
                            message=msg or "",
                            severity="error",
                        ))
                    else:
                        file, line_no = groups[0], groups[1]
                        col = groups[2] if len(groups) > 2 else None
                        severity = groups[3] if len(groups) > 3 else "error"
                        msg = groups[4] if len(groups) > 4 else line
                        errors.append(TypeError(
                            file=file or "",
                            line=int(line_no) if line_no else 0,
                            column=int(col) if col and col.isdigit() else None,
                            message=msg or "",
                            severity=severity or "error",
                        ))
                except (ValueError, IndexError):
                    continue

        return errors

    def format_errors(self, result: CheckResult) -> str:
        if result.passed:
            return "✅ No type errors found."

        lines = [f"❌ Type check failed: {len(result.errors)} error(s)"]

        current_file = None
        for err in result.errors:
            if err.file != current_file:
                current_file = err.file
                lines.append(f"\n📁 {err.file}")

            code_ref = f"[{err.code}]" if err.code else ""
            col_ref = f":{err.column}" if err.column else ""
            lines.append(f"   {err.line}{col_ref}: {err.severity.upper()} {code_ref} {err.message}")

        return "\n".join(lines)

    def get_available_checkers(self) -> List[str]:
        available = []
        for lang, config in self.LANGUAGES.items():
            try:
                result = subprocess.run(
                    [config["project_command"][0]],
                    capture_output=True,
                    timeout=5,
                )
                available.append(lang)
            except FileNotFoundError:
                continue
            except Exception:
                available.append(lang)
        return available

    def suggest_installation(self, language: str) -> str:
        suggestions = {
            "python": "pip install mypy && mypy --version",
            "typescript": "npm install -g typescript && tsc --version",
            "javascript": "npm install eslint && npx eslint --version",
            "rust": "rustup component add rustfmt && cargo --version",
            "go": "go install golang.org/x/tools/cmd/goimports@latest",
            "java": "Ensure javac is in PATH",
            "kotlin": "npm install -g ktlint && ktlint --version",
        }
        return suggestions.get(language, f"Install checker for {language}")


def type_check(file_path: Optional[str] = None, language: Optional[str] = None) -> str:
    checker = TypeChecker()
    if file_path:
        result = checker.check_file(file_path, language)
    else:
        results = checker.check_project(language)
        if not results:
            return "No type checkers configured or no source files found."
        outputs = []
        for r in results:
            outputs.append(checker.format_errors(r))
        return "\n".join(outputs)
    return checker.format_errors(result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(type_check(sys.argv[1]))
    else:
        print(type_check())
