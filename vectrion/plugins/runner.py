"""Subprocess execution engine for multi-language custom plugins."""
from __future__ import annotations

import json
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
    entry = manifest.get("entry", "")
    meta = LANGUAGE_META.get(lang)
    if not meta:
        raise ValueError(f"Unsupported language: {lang!r}")

    cmd = [part.replace("{entry}", entry) for part in meta["cmd"]]
    stdin_data = json.dumps(
        {"vault_dir": str(vault_dir), "vault_index": vault_index}
    ).encode("utf-8")

    result = subprocess.run(
        cmd,
        cwd=str(plugin_dir),
        input=stdin_data,
        capture_output=True,
        timeout=120,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or f"Plugin exited with code {result.returncode}")

    return json.loads(result.stdout.decode("utf-8"))
