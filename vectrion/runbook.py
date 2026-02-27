from __future__ import annotations

import csv
import json
from pathlib import Path

from vectrion.config_store import get_stage_name, get_stage_order
from vectrion.constants import LEGAL_DISCLAIMER
from vectrion.custody import file_sha256
from vectrion.detectors import detect_pii
from vectrion.identity import explain_identity_match, score_identity_match
from vectrion.plugins.defaults import DeterministicExtractor, DraftOnlyNotifier
from vectrion.redaction import redact_text


def _load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _review_pack_html(pack: dict) -> str:
    tl = "".join(
        f"<tr><td>{r.get('timestamp','')}</td><td>{r.get('event','')}</td></tr>" for r in pack.get("timeline", [])
    )
    ids = "".join(
        f"<tr><td>{r.get('event_id','')}</td><td>{r.get('score','')}</td><td>{r.get('explain','')}</td></tr>"
        for r in pack.get("identity_scores", [])
    )
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Vectorian Review Pack</title>
<style>body{{font-family:Arial,sans-serif;margin:24px}} table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #ddd;padding:8px}} th{{background:#f7f7f7}}</style>
</head><body>
<h1>Incident {pack.get('incident',{}).get('incident_id','unknown')}</h1>
<p><strong>Disclaimer:</strong> {pack.get('disclaimer','')}</p>
<h2>Timeline</h2><table><tr><th>Timestamp</th><th>Event</th></tr>{tl}</table>
<h2>Identity Resolution</h2><table><tr><th>Event</th><th>Score</th><th>Explainability</th></tr>{ids}</table>
<h2>Draft Notification</h2><pre>{pack.get('notification_draft','')}</pre>
</body></html>"""


def _manifest(paths: list[Path]) -> list[dict[str, str]]:
    return [{"path": str(p), "sha256": file_sha256(p)} for p in paths if p.exists()]


# Map stage IDs "1"-"9" to legacy runbook letter keys
_STAGE_TO_LAYER = {
    "1": "A",
    "2": "B",
    "3": "C",
    "4": "D",
    "5": "D",   # timeline/custody — same underlying logic as D
    "6": "E",   # regulatory analysis → draft/notification logic
    "7": "E",
    "8": "G",
    "9": "H",
}


def run_layer(state: dict, layer: str, data_dir: Path, exports_dir: Path) -> dict:
    # Custom stages return a placeholder
    if layer.startswith("custom_"):
        state["last_layer"] = layer
        state["layer_description"] = "Manual step"
        state["status"] = "custom_stage"
        state["note"] = "This is a custom stage. Complete manually and proceed."
        return state

    letter = _STAGE_TO_LAYER.get(layer)
    if letter is None:
        state["last_layer"] = layer
        state["layer_description"] = f"Unknown stage {layer}"
        return state

    incident = state.setdefault("incident", {})
    evidence = state.setdefault("evidence", [])
    extracted = state.setdefault("extracted", [])

    if letter == "A":
        incident_csv = data_dir / "incident.csv"
        ev_csv = data_dir / "evidence.csv"
        incident_row = _load_csv(incident_csv)[0]
        state["incident"] = incident_row
        state["evidence"] = _load_csv(ev_csv)
        state["evidence_files"] = [
            {"path": str(incident_csv), "sha256": file_sha256(incident_csv)},
            {"path": str(ev_csv), "sha256": file_sha256(ev_csv)},
        ]
        state["ingest"] = {
            "incident_hash": file_sha256(incident_csv),
            "evidence_hash": file_sha256(ev_csv),
        }

    elif letter == "B":
        extractor = DeterministicExtractor()
        extracted_rows = []
        pii_summary = []
        for row in evidence:
            ex = extractor.extract(row)
            ex["detail_redacted"] = redact_text(ex.get("detail", ""))
            hits = [h.__dict__ for h in detect_pii(ex.get("detail", ""), event_id=ex.get("event_id", ""))]
            ex["pii_hits"] = hits
            pii_summary.extend(hits)
            extracted_rows.append(ex)
        state["extracted"] = extracted_rows
        state["pii_summary"] = pii_summary

    elif letter == "C":
        incident_identity = {
            "name": incident.get("reporter_name", ""),
            "email": incident.get("reporter_email", ""),
            "phone": incident.get("reporter_phone", ""),
        }
        scores = []
        affected_people = []
        for row in extracted:
            explain = explain_identity_match(incident_identity, row)
            score = score_identity_match(incident_identity, row)
            scores.append(
                {
                    "event_id": row.get("event_id"),
                    "score": score,
                    "confidence": explain["confidence"],
                    "factors": explain["factors"],
                    "explain": explain["summary"],
                }
            )
            if score >= 0.6:
                affected_people.append(
                    {
                        "event_id": row.get("event_id"),
                        "name": row.get("name") or incident_identity.get("name", ""),
                        "email": row.get("email", ""),
                        "phone": row.get("phone", ""),
                        "confidence": explain["confidence"],
                    }
                )
        state["identity_scores"] = scores
        state["affected_people"] = affected_people

    elif letter == "D":
        state["timeline"] = [
            {"timestamp": r.get("timestamp", ""), "event": r.get("subject", "")} for r in extracted
        ]
        state["chain_of_custody"] = {
            "files": state.get("ingest", {}),
            "records": [
                {"event_id": r.get("event_id"), "row_hash": file_sha256((data_dir / "evidence.csv"))}
                for r in extracted[:3]
            ],
        }

    elif letter == "E":
        notifier = DraftOnlyNotifier()
        draft = notifier.draft({"incident_id": incident.get("incident_id", "unknown")})
        state["notification_draft"] = draft
        state["notification_sent"] = False

    elif letter == "G":
        incident_id = incident.get("incident_id", "unknown")
        pack = {
            "incident": incident,
            "timeline": state.get("timeline", []),
            "identity_scores": state.get("identity_scores", []),
            "notification_draft": state.get("notification_draft", ""),
            "disclaimer": LEGAL_DISCLAIMER,
        }
        json_out = exports_dir / f"review-pack-{incident_id}.json"
        html_out = exports_dir / f"review-pack-{incident_id}.html"
        manifest_out = exports_dir / f"review-pack-{incident_id}.manifest.json"
        exports_dir.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
        html_out.write_text(_review_pack_html(pack), encoding="utf-8")
        manifest = {
            "incident_id": incident_id,
            "artifacts": _manifest([json_out, html_out]),
            "note": "HTML artifact is PDF-print friendly from browser print dialog",
        }
        manifest_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        state["review_pack_path"] = str(json_out)
        state["review_pack_html_path"] = str(html_out)
        state["review_pack_manifest"] = str(manifest_out)

    elif letter == "H":
        state["status"] = "awaiting_human_approval"
        state["final_note"] = LEGAL_DISCLAIMER

    state["last_layer"] = layer
    state["layer_description"] = get_stage_name(layer)
    return state


def next_layer(current: str, workdir: str = ".vectrion") -> str | None:
    order = get_stage_order(workdir)
    try:
        idx = order.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(order):
        return None
    return order[idx + 1]
