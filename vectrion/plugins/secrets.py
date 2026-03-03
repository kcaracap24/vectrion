"""Secrets detection plugin for Vectrion.

Scans vault files for credentials, API keys, tokens, and other secrets.
Attempts the TruffleHog binary first; falls back to a built-in regex engine.

IMPORTANT: Raw secret values are NEVER stored.
Only the detector type, file, line number, severity, and a short SHA-256
prefix of the matched value are written to the runbook.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Regex pattern catalogue
# ─────────────────────────────────────────────────────────────────────────────

_SECRET_PATTERNS: list[dict[str, Any]] = [
    # AWS
    {
        "kind": "AWS Access Key",
        "severity": "critical",
        "pattern": re.compile(r"(?:^|[^A-Z0-9])(A(?:KIA|SIA|ROA|NPA)[0-9A-Z]{16})(?:[^A-Z0-9]|$)"),
    },
    {
        "kind": "AWS Secret Key",
        "severity": "critical",
        "pattern": re.compile(r"(?i)aws[_\-\s]?secret[_\-\s]?(?:access[_\-\s]?)?key[\"'\s:=]+([A-Za-z0-9/+=]{40})"),
    },
    # GitHub
    {
        "kind": "GitHub Token",
        "severity": "critical",
        "pattern": re.compile(
            r"(ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}"
            r"|ghs_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})"
        ),
    },
    # Google
    {
        "kind": "Google API Key",
        "severity": "high",
        "pattern": re.compile(r"(AIza[0-9A-Za-z\-_]{35})"),
    },
    {
        "kind": "Google OAuth Token",
        "severity": "high",
        "pattern": re.compile(r"(ya29\.[0-9A-Za-z\-_]{20,})"),
    },
    # Stripe
    {
        "kind": "Stripe Secret Key",
        "severity": "critical",
        "pattern": re.compile(r"(sk_(?:live|test)_[0-9A-Za-z]{24,99})"),
    },
    {
        "kind": "Stripe Publishable Key",
        "severity": "medium",
        "pattern": re.compile(r"(pk_(?:live|test)_[0-9A-Za-z]{24,99})"),
    },
    # Slack
    {
        "kind": "Slack Bot Token",
        "severity": "high",
        "pattern": re.compile(r"(xoxb-[0-9]{10,13}-[0-9]{10,13}[A-Za-z0-9-]*)"),
    },
    {
        "kind": "Slack Webhook",
        "severity": "high",
        "pattern": re.compile(
            r"(https://hooks\.slack\.com/services/T[A-Z0-9]{8,}/B[A-Z0-9]{8,}/[A-Za-z0-9]{24})"
        ),
    },
    # Twilio
    {
        "kind": "Twilio Account SID",
        "severity": "high",
        "pattern": re.compile(r"(AC[a-f0-9]{32})"),
    },
    {
        "kind": "Twilio Auth Token",
        "severity": "critical",
        "pattern": re.compile(r"(?i)twilio[_\s\-]?auth[_\s\-]?token[\"'\s:=]+([a-f0-9]{32})"),
    },
    # Private keys (header lines — no value to hash, just flag presence)
    {
        "kind": "RSA Private Key",
        "severity": "critical",
        "pattern": re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
    },
    {
        "kind": "EC Private Key",
        "severity": "critical",
        "pattern": re.compile(r"-----BEGIN EC PRIVATE KEY-----"),
    },
    {
        "kind": "PGP Private Key",
        "severity": "critical",
        "pattern": re.compile(r"-----BEGIN PGP PRIVATE KEY BLOCK-----"),
    },
    {
        "kind": "SSH Private Key",
        "severity": "critical",
        "pattern": re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
    },
    # JWT
    {
        "kind": "JWT Token",
        "severity": "high",
        "pattern": re.compile(r"(eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)"),
    },
    # Database connection strings
    {
        "kind": "DB Connection String",
        "severity": "critical",
        "pattern": re.compile(
            r"((?:mysql|postgres|postgresql|mongodb|mssql|oracle)://[^:\"'\s]+:[^@\"'\s]+@[^\s\"']+)",
            re.IGNORECASE,
        ),
    },
    # SendGrid
    {
        "kind": "SendGrid API Key",
        "severity": "critical",
        "pattern": re.compile(r"(SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43})"),
    },
    # NPM token
    {
        "kind": "NPM Token",
        "severity": "high",
        "pattern": re.compile(r"(npm_[A-Za-z0-9]{36})"),
    },
    # Square
    {
        "kind": "Square Access Token",
        "severity": "critical",
        "pattern": re.compile(r"(sq0atp-[0-9A-Za-z\-_]{22})"),
    },
    # Shopify
    {
        "kind": "Shopify Access Token",
        "severity": "critical",
        "pattern": re.compile(r"(shpat_[a-fA-F0-9]{32})"),
    },
    # Generic password/secret assignments (catch-all, lower priority)
    {
        "kind": "Generic Secret",
        "severity": "medium",
        "pattern": re.compile(
            r"(?i)(?:password|passwd|secret|api[_\-]?key|auth[_\-]?token)"
            r"[\"'\s:=]+([A-Za-z0-9!@#$%^&*()\-_=+\[\]{};:,.<>/?]{12,})"
        ),
    },
]

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hash_secret(value: str) -> str:
    """Return a short SHA-256 hex prefix — never the raw value."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _scan_text_regex(text: str, source_label: str) -> list[dict]:
    """Scan plain text with the built-in regex catalogue."""
    findings: list[dict] = []
    seen: set[tuple] = set()
    lines = text.splitlines()

    for lineno, line in enumerate(lines, start=1):
        for spec in _SECRET_PATTERNS:
            m = spec["pattern"].search(line)
            if not m:
                continue
            matched = m.group(1) if m.lastindex else m.group(0)
            key = (spec["kind"], lineno, source_label)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "detector":    spec["kind"],
                    "severity":    spec["severity"],
                    "source_file": source_label,
                    "line":        lineno,
                    "secret_hash": _hash_secret(matched),
                    "method":      "regex",
                }
            )

    return findings


