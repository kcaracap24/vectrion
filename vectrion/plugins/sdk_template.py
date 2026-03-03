"""Vectorian Custom Scanner SDK Template
========================================
Copy this file to <workdir>/custom_plugins/my_scanner.py
and fill in the class below.

Requirements
------------
Your class MUST:
  1. Have a ``display_name`` class attribute (string).
  2. Implement ``scan_file(self, path, label=None) -> list[dict]``
  3. Implement ``scan_vault(self, vault_dir, vault_index) -> dict``

Severity values
---------------
Use these exact strings for the ``severity`` field in each finding:
    "critical"  — credentials, private keys, high-impact PII
    "high"      — sensitive personal data, tokens
    "medium"    — potentially sensitive patterns
    "low"       — informational findings

Finding dict structure (returned by scan_file)
----------------------------------------------
{
    "detector":    "MyCustomScanner",   # str — name of the detector rule
    "severity":    "high",              # str — critical / high / medium / low
    "source_file": "path/to/file.txt",  # str — path that was scanned
    "line":        42,                  # int — line number of match (0 if unknown)
    "secret_hash": "abc123def456",      # str — short hash/fingerprint of matched value
    "method":      "regex",             # str — how the finding was detected
}

scan_vault return shape
-----------------------
{
    "scanner_name":    "My Custom Scanner",
    "findings":        [...],           # list[dict] — all findings from all files
    "files_scanned":   [...],           # list[str]  — all file paths attempted
    "total_findings":  0,               # int
    "severity_counts": {},              # dict[str, int] — counts per severity level
    "critical_count":  0,               # int
    "high_count":      0,               # int
    "medium_count":    0,               # int
    "method":          "regex",         # str
}
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


class CustomScannerTemplate:
    """
    Rename this class, set display_name, and fill in your detection patterns.
    Vectorian discovers this class automatically — no registration required.
    The file just needs to live in <workdir>/custom_plugins/ and be enabled
    on the Plugins page.
    """

    display_name = "My Custom Scanner"

    # ── Detection patterns ────────────────────────────────────────────────────
    # Map a short rule name → (compiled regex, severity string).
    # Add as many entries as you need.
    _PATTERNS: dict[str, tuple[re.Pattern, str]] = {
        # Example: generic "api_key = ..." assignment pattern
        "example_api_key": (
            re.compile(
                r'(?i)api[-_]?key\s*[=:]\s*["\']?([A-Za-z0-9_\-]{20,50})'
            ),
            "high",
        ),
        # Example: bearer token in Authorization header
        "bearer_token": (
            re.compile(r'(?i)Bearer\s+([A-Za-z0-9_\-\.]{20,200})'),
            "high",
        ),
        # Add your own patterns here…
    }

    # ─────────────────────────────────────────────────────────────────────────

    def scan_file(self, path, label: str | None = None) -> list[dict]:
        """
        Scan a single file and return a list of finding dicts.

        Parameters
        ----------
        path  : str or Path — path to the file to scan
        label : optional display name (e.g. original filename before rename)

        Returns
        -------
        list of finding dicts — empty list if no findings or file unreadable
        """
        findings: list[dict] = []
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return findings

        source = label or str(path)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule_name, (pattern, severity) in self._PATTERNS.items():
                for match in pattern.finditer(line):
                    matched_value = match.group(0)
                    findings.append({
                        "detector":    rule_name,
                        "severity":    severity,
                        "source_file": source,
                        "line":        line_no,
                        "secret_hash": hashlib.sha256(
                            matched_value.encode()
                        ).hexdigest()[:12],
                        "method":      "regex",
                    })
        return findings

    def scan_vault(self, vault_dir, vault_index: list[dict]) -> dict:
        """
        Scan all files in the engagement vault.

        Parameters
        ----------
        vault_dir   : str or Path — directory containing uploaded files
        vault_index : list of file metadata dicts (keys: filename, original_name, …)

        Returns
        -------
        dict matching the scan_vault return shape (see module docstring)
        """
        vault_dir = Path(vault_dir)
        all_findings: list[dict] = []
        files_scanned: list[str] = []

        for entry in vault_index:
            filename = entry.get("filename", "")
            original_name = entry.get("original_name", filename)
            file_path = vault_dir / filename
            if not file_path.exists():
                continue
            files_scanned.append(original_name)
            findings = self.scan_file(file_path, label=original_name)
            all_findings.extend(findings)

        severity_counts: dict[str, int] = {}
        for f in all_findings:
            sev = f.get("severity", "low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "scanner_name":    self.display_name,
            "findings":        all_findings,
            "files_scanned":   files_scanned,
            "total_findings":  len(all_findings),
            "severity_counts": severity_counts,
            "critical_count":  severity_counts.get("critical", 0),
            "high_count":      severity_counts.get("high", 0),
            "medium_count":    severity_counts.get("medium", 0),
            "method":          "regex",
        }
