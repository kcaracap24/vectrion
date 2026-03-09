"""Subprocess execution engine for multi-language custom plugins."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

LANGUAGE_META = {
    "python": {"cmd": ["python3", "{entry}"]},
    "node":   {"cmd": ["node", "{entry}"]},
    "java":   {"cmd": ["java", "-jar", "{entry}"]},
    "bash":   {"cmd": ["bash", "{entry}"]},
    "go":     {"cmd": ["./{entry}"]},
    "ruby":   {"cmd": ["ruby", "{entry}"]},
    "rust":   {"cmd": ["./{entry}"]},
}

# Entry filenames may only contain safe characters — no shell metacharacters,
# no path separators, no null bytes.
_SAFE_ENTRY_RE = re.compile(r'^[A-Za-z0-9_\-][A-Za-z0-9_\-\.]{0,127}$')


def _validate_entry(entry: str, plugin_dir: Path) -> Path:
    """Validate and resolve the plugin entry filename.

    Raises ValueError if the entry is unsafe or resolves outside plugin_dir.
    Returns the resolved absolute Path on success.
    """
    if not entry or not _SAFE_ENTRY_RE.match(entry):
        raise ValueError(
            f"Unsafe plugin entry filename {entry!r}. "
            "Only alphanumerics, hyphens, underscores, and dots are allowed."
        )
    resolved = (plugin_dir / entry).resolve()
    plugin_abs = plugin_dir.resolve()
    # Must stay inside the plugin directory
    if not str(resolved).startswith(str(plugin_abs) + "/") and resolved != plugin_abs:
        raise ValueError(f"Plugin entry {entry!r} resolves outside plugin directory.")
    if not resolved.exists():
        raise FileNotFoundError(f"Plugin entry file not found: {resolved}")
    return resolved


def run_plugin(plugin_dir: Path, manifest: dict, vault_dir: Path, vault_index: list) -> dict:
    """Execute a manifest-based plugin as a subprocess.

    Sends vault metadata as JSON to the plugin's stdin and reads a findings
    dict from stdout.  Stderr is captured and surfaced on non-zero exit.

    Parameters
    ----------
    plugin_dir  : directory that contains the plugin files (cwd for subprocess)
    manifest    : parsed plugin.json content
    vault_dir   : engagement upload directory
    vault_index : list of file metadata dicts from _index.json

    Returns
    -------
    dict matching the standard scan_vault return shape
    """
    lang = manifest.get("language", "python").lower()
    if lang not in LANGUAGE_META:
        raise ValueError(f"Unsupported language: {lang!r}")

    entry_raw = manifest.get("entry", "")
    entry_path = _validate_entry(entry_raw, plugin_dir)
    entry = entry_path.name  # safe, validated filename only

    meta = LANGUAGE_META[lang]
    cmd = [part.replace("{entry}", entry) for part in meta["cmd"]]
    stdin_data = json.dumps(
        {"vault_dir": str(vault_dir), "vault_index": vault_index}
    ).encode("utf-8")

    result = subprocess.run(
        cmd,
        cwd=str(plugin_dir.resolve()),
        input=stdin_data,
        capture_output=True,
        timeout=120,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or f"Plugin exited with code {result.returncode}")

    return json.loads(result.stdout.decode("utf-8"))
