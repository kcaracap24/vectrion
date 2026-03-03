"""Network IOC scanner plugin for Vectrion.

Detects public IPs, suspicious TLDs, disposable email domains, URL shorteners,
and data-exfiltration URL patterns.

Value preview: IPs truncated to x.x.x.*, domain paths stripped to registrable
domain only. Raw values are never stored.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_SUSPICIOUS_TLDS = {
    ".xyz", ".top", ".click", ".download", ".tk", ".ml",
    ".ga", ".cf", ".gq", ".pw", ".cc",
}

_DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.net",
    "guerrillamail.org", "guerrillamail.de", "guerrillamail.info",
    "tempmail.com", "temp-mail.org", "yopmail.com", "yopmail.fr",
    "throwam.com", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "guerrillamail.biz", "spam4.me", "trashmail.com",
    "trashmail.me", "trashmail.net", "dispostable.com",
    "mailnull.com", "spamgourmet.com", "maildrop.cc",
    "getairmail.com", "filzmail.com", "throwam.com",
}

_URL_SHORTENERS = {
    "bit.ly", "t.co", "tinyurl.com", "ow.ly", "short.io",
    "is.gd", "buff.ly", "goo.gl",
}

_IPV4_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")
_URL_RE = re.compile(r"https?://([^\s\"'<>\)]+)", re.IGNORECASE)
# Data-exfil: query string with large base64 or very long params
_EXFIL_B64_RE = re.compile(r"[?&][^=]+=([A-Za-z0-9+/]{100,}={0,2})")
_DOMAIN_RE = re.compile(r"\b(?:[A-Za-z0-9\-]+\.)+([A-Za-z]{2,})\b")

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _is_private_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        return addr.is_private or addr.is_loopback or addr.is_multicast or addr.is_link_local
    except ValueError:
        return True  # malformed — treat as non-public


def _redact_ip(ip_str: str) -> str:
    parts = ip_str.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.*"
    return ip_str


def _registrable_domain(host: str) -> str:
    """Return just the registrable domain (last two labels)."""
    parts = host.rstrip(".").split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _scan_text(text: str, source_label: str) -> list[dict]:
    findings: list[dict] = []
    seen: set[tuple] = set()
    lines = text.splitlines()

    for lineno, line in enumerate(lines, start=1):

        # ── Public / Private IPv4 ─────────────────────────────────────────
        for m in _IPV4_RE.finditer(line):
            ip = m.group(1)
            octets = ip.split(".")
            # Validate octet ranges
            try:
                if not all(0 <= int(o) <= 255 for o in octets):
                    continue
            except ValueError:
                continue
            private = _is_private_ip(ip)
            kind = "Internal IP Disclosed" if private else "Public IPv4"
            severity = "medium" if private else "high"
            display = _redact_ip(ip) if not private else ip
            key = (kind, ip, source_label)
            if key not in seen:
                seen.add(key)
                findings.append({
                    "detector":    kind,
                    "severity":    severity,
                    "source_file": source_label,
                    "line":        lineno,
                    "secret_hash": _hash_value(ip),
                    "method":      "regex",
                    "preview":     display,
                })

        # ── Disposable email domains ──────────────────────────────────────
        for m in _EMAIL_RE.finditer(line):
            domain = m.group(1).lower()
            if domain in _DISPOSABLE_DOMAINS:
                key = ("Disposable Email Domain", domain, source_label)
                if key not in seen:
                    seen.add(key)
                    findings.append({
                        "detector":    "Disposable Email Domain",
                        "severity":    "high",
                        "source_file": source_label,
                        "line":        lineno,
                        "secret_hash": _hash_value(domain),
                        "method":      "regex",
                        "preview":     f"*@{domain}",
                    })

        # ── URLs: shorteners, suspicious TLDs, data-exfil ────────────────
        for m in _URL_RE.finditer(line):
            url_tail = m.group(1)
            try:
                parsed = urlparse("https://" + url_tail)
                host = (parsed.hostname or "").lower()
                reg = _registrable_domain(host)
            except Exception:
                continue

            # URL shortener
            if host in _URL_SHORTENERS or reg in _URL_SHORTENERS:
                key = ("URL Shortener", reg, source_label, lineno)
                if key not in seen:
                    seen.add(key)
                    findings.append({
                        "detector":    "URL Shortener",
                        "severity":    "medium",
                        "source_file": source_label,
                        "line":        lineno,
                        "secret_hash": _hash_value(url_tail[:100]),
                        "method":      "regex",
                        "preview":     reg,
                    })

            # Suspicious TLD
            for tld in _SUSPICIOUS_TLDS:
                if host.endswith(tld):
                    key = ("Suspicious TLD", reg, source_label)
                    if key not in seen:
                        seen.add(key)
                        findings.append({
                            "detector":    "Suspicious TLD",
                            "severity":    "high",
                            "source_file": source_label,
                            "line":        lineno,
                            "secret_hash": _hash_value(reg),
                            "method":      "regex",
                            "preview":     reg,
                        })
                    break

            # Data-exfil URL pattern
            full_url = m.group(0)
            # Check for large base64 in query params
            if _EXFIL_B64_RE.search(full_url):
                key = ("Data Exfil URL Pattern", lineno, source_label)
                if key not in seen:
                    seen.add(key)
                    findings.append({
                        "detector":    "Data Exfil URL Pattern",
                        "severity":    "critical",
                        "source_file": source_label,
                        "line":        lineno,
                        "secret_hash": _hash_value(full_url[:100]),
                        "method":      "regex",
                        "preview":     reg,
                    })
            # Check for very long query string
            elif parsed.query and len(parsed.query) > 300:
                key = ("Data Exfil URL Pattern", lineno, source_label)
                if key not in seen:
                    seen.add(key)
                    findings.append({
                        "detector":    "Data Exfil URL Pattern",
                        "severity":    "critical",
                        "source_file": source_label,
                        "line":        lineno,
                        "secret_hash": _hash_value(parsed.query[:100]),
                        "method":      "regex",
                        "preview":     reg,
                    })

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class NetworkIOCScanner:
    """
    Scan vault files for network-level indicators of compromise.

    Raw values are never stored. IP addresses are truncated to x.x.x.*;
    domain paths are stripped to the registrable domain only.
    """

    name = "network-ioc"

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
            "scanner_name":   "Network IOCs",
            "findings":       all_findings,
            "files_scanned":  files_scanned,
            "total_findings": len(all_findings),
            "severity_counts": severity_counts,
            "critical_count": severity_counts.get("critical", 0),
            "high_count":     severity_counts.get("high", 0),
            "medium_count":   severity_counts.get("medium", 0),
            "method":         "regex",
        }
