"""Plugin registry for Vectrion.

Single source of truth for plugin metadata and per-installation config.
Config is persisted to <workdir>/plugins.json.
"""
from __future__ import annotations

import json
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Plugin metadata catalogue
# ─────────────────────────────────────────────────────────────────────────────

_PLUGIN_META: list[dict] = [
    # ── Core Scanners ────────────────────────────────────────────────────────
    {
        "id": "secrets-scanner",
        "name": "Secrets & Credentials",
        "category": "Core Scanners",
        "icon": "&#128272;",
        "description": "API keys, tokens, private keys (TruffleHog + regex). 20+ detector types.",
        "tags": ["AWS", "GitHub", "Stripe", "JWT", "SSH Keys"],
        "external": False,
    },
    {
        "id": "phi-enhanced",
        "name": "PHI / Healthcare Data",
        "category": "Core Scanners",
        "icon": "&#129657;",
        "description": "ICD-10 codes, NPI, DEA registrations, NDC drug codes, Medicare Beneficiary IDs, CPT/HCPCS procedure codes.",
        "tags": ["ICD-10", "NPI", "DEA", "NDC", "Medicare", "CPT"],
        "external": False,
    },
    {
        "id": "network-ioc",
        "name": "Network IOCs",
        "category": "Core Scanners",
        "icon": "&#127760;",
        "description": "Public IPs, suspicious TLDs, disposable email domains, URL shorteners, data-exfil URL patterns.",
        "tags": ["IP Addresses", "Phishing TLDs", "Disposable Email", "URL Shorteners"],
        "external": False,
    },
    {
        "id": "encoded-payload",
        "name": "Encoded / Injected Payloads",
        "category": "Core Scanners",
        "icon": "&#9888;",
        "description": "Base64 blobs, hex payloads, SQL injection, command injection, path traversal, script injection.",
        "tags": ["SQLi", "Base64", "Command Injection", "Path Traversal", "XSS"],
        "external": False,
    },
    # ── External Integrations ─────────────────────────────────────────────────
    {
        "id": "hibp",
        "name": "HaveIBeenPwned",
        "category": "External Integrations",
        "icon": "&#128683;",
        "description": "Check extracted emails against the HaveIBeenPwned breach database.",
        "tags": ["Email Breach Lookup", "Dark Web"],
        "external": True,
        "api_key_label": "HIBP API Key",
        "api_key_url": "https://haveibeenpwned.com/API/v3",
    },
    {
        "id": "virustotal",
        "name": "VirusTotal",
        "category": "External Integrations",
        "icon": "&#128737;",
        "description": "File hash reputation lookup against VirusTotal threat intelligence.",
        "tags": ["File Reputation", "Malware Hash"],
        "external": True,
        "api_key_label": "VirusTotal API Key",
        "api_key_url": "https://www.virustotal.com/gui/my-apikey",
    },
    {
        "id": "shodan",
        "name": "Shodan",
        "category": "External Integrations",
        "icon": "&#128225;",
        "description": "Enrich public IPs with open ports, services, and known CVEs via Shodan.",
        "tags": ["IP Intelligence", "Attack Surface"],
        "external": True,
        "api_key_label": "Shodan API Key",
        "api_key_url": "https://account.shodan.io/",
    },
]

# Map of scanner IDs to their classes (populated lazily to avoid circular imports)
_SCANNER_MAP: dict[str, type] | None = None


def _get_scanner_map() -> dict[str, type]:
    global _SCANNER_MAP
    if _SCANNER_MAP is None:
        from vectrion.plugins.phi_enhanced import PHIEnhancedScanner
        from vectrion.plugins.network_ioc import NetworkIOCScanner
        from vectrion.plugins.encoded_payload import EncodedPayloadScanner
        _SCANNER_MAP = {
            "phi-enhanced": PHIEnhancedScanner,
            "network-ioc": NetworkIOCScanner,
            "encoded-payload": EncodedPayloadScanner,
        }
    return _SCANNER_MAP


# ─────────────────────────────────────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────────────────────────────────────

def _config_path(workdir) -> Path:
    return Path(workdir) / "plugins.json"


def _default_config() -> dict:
    """Build default config: core plugins enabled, external disabled."""
    cfg: dict[str, dict] = {}
    for meta in _PLUGIN_META:
        if meta["external"]:
            cfg[meta["id"]] = {"enabled": False, "api_key": ""}
        else:
            cfg[meta["id"]] = {"enabled": True}
    return cfg


def load_plugin_config(workdir) -> dict:
    """Load plugins.json, filling in defaults for any missing entries."""
    path = _config_path(workdir)
    cfg = _default_config()
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            for pid, vals in saved.items():
                if pid in cfg:
                    cfg[pid].update(vals)
                else:
                    cfg[pid] = vals
        except Exception:
            pass
    return cfg


def save_plugin_config(workdir, config: dict) -> None:
    """Persist plugin config to plugins.json."""
    path = _config_path(workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def is_plugin_enabled(plugin_id: str, workdir) -> bool:
    cfg = load_plugin_config(workdir)
    return bool(cfg.get(plugin_id, {}).get("enabled", False))


def get_plugin_api_key(plugin_id: str, workdir) -> str:
    cfg = load_plugin_config(workdir)
    return cfg.get(plugin_id, {}).get("api_key", "")