def _try_trufflehog(path: Path) -> list[dict] | None:
    """Try the trufflehog binary. Returns findings or None if unavailable."""
    if not shutil.which("trufflehog"):
        return None
    try:
        result = subprocess.run(
            ["trufflehog", "filesystem", "--json", "--no-update", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        findings: list[dict] = []
        for raw_line in result.stdout.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
                raw_val = obj.get("Raw", "") or obj.get("RawV2", "")
                fs_meta = (
                    obj.get("SourceMetadata", {})
                    .get("Data", {})
                    .get("Filesystem", {})
                )
                findings.append(
                    {
                        "detector":    obj.get("DetectorName", "Unknown"),
                        "severity":    "high",
                        "source_file": fs_meta.get("file", str(path)),
                        "line":        fs_meta.get("line", 0),
                        "secret_hash": _hash_secret(raw_val) if raw_val else "",
                        "method":      "trufflehog",
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return findings
    except (subprocess.TimeoutExpired, OSError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class SecretsScanner:
    """
    Scan vault files for secrets (API keys, tokens, private keys, etc.).

    Raw secret values are NEVER stored — only a 16-char SHA-256 prefix
    of the matched value is retained for deduplication and auditing.
    """

    name = "secrets-scanner"

    def scan_file(self, path: Path, label: str | None = None) -> list[dict]:
        """Scan a single file. Returns findings list."""
        # Prefer trufflehog when available
        th = _try_trufflehog(path)
        if th is not None:
            return th
        # Regex fallback
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return _scan_text_regex(text, label or str(path))

    def scan_vault(self, vault_dir: Path, vault_index: list[dict]) -> dict:
        """
        Scan all vault files.
        Returns a summary dict suitable for ``state["secrets_scan"]``.
        """
        all_findings: list[dict] = []
        files_scanned: list[str] = []
        seen_keys: set[tuple] = set()

        for entry in vault_index:
            orig_name = entry.get("original_name", entry["filename"])

            # Prefer the extracted .txt file (cleaner text for scanning)
            txt_path = vault_dir / (entry["filename"] + ".txt")
            raw_path = vault_dir / entry["filename"]

            scan_path = txt_path if txt_path.exists() else raw_path
            if not scan_path.exists():
                continue

            # Skip very large files to avoid timeouts
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

        # Sort by severity then file
        all_findings.sort(
            key=lambda f: (_SEVERITY_ORDER.get(f.get("severity", "unknown"), 4), f.get("source_file", ""))
        )

        severity_counts: dict[str, int] = {}
        for f in all_findings:
            sev = f.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "findings":       all_findings,
            "files_scanned":  files_scanned,
            "total_findings": len(all_findings),
            "severity_counts": severity_counts,
            "critical_count": severity_counts.get("critical", 0),
            "high_count":     severity_counts.get("high", 0),
            "medium_count":   severity_counts.get("medium", 0),
            "method":         "trufflehog" if shutil.which("trufflehog") else "regex",
        }
