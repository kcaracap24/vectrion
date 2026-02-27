from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vectrion.models import utc_now_iso
from vectrion.persistence import maybe_postgres


class Storage:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.state_dir = base_dir / "state"
        self.audit_dir = base_dir / "audit"
        self.exports_dir = base_dir / "exports"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        migrations = Path(__file__).resolve().parent / "migrations"
        self.pg = maybe_postgres(migrations)
        if self.pg:
            self.pg.apply_migrations()

    def _state_path(self, incident_id: str) -> Path:
        return self.state_dir / f"{incident_id}.json"

    def _audit_path(self, incident_id: str) -> Path:
        return self.audit_dir / f"{incident_id}.log"

    def load_state_obj(self, incident_id: str) -> dict[str, Any]:
        p = self._state_path(incident_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def save_state_obj(self, incident_id: str, obj: dict[str, Any]) -> None:
        obj["updated_at"] = utc_now_iso()
        if "created_at" not in obj:
            obj["created_at"] = utc_now_iso()
        self._state_path(incident_id).write_text(json.dumps(obj, indent=2), encoding="utf-8")
        if self.pg:
            self.pg.upsert_incident(obj)

    def load_state(self, incident_id: str) -> dict[str, Any]:
        return self.load_state_obj(incident_id)

    def save_state(self, state: dict[str, Any]) -> None:
        self.save_state_obj(state["incident_id"], state)

    def audit(self, incident_id: str, action: str, payload: dict[str, Any] = None) -> None:
        row = {
            "ts": utc_now_iso(),
            "action": action,
            "payload": payload or {},
        }
        with self._audit_path(incident_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        if self.pg:
            self.pg.insert_audit(incident_id, action, payload or {})

    def persist_core_entities(self, incident_id: str, runbook: dict[str, Any]) -> None:
        if not self.pg:
            return
        self.pg.replace_records("evidence_files", incident_id, runbook.get("evidence_files", []))
        self.pg.replace_records("normalized_records", incident_id, runbook.get("extracted", []))
        self.pg.replace_records("pii_findings", incident_id, runbook.get("pii_summary", []))
        self.pg.replace_records("identity_links", incident_id, runbook.get("identity_scores", []))
        self.pg.replace_records("affected_people", incident_id, runbook.get("affected_people", []))
        draft = runbook.get("notification_draft")
        if draft:
            self.pg.replace_records("drafts", incident_id, [{"draft": draft}])
