"""Encoded / Injected Payload scanner plugin for Vectrion.

Detects Base64 blobs, hex payloads, SQL injection patterns, command injection,
path traversal, and script injection indicators.

Raw matches are NEVER stored — only a 16-char SHA-256 prefix is retained.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Pattern catalogue
# ─────────────────────────────────────────────────────────────────────────────

_PAYLOAD_PATTERNS: list[dict[str, Any]] = [
    {
        "kind": "Base64 Blob",
        "severity": "high",
        "pattern": re.compile(r"[A-Za-z0-9+/]{100,}={0,2}"),
    },
    {
        "kind": "Hex Payload",
        "severity": "high",
        "pattern": re.compile(r"\b[0-9a-fA-F]{80,}\b"),
    },
    {
        "kind": "SQL Injection",
        "severity": "critical",
        "pattern": re.compile(
            r"(?i)(UNION\s+(?:ALL\s+)?SELECT|1\s*=\s*1|DROP\s+TABLE"
            r"|xp_cmdshell|OR\s+'[^']+'\s*=\s*'[^']+')",
        ),
    },
    {
        "kind": "Command Injection",
        "severity": "critical",
        "pattern": re.compile(
            r"(?i)(cmd\.exe|powershell\s+-|/bin/(?:sh|bash)\s+-"
            r"|nc\s+-e|wget\s+http|curl\s+-[a-z]*\s+http)",
        ),
    },
    {
        "kind": "Path Traversal",
        "severity": "high",
        "pattern": re.compile(r"(?:\.\.[\\/]){2,}|%2e%2e(?:%2f|%5c)", re.IGNORECASE),
    },
    {
        "kind": "Script Injection",
        "severity": "critical",
        "pattern": re.compile(
            r"(?i)(<script[\s>]|javascript:|eval\s*\(|document\.write\s*\()",
        ),
    },
]

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _scan_text(text: str, source_label: str) -> list[dict]:
    findings: list[dict] = []
    seen: set[tuple] = set()
    lines = text.splitlines()

    for lineno, line in enumerate(lines, start=1):
        for spec in _PAYLOAD_PATTERNS:
            m = spec["pattern"].search(line)
            if not m:
                continue
            matched = m.group(0)
            key = (spec["kind"], lineno, source_label)
            if key in seen:
                continue
            seen.add(key)
            findings.append({
                "detector":    spec["kind"],
                "severity":    spec["severity"],
                "source_file": source_label,
                "line":        lineno,
                "secret_hash": _hash_value(matched[:200]),
                "method":      "regex",
            })

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class EncodedPayloadScanner:
    """
    Scan vault files for encoded blobs and injection attack signatures.

    Raw matches are NEVER stored — only a 16-char SHA-256 prefix is retained.
    """

    name = "encoded-payload"

    def scan_file(self, path: Path, label: str | None = None) -> list[dict]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return _scan_text(text, label or str(path))

    def scan_vault(self, vault_dir: Path, vault_index: list[dict]) -> dict:
        all_findings: list[dict] = []
        files_scanned: list[str] = []
        seen_keys: set[tuple] = set()

        for entry in vault_index:
            orig_name = entry.get("original_name", entry["filename"])
            txt_path = vault_dir / (entry["filename"] + ".txt")
            raw_path = vault_dir / entry["filename"]
            scan_path = txt_path if txt_path.exists() else raw_path
            if not scan_path.exists():
                continue
            if scan_path.stat().st_size > 10_000_000:
                continue

            findings = self.scan_file(scan_path, label=orig_name)
            for f in findings:
                f["original_name"] = orig_name
                key = (f["detector"], f["line"], f["source_file"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_findings.append(f)

            files_scanned.append(orig_name)

        all_findings.sort(
            key=lambda f: (_SEVERITY_ORDER.get(f.get("severity", "unknown"), 4), f.get("source_file", ""))
        )

        severity_counts: dict[str, int] = {}
        for f in all_findings:
            sev = f.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "scanner_name":   "Encoded / Injected Payloads",
            "findings":       all_findings,
            "files_scanned":  files_scanned,
            "total_findings": len(all_findings),
            "severity_counts": severity_counts,
            "critical_count": severity_counts.get("critical", 0),
            "high_count":     severity_counts.get("high", 0),
            "medium_count":   severity_counts.get("medium", 0),
            "method":         "regex",
        }
