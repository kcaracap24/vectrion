from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class IncidentState:
    incident_id: str
    current_layer: str = "1"
    completed_layers: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "current_layer": self.current_layer,
            "completed_layers": self.completed_layers,
            "data": self.data,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "IncidentState":
        return cls(
            incident_id=raw["incident_id"],
            current_layer=raw.get("current_layer", "1"),
            completed_layers=raw.get("completed_layers", []),
            data=raw.get("data", {}),
            created_at=raw.get("created_at", utc_now_iso()),
            updated_at=raw.get("updated_at", utc_now_iso()),
        )
