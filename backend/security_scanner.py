import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from config import WORKSPACE_ROOT


@dataclass
class SecurityIssue:
    file: str
    line: int
    severity: str
    category: str
    rule: str
    message: str
    code: str
    cwe: Optional[str] = None
    owasp: Optional[str] = None


@dataclass
class ScanResult:
    passed: bool
    issues: List[SecurityIssue]
    files_scanned: int
    scan_time: float


class SecurityScanner:
    PATTERNS = {
        "hardcoded_credentials": {
            "severity": "critical",
            "category": "credentials",
            "patterns": [
                (r'password\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded password found"),
                (r'api[_-]?key\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded API key found"),
                (r'secret\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret found"),
                (r'token\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded token found"),
                (r'private[_-]?key\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded private key found"),
                (r'aws[_-]?access[_-]?key', "AWS access key pattern"),
                (r'ghp_[a-zA-Z0-9]{36}', "GitHub personal access token"),
                (r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth token"),
                (r'AKIA[0-9A-Z]{16}', "AWS access key ID"),
                (r'sk-[a-zA-Z0-9]{48}', "OpenAI API key"),
                (r'xox[baprs]-[a-zA-Z0-9]{10,}', "Slack token"),
            ],
            "extensions": [".py", ".js", ".ts", ".java", ".go", ".rb", ".php"],
        },
        "sql_injection": {
            "severity": "critical",
            "category": "injection",
            "patterns": [
                (r'execute\s*\(\s*f["\']', "Potential SQL injection with f-string"),
                (r'query\s*\(\s*f["\']', "Potential SQL injection with f-string"),
                (r'cursor\.execute\s*\([^)]*\%s', "SQL injection with % formatting"),
                (r'cursor\.execute\s*\([^)]*\.format\s*\(', "SQL injection with .format()"),
                (r'\$iquery\s*=', "Potential SQL injection"),
                (r'"\s*\+\s*.*\s*\+\s*"', "String concatenation in SQL query"),
                (r'`.*\$\{.*\}.*`', "Template literal with variable in SQL"),
            ],
            "extensions": [".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".cs"],
        },
        "command_injection": {
            "severity": "critical",
            "category": "injection",
            "patterns": [
                (r'os\.system\s*\(', "os.system() is vulnerable to command injection"),
                (r'subprocess\.\w+\s*\(\s*shell\s*=\s*True', "subprocess with shell=True is dangerous"),
                (r'eval\s*\(', "eval() is dangerous and should not be used"),
                (r'exec\s*\(', "exec() is dangerous and should not be used"),
                (r'child_process\.exec\s*\(', "child_process.exec() is vulnerable to injection"),
                (r'child_process\.execSync\s*\(', "child_process.execSync() is vulnerable to injection"),
                (r'Runtime\.getRuntime\(\)\.exec\s*\(', "Runtime.exec() is vulnerable to injection"),
            ],
            "extensions": [".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".sh"],
        },
        "xss": {
            "severity": "high",
            "category": "xss",
            "patterns": [
                (r'innerHTML\s*=', "innerHTML assignment is vulnerable to XSS"),
                (r'dangerouslySetInnerHTML', "dangerouslySetInnerHTML is vulnerable to XSS"),
                (r'\.html\s*\(\s*\$', "jQuery .html() with user input"),
                (r'response\.write\s*\([^)]*request\.', "Response writing user input directly"),
                (r'@\.raw\s*\(', "Template raw output without escaping"),
                (r'\| safe\b', "Django safe filter - verify content is safe"),
                (r'v-html=', "Vue v-html directive - XSS risk"),
            ],
            "extensions": [".py", ".js", ".ts", ".html", ".vue", ".jsx", ".tsx"],
        },
        "path_traversal": {
            "severity": "high",
            "category": "path_traversal",
            "patterns": [
                (r'open\s*\([^)]*\+\s*request\.', "Path traversal via request parameter"),
                (r'FileInputStream\s*\([^)]*\+', "Path traversal in Java"),
                (r'Path\.get\s*\([^)]*request\.', "Path traversal via request"),
                (r'\.\./', "Directory traversal pattern detected"),
                (r'%2e%2e%2f', "URL encoded directory traversal"),
                (r'\.\.\\', "Windows path traversal"),
            ],
            "extensions": [".py", ".js", ".ts", ".java", ".go", ".rb", ".php"],
        },
        "insecure_random": {
            "severity": "medium",
            "category": "cryptography",
            "patterns": [
                (r'random\.random\s*\(', "random.random() is not cryptographically secure"),
                (r'random\.randint\s*\(', "random.randint() is not cryptographically secure"),
                (r'random\.choice\s*\(', "random.choice() is not cryptographically secure"),
                (r'Math\.random\s*\(', "Math.random() is not cryptographically secure"),
                (r'new\s+Random\s*\(', "java.util.Random is not cryptographically secure"),
            ],
            "extensions": [".py", ".js", ".ts", ".java"],
        },
        "weak_crypto": {
            "severity": "high",
            "category": "cryptography",
            "patterns": [
                (r'md5', "MD5 is considered insecure for cryptographic purposes"),
                (r'sha1\b', "SHA-1 is considered insecure for cryptographic purposes"),
                (r'DES\b', "DES is insecure, use AES"),
                (r'RC4\b', "RC4 is insecure"),
                (r'crypto\.createCipher\b', "createCipher is deprecated, use createCipheriv"),
                (r'hashlib\.new\s*\(\s*["\']md5', "MD5 hash is insecure"),
                (r'hashlib\.new\s*\(\s*["\']sha1', "SHA-1 hash is insecure"),
                (r'mcf_crypt', "Mcrypt is deprecated and insecure"),
            ],
            "extensions": [".py", ".js", ".ts", ".java", ".go", ".rb", ".php"],
        },
        "unsafe_yaml": {
            "severity": "high",
            "category": "deserialization",
            "patterns": [
                (r'yaml\.load\s*\([^)]*\)\s*(?!\)', "yaml.load() without Loader is unsafe"),
                (r'yaml\.unsafe_load', "yaml.unsafe_load() can execute arbitrary code"),
                (r'pickle\.load\s*\(', "pickle.load() can execute arbitrary code"),
                (r'pickle\.loads\s*\([^)]*request\.', "pickle.load() with user input is dangerous"),
                (r'unserialize\s*\([^)]*request\.', "unserialize() with user input is dangerous"),
            ],
            "extensions": [".py", ".js", ".php"],
        },
        "敞开重定向": {
            "severity": "medium",
            "category": "open_redirect",
            "patterns": [
                (r'redirect\s*\(\s*request\.', "Open redirect via request parameter"),
                (r'response\.redirect\s*\([^)]*request\.', "Open redirect via request"),
                (r'window\.location\s*=\s*\$', "Open redirect via user input"),
                (r'Location\s*:\s*.*request\.', "Open redirect in header"),
            ],
            "extensions": [".py", ".js", ".ts", ".java", ".go", ".rb", ".php"],
        },
        "xxe": {
            "severity": "critical",
            "category": "xxe",
            "patterns": [
                (r'SAXBuilder\s*\(\s*\)', "SAXBuilder without security config is vulnerable to XXE"),
                (r'DocumentBuilderFactory\.newInstance\s*\(\s*\)', "DocumentBuilderFactory without XXE protection"),
                (r'XMLInputFactory\.newInstance\s*\(\s*\)', "XMLInputFactory without XXE protection"),
                (r'lxml\.etree\.parse', "lxml parse without security config"),
                (r'etree\.fromstring\s*\(', "fromstring can be vulnerable to XXE"),
            ],
            "extensions": [".py", ".java", ".js", ".ts"],
        },
        "ssrf": {
            "severity": "high",
            "category": "ssrf",
            "patterns": [
                (r'requests\.\w+\s*\(\s*request\.', "SSRF via request parameter"),
                (r'urllib\.\w+\s*\([^)]*request\.', "SSRF via request parameter"),
                (r'http.*request\.', "Potential SSRF"),
                (r'file://', "File scheme in HTTP request can lead to SSRF"),
                (r'gopher://', "Gopher protocol in HTTP request can lead to SSRF"),
            ],
            "extensions": [".py", ".js", ".ts", ".java", ".go", ".rb", ".php"],
        },
        "sensitive_data_exposure": {
            "severity": "high",
            "category": "data_exposure",
            "patterns": [
                (r'console\.log\s*\([^)]*password', "Sensitive data in console.log"),
                (r'print\s*\([^)]*password', "Sensitive data in print statement"),
                (r'\.write\s*\([^)]*password', "Sensitive data being written"),
                (r'logging\.\w+\s*\([^)]*password', "Sensitive data in logs"),
                (r'\.env\b', ".env file should not be committed"),
                (r'id_rsa', "Private key should not be committed"),
                (r'\.pem\b', "Certificate/key file should not be committed"),
            ],
            "extensions": [".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".env"],
        },
    }

    IGNORE_PATTERNS = [
        r'node_modules',
        r'\.git',
        r'vendor',
        r'\.venv',
        r'__pycache__',
        r'dist',
        r'build',
        r'\.min\.',
        r'test[s]?/',
        r'spec/',
    ]

    CWE_REFERENCES = {
        "hardcoded_credentials": "CWE-798",
        "sql_injection": "CWE-89",
        "command_injection": "CWE-78",
        "xss": "CWE-79",
        "path_traversal": "CWE-22",
        "insecure_random": "CWE-338",
        "weak_crypto": "CWE-327",
        "unsafe_yaml": "CWE-502",
        "open_redirect": "CWE-601",
        "xxe": "CWE-611",
        "ssrf": "CWE-918",
        "sensitive_data_exposure": "CWE-200",
    }

    OWASP_REFERENCES = {
        "hardcoded_credentials": "A07:2021",
        "sql_injection": "A03:2021",
        "command_injection": "A03:2021",
        "xss": "A03:2021",
        "path_traversal": "A01:2021",
        "insecure_random": "A02:2021",
        "weak_crypto": "A02:2021",
        "unsafe_yaml": "A08:2021",
        "open_redirect": "A01:2021",
        "xxe": "A03:2021",
        "ssrf": "A10:2021",
        "sensitive_data_exposure": "A01:2021",
    }

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT

    def scan_file(self, file_path: str) -> List[SecurityIssue]:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return []

        issues = []
        for ignore_pattern in self.IGNORE_PATTERNS:
            if re.search(ignore_pattern, str(path)):
                return []

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return []

        for issue_type, config in self.PATTERNS.items():
            if path.suffix not in config["extensions"]:
                continue

            for pattern, message in config["patterns"]:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    line_num = content[:match.start()].count('\n') + 1
                    line_start = content.rfind('\n', 0, match.start()) + 1
                    line_end = content.find('\n', match.start())
                    if line_end == -1:
                        line_end = len(content)
                    code_line = content[line_start:line_end].strip()

                    issues.append(SecurityIssue(
                        file=str(path.relative_to(self.workspace_root)),
                        line=line_num,
                        severity=config["severity"],
                        category=config["category"],
                        rule=issue_type,
                        message=message,
                        code=code_line[:100],
                        cwe=self.CWE_REFERENCES.get(issue_type),
                        owasp=self.OWASP_REFERENCES.get(issue_type),
                    ))

        return issues

    def scan_project(self, extensions: Optional[List[str]] = None) -> ScanResult:
        import time
        start_time = time.time()

        all_issues = []
        files_scanned = 0

        extensions = extensions or [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php"]

        for ext in extensions:
            for file_path in self.workspace_root.rglob(f"*{ext}"):
                for ignore_pattern in self.IGNORE_PATTERNS:
                    if re.search(ignore_pattern, str(file_path)):
                        break
                else:
                    issues = self.scan_file(str(file_path))
                    all_issues.extend(issues)
                    files_scanned += 1

        scan_time = time.time() - start_time

        return ScanResult(
            passed=len(all_issues) == 0,
            issues=all_issues,
            files_scanned=files_scanned,
            scan_time=round(scan_time, 2),
        )

    def format_issues(self, result: ScanResult) -> str:
        if result.passed:
            return f"✅ Security scan passed! No issues found in {result.files_scanned} files."

        lines = [
            f"🔴 Security scan completed: {len(result.issues)} issue(s) found",
            f"   Files scanned: {result.files_scanned}, Time: {result.scan_time}s\n",
        ]

        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for issue in result.issues:
            severity = issue.severity.lower()
            if severity in by_severity:
                by_severity[severity].append(issue)

        severity_order = ["critical", "high", "medium", "low"]
        severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

        for severity in severity_order:
            issues = by_severity.get(severity, [])
            if not issues:
                continue

            lines.append(f"{severity_icons.get(severity, '⚪')} **{severity.upper()}** ({len(issues)} issue(s))")

            by_category = {}
            for issue in issues:
                if issue.category not in by_category:
                    by_category[issue.category] = []
                by_category[issue.category].append(issue)

            for category, cat_issues in by_category.items():
                lines.append(f"  📁 {category}")
                for issue in cat_issues[:5]:
                    cwe = f" [{issue.cwe}]" if issue.cwe else ""
                    owasp = f" (OWASP {issue.owasp})" if issue.owasp else ""
                    lines.append(f"     {issue.file}:{issue.line} - {issue.message}{cwe}{owasp}")
                    lines.append(f"     Code: `{issue.code[:60]}...`" if len(issue.code) > 60 else f"     Code: `{issue.code}`")

                if len(cat_issues) > 5:
                    lines.append(f"     ... and {len(cat_issues) - 5} more")

            lines.append("")

        lines.append("-" * 50)
        lines.append("Recommendations:")
        lines.append("- Review and fix critical/high severity issues first")
        lines.append("- Use environment variables for secrets")
        lines.append("- Never commit .env files or credentials")
        lines.append("- Use parameterized queries for database operations")
        lines.append("- Validate and sanitize all user inputs")

        return "\n".join(lines)

    def get_summary(self, result: ScanResult) -> Dict:
        by_severity = {}
        by_category = {}

        for issue in result.issues:
            sev = issue.severity.lower()
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_category[issue.category] = by_category.get(issue.category, 0) + 1

        return {
            "total_issues": len(result.issues),
            "passed": result.passed,
            "files_scanned": result.files_scanned,
            "scan_time": result.scan_time,
            "by_severity": by_severity,
            "by_category": by_category,
        }


def security_scan(file_path: Optional[str] = None) -> str:
    scanner = SecurityScanner()
    if file_path:
        issues = scanner.scan_file(file_path)
        result = ScanResult(
            passed=len(issues) == 0,
            issues=issues,
            files_scanned=1,
            scan_time=0,
        )
    else:
        result = scanner.scan_project()
    return scanner.format_issues(result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(security_scan(sys.argv[1]))
    else:
        print(security_scan())
