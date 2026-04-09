from langchain_core.tools import tool
from pathlib import Path
from config import WORKSPACE_ROOT


@tool
def type_check_file(file_path: str, language: str = None) -> str:
    """Run type checker on a file or the entire project.
    Use to verify code correctness and catch type errors before runtime.
    Supports: python (mypy), typescript (tsc), rust (cargo check), go (go vet), java (javac).
    """
    from type_checker import TypeChecker
    checker = TypeChecker(WORKSPACE_ROOT)
    result = checker.check_file(file_path, language)
    return checker.format_errors(result)


@tool
def type_check_project(language: str = None) -> str:
    """Run type checker on the entire project.
    Use to find type errors across all files.
    Supports: python (mypy), typescript (tsc), rust (cargo check), go (go vet), java (javac).
    """
    from type_checker import TypeChecker
    checker = TypeChecker(WORKSPACE_ROOT)
    results = checker.check_project(language)
    if not results:
        return "No type checkers configured or no source files found."
    outputs = []
    for r in results:
        outputs.append(checker.format_errors(r))
    return "\n".join(outputs)


@tool
def lint_file(file_path: str, linter: str = None) -> str:
    """Run linter on a file or the entire project.
    Use to find code style issues and potential bugs.
    Supports: python (ruff, flake8, pylint), javascript (eslint), typescript (eslint), rust (clippy), go (gofmt), css (stylelint).
    """
    from lint_fixer import LintFixer
    fixer = LintFixer(WORKSPACE_ROOT)
    result = fixer.lint_file(file_path, linter)
    return fixer.format_issues(result)


@tool
def lint_and_fix_file(file_path: str, linter: str = None) -> str:
    """Run linter and auto-fix issues on a file.
    Use to automatically fix code style issues.
    Supports: python (ruff), javascript/typescript (eslint), rust (rustfmt), go (gofmt), css (stylelint).
    """
    from lint_fixer import LintFixer
    fixer = LintFixer(WORKSPACE_ROOT)
    result = fixer.lint_file(file_path, linter)
    if result.passed:
        return "No lint issues found."

    fixed, output = fixer.fix_file(file_path, linter)
    return fixer.format_fix_result(fixed, output)


@tool
def security_scan_file(file_path: str) -> str:
    """Scan a file for security vulnerabilities.
    Use to find hardcoded credentials, SQL injection, XSS, command injection, and other security issues.
    """
    from security_scanner import SecurityScanner
    scanner = SecurityScanner(WORKSPACE_ROOT)
    issues = scanner.scan_file(file_path)
    if not issues:
        return f"✅ No security issues found in {file_path}"

    result = scanner.format_issues(
        type('ScanResult', (), {
            'passed': False,
            'issues': issues,
            'files_scanned': 1,
            'scan_time': 0
        })()
    )
    return result


@tool
def security_scan_project() -> str:
    """Scan the entire project for security vulnerabilities.
    Use to find hardcoded credentials, SQL injection, XSS, command injection, and other security issues across all files.
    """
    from security_scanner import SecurityScanner
    scanner = SecurityScanner(WORKSPACE_ROOT)
    result = scanner.scan_project()
    return scanner.format_issues(result)


@tool
def code_review_file(file_path: str) -> str:
    """Review a file for code quality issues, best practices, and potential bugs.
    Use to get feedback on code quality, error handling, performance, and maintainability.
    """
    from code_review import CodeReviewer
    reviewer = CodeReviewer(WORKSPACE_ROOT)
    result = reviewer.review_file(file_path)
    return reviewer.format_result(result)


@tool
def code_review_project() -> str:
    """Review the entire project for code quality issues.
    Use to get an overview of code quality across all files, including error handling, performance, and best practices.
    """
    from code_review import CodeReviewer
    reviewer = CodeReviewer(WORKSPACE_ROOT)
    summary = reviewer.review_project()
    return reviewer.format_summary(summary)


@tool
def run_all_checks(file_path: str = None) -> str:
    """Run all code quality checks: type checking, linting, security scan, and code review.
    Use for comprehensive code quality analysis on a file or the entire project.
    """
    from type_checker import TypeChecker
    from lint_fixer import LintFixer
    from security_scanner import SecurityScanner
    from code_review import CodeReviewer

    results = []

    results.append("=" * 50)
    results.append("TYPE CHECKING")
    results.append("=" * 50)
    checker = TypeChecker(WORKSPACE_ROOT)
    if file_path:
        r = checker.check_file(file_path)
        results.append(checker.format_errors(r))
    else:
        rs = checker.check_project()
        for r in rs:
            results.append(checker.format_errors(r))

    results.append("")
    results.append("=" * 50)
    results.append("LINTING")
    results.append("=" * 50)
    fixer = LintFixer(WORKSPACE_ROOT)
    if file_path:
        r = fixer.lint_file(file_path)
        results.append(fixer.format_issues(r))
    else:
        rs = fixer.lint_project()
        for r in rs:
            results.append(fixer.format_issues(r))

    results.append("")
    results.append("=" * 50)
    results.append("SECURITY SCAN")
    results.append("=" * 50)
    scanner = SecurityScanner(WORKSPACE_ROOT)
    if file_path:
        issues = scanner.scan_file(file_path)
        r = type('ScanResult', (), {
            'passed': len(issues) == 0,
            'issues': issues,
            'files_scanned': 1,
            'scan_time': 0
        })()
        results.append(scanner.format_issues(r))
    else:
        r = scanner.scan_project()
        results.append(scanner.format_issues(r))

    results.append("")
    results.append("=" * 50)
    results.append("CODE REVIEW")
    results.append("=" * 50)
    reviewer = CodeReviewer(WORKSPACE_ROOT)
    if file_path:
        r = reviewer.review_file(file_path)
        results.append(reviewer.format_result(r))
    else:
        s = reviewer.review_project()
        results.append(reviewer.format_summary(s))

    return "\n".join(results)
