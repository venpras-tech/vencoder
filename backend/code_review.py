import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from config import WORKSPACE_ROOT


@dataclass
class CodeReviewIssue:
    file: str
    line: int
    category: str
    severity: str
    title: str
    description: str
    suggestion: str
    code: Optional[str] = None


@dataclass
class CodeReviewResult:
    file: str
    issues: List[CodeReviewIssue]
    score: int
    summary: str


class CodeReviewer:
    BEST_PRACTICES = {
        "error_handling": {
            "patterns": [
                (r"except:\s*$", "Bare except clause - catch specific exceptions"),
                (r"except\s*:\s*pass", "Empty except clause - handle the exception properly"),
                (r"print\s*\(", "Consider using logging instead of print"),
                (r"raise\s+Exception\s*\(\"", "Consider using more specific exception types"),
                (r"catch\s*\(\s*Exception", "Empty or bare exception catch"),
                (r"console\.error\s*\(\s*\)", "Empty console.error call"),
            ],
            "category": "Error Handling",
            "severity": "medium",
        },
        "code_quality": {
            "patterns": [
                (r"def\s+\w+\s*\([^)]*\):\s*\n\s{0,4}#", "Comments before function - consider docstring"),
                (r"\bfunction\s+\w+\s*\([^)]*\)\s*{\s*/\*\s*$", "Block comment before function - use JSDoc"),
                (r"if\s+True\s*:", "Condition always true"),
                (r"if\s+False\s*:", "Condition always false"),
                (r"while\s+True\s*:\s*\n\s{0,4}break", "Consider refactoring infinite loop with break"),
                (r"pass\s*$", "Empty function/body - add implementation or raise NotImplementedError"),
                (r"// TODO", "TODO comment found - should be addressed"),
                (r"# TODO", "TODO comment found - should be addressed"),
                (r"HACK", "HACK comment found - should be addressed"),
                (r"FIXME", "FIXME comment found - should be addressed"),
                (r"XXX", "XXX comment found - should be addressed"),
            ],
            "category": "Code Quality",
            "severity": "low",
        },
        "performance": {
            "patterns": [
                (r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(", "Use enumerate() instead of range(len())"),
                (r"\.append\s*\(\s*\w+\s*\)\s*\n\s*for\s", "Consider list comprehension"),
                (r"\[\s*\w+\s+for\s+\w+\s+in\s+\w+\s+for\s+\w+\s+in\s+", "Nested list comprehension - consider separate loop"),
                (r"@app\.route.*\ndef\s+\w+\s*\(self\)", "Consider class-based views for Flask routes"),
                (r"\.query\.all\(\).*for\s", "Loading all records - consider pagination"),
            ],
            "category": "Performance",
            "severity": "medium",
        },
        "security": {
            "patterns": [
                (r"os\.system\s*\(", "os.system() is potentially unsafe"),
                (r"eval\s*\(", "eval() is dangerous"),
                (r"exec\s*\(", "exec() is dangerous"),
                (r"password\s*=\s*[\"'][^\"']+[\"']", "Hardcoded password detected"),
                (r"api[_-]?key\s*=\s*[\"'][^\"']+[\"']", "Hardcoded API key detected"),
                (r"\.format\s*\([^)]*request\.", "String format with user input - consider f-string or parameterized"),
                (r"innerHTML\s*=", "innerHTML assignment - XSS risk"),
                (r"admin\s*==\s*True", "Simple admin check - consider role-based access"),
            ],
            "category": "Security",
            "severity": "high",
        },
        "maintainability": {
            "patterns": [
                (r"from\s+\w+\s+import\s+\*", "Wildcard import - import specific names"),
                (r"import\s+\w+\s*\n\s*import\s+\w+", "Multiple imports - consider combining"),
                (r"\bglobals\(\)", "globals() usage - consider refactoring"),
                (r"\blocals\(\)", "locals() usage - consider refactoring"),
                (r"\breload\s*\(", "reload() is deprecated"),
                (r"__init__\.py.*\n.*__all__", "Consider defining __all__ explicitly"),
            ],
            "category": "Maintainability",
            "severity": "low",
        },
        "testing": {
            "patterns": [
                (r"class\s+\w+.*:\s*\n\s{0,4}(?!.*test)", "Class without test file detected"),
                (r"@pytest\.fixture\s*\n\s{0,4}def\s+\w+\s*\([^)]*\):\s*\n\s{0,4}pass", "Empty fixture"),
                (r"self\.assert\w+\s*\([^,]+,\s*None\s*\)", "Assertion with None - use assertIsNone"),
                (r"self\.assert\w+\s*\(\s*True\s*,", "Assert True/False - use assertTrue/assertFalse"),
                (r"#.*test.*\n(?!.*def test_)", "Comment mentioning test but no test function"),
            ],
            "category": "Testing",
            "severity": "medium",
        },
        "documentation": {
            "patterns": [
                (r"def\s+\w+\s*\([^)]*\)\s*->\s*\w+\s*:\s*\n(?!.*\"\"\")", "Function with return type but no docstring"),
                (r"class\s+\w+\s*\([^)]*\):\s*\n(?!.*\"\"\")", "Class without docstring"),
                (r"def\s+\w+\s*\([^)]*\):\s*\n\s{0,4}\"\"\"\s*\n\s*\"\"\"\s*$", "Empty docstring"),
                (r"def\s+\w+\s*\([^)]*\)\s*:\s*$", "Function without docstring"),
            ],
            "category": "Documentation",
            "severity": "low",
        },
        "design": {
            "patterns": [
                (r"class\s+\w+\s*\(\s*\):", "Empty class definition"),
                (r"super\(\).__init__\(\)\s*\n\s{0,8}pass", "super().__init__() with pass"),
                (r"if\s+.*\s+else\s+.*if\s+", "Chained if-else - consider match/case or dictionary dispatch"),
                (r"return\s+True\s+if\s+.*\s+else\s+False", "Redundant boolean - return the condition directly"),
                (r"if\s+\w+\s+==\s+True\s*:", "Redundant comparison - use 'if condition:'"),
                (r"if\s+len\s*\(\s*\w+\s*\)\s*>\s*0\s*:", "Use 'if items:' instead of 'if len(items) > 0:'"),
            ],
            "category": "Design Patterns",
            "severity": "low",
        },
    }

    COMPLEXITY_PATTERNS = {
        "high_complexity": {
            "patterns": [
                (r"if.*elif.*elif.*elif.*:", "Too many elif branches - consider dictionary dispatch or polymorphism"),
                (r"for\s+.*in\s+.*:\s*\n\s*for\s+.*in\s+.*:\s*\n\s*for\s+", "Deeply nested loops - consider refactoring"),
            ],
            "category": "Complexity",
            "severity": "medium",
        }
    }

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT

    def review_file(self, file_path: str) -> CodeReviewResult:
        path = Path(file_path)
        if not path.exists():
            return CodeReviewResult(
                file=str(path),
                issues=[],
                score=100,
                summary="File not found"
            )

        issues = []

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
        except Exception as e:
            return CodeReviewResult(
                file=str(path),
                issues=[],
                score=0,
                summary=f"Error reading file: {e}"
            )

        for category, config in {**self.BEST_PRACTICES, **self.COMPLEXITY_PATTERNS}.items():
            for pattern, message in config["patterns"]:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    line_num = content[:match.start()].count('\n') + 1

                    line_start = content.rfind('\n', 0, match.start()) + 1
                    line_end = content.find('\n', match.start())
                    if line_end == -1:
                        line_end = len(content)
                    code_line = content[line_start:line_end].strip()

                    issue = CodeReviewIssue(
                        file=str(path.relative_to(self.workspace_root)),
                        line=line_num,
                        category=config["category"],
                        severity=config["severity"],
                        title=message,
                        description=f"Found in {path.name} at line {line_num}",
                        suggestion=self._get_suggestion(category, message, code_line),
                        code=code_line,
                    )
                    issues.append(issue)

        score = self._calculate_score(issues)

        return CodeReviewResult(
            file=str(path.relative_to(self.workspace_root)),
            issues=issues,
            score=score,
            summary=self._generate_summary(issues, score),
        )

    def review_files(self, file_paths: List[str]) -> List[CodeReviewResult]:
        results = []
        for file_path in file_paths:
            result = self.review_file(file_path)
            results.append(result)
        return results

    def review_project(self, extensions: Optional[List[str]] = None) -> Dict:
        extensions = extensions or [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php"]

        results = []
        files_checked = 0

        for ext in extensions:
            for file_path in self.workspace_root.rglob(f"*{ext}"):
                if any(skip in str(file_path) for skip in ["node_modules", ".venv", "__pycache__", ".git", "vendor"]):
                    continue
                result = self.review_file(str(file_path))
                results.append(result)
                files_checked += 1

        all_issues = []
        for result in results:
            all_issues.extend(result.issues)

        total_score = sum(r.score for r in results) / len(results) if results else 100

        return {
            "files_reviewed": files_checked,
            "total_issues": len(all_issues),
            "average_score": round(total_score, 1),
            "results": results,
            "issues_by_severity": self._group_by_severity(all_issues),
            "issues_by_category": self._group_by_category(all_issues),
        }

    def _calculate_score(self, issues: List[CodeReviewIssue]) -> int:
        if not issues:
            return 100

        deductions = {
            "critical": 20,
            "high": 10,
            "medium": 5,
            "low": 2,
        }

        total_deduction = 0
        seen_categories = set()

        for issue in issues:
            if issue.category not in seen_categories:
                seen_categories.add(issue.category)
                total_deduction += deductions.get(issue.severity, 5)

        return max(0, 100 - total_deduction)

    def _generate_summary(self, issues: List[CodeReviewIssue], score: int) -> str:
        if not issues:
            return "Code looks good! No issues detected."

        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for issue in issues:
            if issue.severity in by_severity:
                by_severity[issue.severity].append(issue)

        lines = []
        if by_severity["critical"]:
            lines.append(f"🔴 Critical: {len(by_severity['critical'])} issue(s) need immediate attention")
        if by_severity["high"]:
            lines.append(f"🟠 High: {len(by_severity['high'])} issue(s) should be addressed")
        if by_severity["medium"]:
            lines.append(f"🟡 Medium: {len(by_severity['medium'])} issue(s) recommended to fix")
        if by_severity["low"]:
            lines.append(f"🟢 Low: {len(by_severity['low'])} issue(s) are suggestions")

        return " | ".join(lines) if lines else "Code review complete"

    def _get_suggestion(self, category: str, message: str, code: str) -> str:
        suggestions = {
            "Bare except clause": "Use 'except SpecificException as e:' instead",
            "Empty except clause": "Handle the exception or log it",
            "Consider using logging": "Replace print() with proper logging: logging.getLogger(__name__).info()",
            "Hardcoded password": "Use environment variables: os.environ.get('PASSWORD')",
            "Use enumerate()": "Replace 'for i in range(len(items))' with 'for i, item in enumerate(items)'",
            "Wildcard import": "Use 'from module import specific_name'",
            "os.system()": "Use subprocess.run() or subprocess.Popen()",
            "eval()": "Avoid eval() - use ast.literal_eval() for safe parsing",
            "innerHTML": "Use textContent or sanitize input before setting innerHTML",
            "Consider list comprehension": "Use [x for x in items] instead of append in loop",
        }

        for key, value in suggestions.items():
            if key.lower() in message.lower():
                return value

        return "Review and refactor if needed"

    def _group_by_severity(self, issues: List[CodeReviewIssue]) -> Dict:
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for issue in issues:
            if issue.severity in by_severity:
                by_severity[issue.severity].append(issue)
        return by_severity

    def _group_by_category(self, issues: List[CodeReviewIssue]) -> Dict:
        by_category = {}
        for issue in issues:
            if issue.category not in by_category:
                by_category[issue.category] = []
            by_category[issue.category].append(issue)
        return by_category

    def format_result(self, result: CodeReviewResult) -> str:
        lines = [
            f"## Code Review: {result.file}",
            f"",
            f"**Score: {result.score}/100**",
            f"",
            result.summary,
            f"",
        ]

        if result.issues:
            lines.append("### Issues Found")
            lines.append("")

            by_category = {}
            for issue in result.issues:
                if issue.category not in by_category:
                    by_category[issue.category] = []
                by_category[issue.category].append(issue)

            for category, issues in by_category.items():
                lines.append(f"#### {category} ({len(issues)} issue(s))")
                for issue in issues:
                    severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue.severity, "⚪")
                    lines.append(f"{severity_icon} **{issue.title}** (Line {issue.line})")
                    if issue.code:
                        lines.append(f"   ```")
                        lines.append(f"   {issue.code[:80]}")
                        lines.append(f"   ```")
                    lines.append(f"   💡 {issue.suggestion}")
                    lines.append("")
        else:
            lines.append("✅ No issues found!")

        return "\n".join(lines)

    def format_summary(self, summary: Dict) -> str:
        lines = [
            "# Code Review Summary",
            "",
            f"**Files Reviewed:** {summary['files_reviewed']}",
            f"**Total Issues:** {summary['total_issues']}",
            f"**Average Score:** {summary['average_score']}/100",
            "",
        ]

        if summary['issues_by_severity']:
            lines.append("### Issues by Severity")
            for severity, issues in summary['issues_by_severity'].items():
                if issues:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
                    lines.append(f"{icon} {severity.capitalize()}: {len(issues)}")
            lines.append("")

        if summary['issues_by_category']:
            lines.append("### Issues by Category")
            for category, issues in summary['issues_by_category'].items():
                lines.append(f"- **{category}**: {len(issues)} issue(s)")
            lines.append("")

        lines.append("### Files with Issues")
        for result in sorted(summary['results'], key=lambda x: x.score):
            if result.issues:
                icon = "✅" if result.score >= 80 else "⚠️" if result.score >= 60 else "❌"
                lines.append(f"{icon} {result.file}: {result.score}/100 ({len(result.issues)} issues)")

        return "\n".join(lines)


def review_file(file_path: str) -> str:
    reviewer = CodeReviewer()
    result = reviewer.review_file(file_path)
    return reviewer.format_result(result)


def review_project() -> str:
    reviewer = CodeReviewer()
    summary = reviewer.review_project()
    return reviewer.format_summary(summary)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(review_file(sys.argv[1]))
    else:
        print(review_project())
