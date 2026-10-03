"""Deterministic security scanner for external capabilities and skills."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from orkestra.schemas.scanner import (
    ScanResult,
    SecurityViolation,
    SecurityViolationSeverity,
)

# Textual regex patterns: (rule_id, severity, regex, explanation)
TEXT_SECURITY_PATTERNS: list[tuple[str, SecurityViolationSeverity, re.Pattern[str], str]] = [
    # 1. Directory traversal / escape
    (
        "TRAV-001",
        SecurityViolationSeverity.HIGH,
        re.compile(r"(\.\.[/\\])+", re.IGNORECASE),
        "Path traversal sequence detected ('../' or '..\\')",
    ),
    (
        "ESC-001",
        SecurityViolationSeverity.CRITICAL,
        re.compile(r"(~[/\\]\.ssh|/etc/(passwd|shadow)|C:\\Windows\\System32)", re.IGNORECASE),
        "Access to sensitive host system directories detected",
    ),
    # 2. Destructive system operations
    (
        "DEST-001",
        SecurityViolationSeverity.CRITICAL,
        re.compile(
            r"(rm\s+-(?:r[fv]|fr)\s+[/~]|format\s+[c-z]:|del\s+/[sfq]|rmdir\s+/[sq]|dd\s+if=/dev/zero)",
            re.IGNORECASE,
        ),
        "Destructive disk/filesystem operation detected",
    ),
    (
        "DEST-002",
        SecurityViolationSeverity.CRITICAL,
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),
        "Fork bomb pattern detected",
    ),
    # 3. Exfiltration & obfuscation
    (
        "EXFIL-001",
        SecurityViolationSeverity.HIGH,
        re.compile(
            r"(curl\s+-[dF]\s*@|wget\s+--post-file|powershell.*-(?:enc|encodedcommand)\b)",
            re.IGNORECASE,
        ),
        "Outbound data exfiltration or encoded command execution pattern detected",
    ),
    (
        "SHELL-001",
        SecurityViolationSeverity.CRITICAL,
        re.compile(r"(nc\s+.*-e\s+|bash\s+-i\s+>&|/dev/tcp/)", re.IGNORECASE),
        "Reverse shell or interactive network pipe detected",
    ),
    # 4. Prompt injection & guardrail bypass
    (
        "INJ-001",
        SecurityViolationSeverity.HIGH,
        re.compile(
            r"(ignore\s+(?:all\s+)?(?:previous\s+)?instructions|disregard\s+(?:all\s+)?(?:safety|policy|guardrails)|bypass\s+(?:verification|policy|gates))",
            re.IGNORECASE,
        ),
        "Prompt injection or guardrail subversion phrase detected",
    ),
    (
        "INJ-002",
        SecurityViolationSeverity.MEDIUM,
        re.compile(
            r"(<\|im_start\|>|\[SYSTEM\]|<system>|SYSTEM\s+PROMPT\s+OVERRIDE)",
            re.IGNORECASE,
        ),
        "System prompt framing or special delimiter injection detected",
    ),
]


class SkillSecurityScanner:
    """Deterministic security scanner verifying skills and capabilities before admission."""

    def __init__(self, max_allowed_risk: float = 0.3) -> None:
        self.max_allowed_risk = max_allowed_risk

    def scan_text(self, content: str, source_name: str = "<memory>") -> ScanResult:
        """Scan raw text/markdown/YAML content for prompt injection and security hazards."""
        violations: list[SecurityViolation] = []
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            for rule_id, severity, pattern, msg in TEXT_SECURITY_PATTERNS:
                m = pattern.search(line)
                if m:
                    violations.append(
                        SecurityViolation(
                            rule_id=rule_id,
                            severity=severity,
                            message=f"{msg} in {source_name}",
                            line=line_num,
                            evidence=m.group(0)[:100],
                        )
                    )

        return self._build_result(violations, len(content.encode("utf-8")))

    def scan_python_code(self, code: str, source_name: str = "<script>") -> ScanResult:
        """Scan Python code via AST parsing for dangerous builtin and system calls."""
        text_result = self.scan_text(code, source_name)
        violations = list(text_result.violations)

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Detect eval() or exec()
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("eval", "exec", "compile")
                ):
                    violations.append(
                        SecurityViolation(
                            rule_id="AST-001",
                            severity=SecurityViolationSeverity.CRITICAL,
                            message=f"Dangerous dynamic call '{node.func.id}()' detected",
                            line=node.lineno,
                            evidence=f"{node.func.id}(...)",
                        )
                    )
                # Detect os.system() or __import__
                elif (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr == "system"
                ):
                    violations.append(
                        SecurityViolation(
                            rule_id="AST-002",
                            severity=SecurityViolationSeverity.CRITICAL,
                            message="Unsanitized 'os.system()' call detected",
                            line=node.lineno,
                            evidence="os.system(...)",
                        )
                    )
        except SyntaxError as e:
            violations.append(
                SecurityViolation(
                    rule_id="SYN-001",
                    severity=SecurityViolationSeverity.MEDIUM,
                    message=f"Syntax error during AST inspection: {e}",
                    line=e.lineno,
                    evidence=e.text.strip() if e.text else "",
                )
            )

        return self._build_result(violations, len(code.encode("utf-8")))

    def scan_file(self, path: Path) -> ScanResult:
        """Scan a file on disk."""
        if not path.exists():
            return ScanResult(
                is_safe=False,
                risk_score=1.0,
                highest_severity=SecurityViolationSeverity.CRITICAL,
                violations=[
                    SecurityViolation(
                        rule_id="FILE-001",
                        severity=SecurityViolationSeverity.CRITICAL,
                        message=f"File not found: {path}",
                    )
                ],
                scanned_bytes=0,
            )

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return ScanResult(
                is_safe=False,
                risk_score=1.0,
                highest_severity=SecurityViolationSeverity.CRITICAL,
                violations=[
                    SecurityViolation(
                        rule_id="FILE-002",
                        severity=SecurityViolationSeverity.CRITICAL,
                        message=f"Failed to read file: {e}",
                    )
                ],
                scanned_bytes=0,
            )

        if path.suffix in (".py", ".pyw"):
            return self.scan_python_code(content, str(path))
        return self.scan_text(content, str(path))

    def _build_result(self, violations: list[SecurityViolation], scanned_bytes: int) -> ScanResult:
        if not violations:
            return ScanResult(
                is_safe=True,
                risk_score=0.0,
                highest_severity=None,
                violations=[],
                scanned_bytes=scanned_bytes,
            )

        severity_weights = {
            SecurityViolationSeverity.INFO: 0.05,
            SecurityViolationSeverity.LOW: 0.1,
            SecurityViolationSeverity.MEDIUM: 0.3,
            SecurityViolationSeverity.HIGH: 0.6,
            SecurityViolationSeverity.CRITICAL: 1.0,
        }

        max_sev = max(violations, key=lambda v: severity_weights[v.severity]).severity
        total_risk = min(1.0, sum(severity_weights[v.severity] for v in violations))
        is_safe = total_risk <= self.max_allowed_risk and max_sev not in (
            SecurityViolationSeverity.HIGH,
            SecurityViolationSeverity.CRITICAL,
        )

        return ScanResult(
            is_safe=is_safe,
            risk_score=round(total_risk, 3),
            highest_severity=max_sev,
            violations=violations,
            scanned_bytes=scanned_bytes,
        )
