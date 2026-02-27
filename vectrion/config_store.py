from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vectrion.constants import DEFAULT_STAGES

_CONFIG_FILENAME = "config.json"

_DEFAULT_INCIDENT_FORMAT = {
    "prefix": "INC",
    "year": True,
    "separator": "-",
    "digits": 4,
}


def _default_config() -> dict[str, Any]:
    return {
        "setup_complete": False,
        "incident_code_format": dict(_DEFAULT_INCIDENT_FORMAT),
        "stages": [
            {
                "id": s["id"],
                "name": s["name"],
                "custom_name": "",
                "enabled": True,
                "owner": "",
                "notes": "",
            }
            for s in DEFAULT_STAGES
        ],
    }


def _config_path(workdir: str | Path) -> Path:
    return Path(workdir) / _CONFIG_FILENAME


def load_config(workdir: str | Path = ".vectrion") -> dict[str, Any]:
    p = _config_path(workdir)
    if not p.exists():
        return _default_config()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return _default_config()


def save_config(workdir: str | Path, config: dict[str, Any]) -> None:
    p = _config_path(workdir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, indent=2), encoding="utf-8")


def is_setup_complete(workdir: str | Path = ".vectrion") -> bool:
    return bool(load_config(workdir).get("setup_complete", False))


def get_active_stages(workdir: str | Path = ".vectrion") -> list[dict[str, Any]]:
    cfg = load_config(workdir)
    return [s for s in cfg.get("stages", []) if s.get("enabled", True)]


def get_stage_order(workdir: str | Path = ".vectrion") -> list[str]:
    return [s["id"] for s in get_active_stages(workdir)]


def get_stage_name(stage_id: str, workdir: str | Path = ".vectrion") -> str:
    cfg = load_config(workdir)
    for s in cfg.get("stages", []):
        if s["id"] == stage_id:
            return s.get("custom_name") or s.get("name", stage_id)
    return stage_id
