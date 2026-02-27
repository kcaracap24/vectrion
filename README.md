# Vectrion MVP

Interactive Breach Response Agent (MVP) with deterministic-first extraction, layer-gated runbook, audit logs, review-pack export, and draft-only notifications.

> LEGAL DISCLAIMER: This output is a draft for internal incident response review only. It may contain inaccuracies and must be validated by authorized legal, compliance, and security personnel. Do not treat as legal advice.

## Features
- Layer-gated runbook for A/B/C/D/E/G/H
- Audit logs (JSONL) per incident (+ optional Postgres `audit_logs`)
- Deterministic-first extraction plugin
- Deterministic PII detection + confidence + evidence refs + redaction
- Identity resolution scoring with explainability factors
- Chain-of-custody SHA-256 hashing + review-pack manifest hashes
- Review-pack export (JSON + HTML print-to-PDF friendly)
- VQL parser/executor (SELECT/STATS/FIND + GROUP BY + EXCLUDE)
- HTTP endpoints: trigger/status/proceed
- Policy: **never auto-send notifications** (draft only)

## Memory Budget Notes (<1GB VM)
- Minimal Python deps (`flask`, `pytest` for dev only)
- Postgres + Redis compose limits tuned (`mem_limit`)
- No heavy ML runtime

## Quickstart
```bash
cd vectrion
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
```

## CLI Runbook
```bash
vectrion --workdir .vectrion migrate
vectrion --workdir .vectrion start INC-2026-0001
vectrion --workdir .vectrion proceed INC-2026-0001 --layer A
vectrion --workdir .vectrion proceed INC-2026-0001 --layer B
vectrion --workdir .vectrion proceed INC-2026-0001 --layer C
vectrion --workdir .vectrion proceed INC-2026-0001 --layer D
vectrion --workdir .vectrion proceed INC-2026-0001 --layer E
vectrion --workdir .vectrion proceed INC-2026-0001 --layer G
vectrion --workdir .vectrion proceed INC-2026-0001 --layer H
vectrion --workdir .vectrion status INC-2026-0001
```

Interactive mode:
```bash
vectrion --workdir .vectrion interactive INC-2026-0001
# commands: proceed | rerun | add-detector <name> | add-transform <name> | split-cohort <field> | status
```

## HTTP API
```bash
vectrion-http
# POST /trigger {"incident_id":"INC-2026-0002"}
# GET /status/INC-2026-0002
# POST /proceed/INC-2026-0002 {"layer":"A"}
```

## Non-Technical UI (Operator Console)
Simple browser UI for incident creation + one-click layer progression.

```bash
vectrion-ui
# open http://localhost:8090
```

## VQL
Supported forms:
- `SELECT field1,field2 FROM evidence WHERE source='vpn' LIMIT 10`
- `SELECT * FROM evidence WHERE detail~'MFA' EXCLUDE source='mail'`
- `SELECT * FROM evidence GROUP BY source`
- `STATS COUNT BY source FROM evidence`
- `FIND 'vpn' IN evidence EXCLUDE source='mail' GROUP BY source`

```bash
vectrion-vql "SELECT event_id,subject FROM evidence WHERE source='vpn' LIMIT 2"
```

## Postgres persistence (optional)
```bash
pip install -e .[postgres]
export VECTRION_DATABASE_URL='postgresql://vectrion:vectrion@localhost:5432/vectrion'
vectrion --workdir .vectrion migrate
```
Core entities persisted: incidents, runs, evidence_files, normalized_records, pii_findings, identity_links, affected_people, drafts, audit_logs.

## Docker Compose (postgres + redis)
```bash
docker compose up -d
```

## Demo Script
```bash
./scripts/demo_run.sh
```

## Tests
```bash
pytest -q
```
