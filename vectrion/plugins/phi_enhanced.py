"""PHI / Healthcare Data scanner plugin for Vectrion.

Detects healthcare identifiers: ICD-10 codes, NPI numbers, DEA registrations,
NDC drug codes, Medicare Beneficiary IDs, CPT and HCPCS procedure codes.

IMPORTANT: Raw matched values are NEVER stored — only a 16-char SHA-256 prefix
is retained for deduplication and auditing purposes.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Pattern catalogue
# ─────────────────────────────────────────────────────────────────────────────

_PHI_PATTERNS: list[dict[str, Any]] = [
    {
        "kind": "ICD-10 Code",
        "severity": "high",
        "pattern": re.compile(r"\b([A-TV-Z][0-9][0-9AB]\.?[0-9A-TV-Z]{0,4})\b"),
        # Context keyword required on the same line (reduces false positives)
        "keywords": re.compile(r"(?i)\b(diagnosis|diagnos|icd|icd-10|icd10|dx|condition|disorder)\b"),
    },
    {
        "kind": "NPI Number",
        "severity": "high",
        "pattern": re.compile(r"\b([12][0-9]{9})\b"),
        "keywords": re.compile(r"(?i)\b(npi|national provider|provider id|provider number|billing provider)\b"),
    },
    {
        "kind": "DEA Registration",
        "severity": "critical",
        "pattern": re.compile(r"\b([A-PR-UWXYZ][A-Z9][0-9]{7})\b"),
        "keywords": None,  # DEA format is distinct enough — no context required
    },
    {
        "kind": "NDC Drug Code",
        "severity": "high",
        "pattern": re.compile(r"\b([0-9]{4,5}-[0-9]{3,4}-[0-9]{1,2})\b"),
        "keywords": None,
    },
    {
        "kind": "Medicare Beneficiary ID",
        "severity": "high",
        "pattern": re.compile(r"\b([1-9][A-Z][A-Z0-9][0-9][A-Z][A-Z0-9][0-9][A-Z][A-Z0-9]{2}[0-9])\b"),
        "keywords": None,
    },
    {
        "kind": "CPT Code",
        "severity": "medium",
        "pattern": re.compile(r"\b([0-9]{4}[0-9TFM])\b"),
        "keywords": re.compile(r"(?i)\b(cpt|procedure code|procedure|billing code|service code)\b"),
    },
    {
        "kind": "HCPCS Code",
        "severity": "medium",
        "pattern": re.compile(r"\b([A-Z][0-9]{4})\b"),
        "keywords": re.compile(r"(?i)\b(hcpcs|healthcare common procedure|durable medical|dmr)\b"),
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
        for spec in _PHI_PATTERNS:
            # Context keyword check for ambiguous patterns
            if spec["keywords"] and not spec["keywords"].search(line):
                continue
            for m in spec["pattern"].finditer(line):
                matched = m.group(1) if m.lastindex else m.group(0)
                key = (spec["kind"], lineno, source_label)
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "detector":    spec["kind"],
                    "severity":    spec["severity"],
                    "source_file": source_label,
                    "line":        lineno,
                    "secret_hash": _hash_value(matched),
                    "method":      "regex",
                })

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class PHIEnhancedScanner:
    """
    Scan vault files for PHI / healthcare identifiers.

    Raw matched values are NEVER stored — only a 16-char SHA-256 prefix
    is retained for deduplication and auditing.
    """

    name = "phi-enhanced"

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
            "scanner_name":   "PHI / Healthcare Data",
            "findings":       all_findings,
            "files_scanned":  files_scanned,
            "total_findings": len(all_findings),
            "severity_counts": severity_counts,
            "critical_count": severity_counts.get("critical", 0),
            "high_count":     severity_counts.get("high", 0),
            "medium_count":   severity_counts.get("medium", 0),
            "method":         "regex",
        }
