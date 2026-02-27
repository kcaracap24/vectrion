from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PostgresPersistence:
    dsn: str
    migrations_dir: Path

    def _connect(self):
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "psycopg is required for Postgres persistence. Install with: pip install psycopg[binary]"
            ) from exc
        return psycopg.connect(self.dsn)

    def apply_migrations(self) -> None:
        files = sorted(self.migrations_dir.glob("*.sql"))
        if not files:
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                for f in files:
                    cur.execute("SELECT 1 FROM schema_migrations WHERE filename=%s", (f.name,))
                    if cur.fetchone():
                        continue
                    cur.execute(f.read_text(encoding="utf-8"))
                    cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (f.name,))
            conn.commit()

    def upsert_incident(self, state: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO incidents (incident_id, current_layer, completed_layers, state_json, created_at, updated_at)
                    VALUES (%s, %s, %s::jsonb, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (incident_id) DO UPDATE
                    SET current_layer=EXCLUDED.current_layer,
                        completed_layers=EXCLUDED.completed_layers,
                        state_json=EXCLUDED.state_json,
                        updated_at=NOW()
                    """,
                    (
                        state["incident_id"],
                        state.get("current_layer", "A"),
                        json.dumps(state.get("completed_layers", [])),
                        json.dumps(state),
                    ),
                )
            conn.commit()

    def insert_run(self, incident_id: str, layer: str, status: str, payload: dict[str, Any] | None = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO runs (incident_id, layer, status, payload_json)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (incident_id, layer, status, json.dumps(payload or {})),
                )
            conn.commit()

    def insert_audit(self, incident_id: str, action: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO audit_logs (incident_id, action, payload_json) VALUES (%s, %s, %s::jsonb)",
                    (incident_id, action, json.dumps(payload)),
                )
            conn.commit()

    def replace_records(self, table: str, incident_id: str, rows: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {table} WHERE incident_id=%s", (incident_id,))
                for r in rows:
                    cur.execute(
                        f"INSERT INTO {table} (incident_id, payload_json) VALUES (%s, %s::jsonb)",
                        (incident_id, json.dumps(r)),
                    )
            conn.commit()


def maybe_postgres(migrations_dir: Path) -> PostgresPersistence | None:
    dsn = os.getenv("VECTRION_DATABASE_URL", "").strip()
    if not dsn:
        return None
    return PostgresPersistence(dsn=dsn, migrations_dir=migrations_dir)
