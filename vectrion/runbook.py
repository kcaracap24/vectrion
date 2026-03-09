"""Vectorian Runbook Engine

Drives the 9-stage breach response workflow.
When vault files have been uploaded for an engagement, all stages operate on
real ingested data.  Falls back to static demo data when no vault files exist.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from vectrion.config_store import get_stage_name, get_stage_order
from vectrion.constants import LEGAL_DISCLAIMER
from vectrion.custody import file_sha256
from vectrion.detectors import classify_hits, detect_pii
from vectrion.identity import explain_identity_match, score_identity_match
from vectrion.plugins.defaults import DeterministicExtractor, DraftOnlyNotifier
from vectrion.plugins.secrets import SecretsScanner
from vectrion.redaction import redact_text


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _make_person_key(ssn: str = "", email: str = "", name: str = "",
                     dob: str = "", phone: str = "") -> str | None:
    """
    Deterministic 16-char hex key for a person.  Used for cross-file dedup.
    Priority anchor: SSN > email > name+DOB > name+phone > name alone.
    Returns None when there is no identity signal at all.
    """
    def _norm_ssn(v):   return re.sub(r"[^0-9]", "", v or "")
    def _norm_email(v): return (v or "").lower().strip()
    def _norm_name(v):  return re.sub(r"\s+", " ", (v or "").lower().strip())
    def _norm_phone(v): return re.sub(r"[^0-9]", "", v or "")

    ssn_d   = _norm_ssn(ssn)
    email_d = _norm_email(email)
    name_d  = _norm_name(name)
    dob_d   = (dob or "").strip()
    phone_d = _norm_phone(phone)

    if len(ssn_d) >= 9:
        raw = f"ssn:{ssn_d}"
    elif "@" in email_d:
        raw = f"email:{email_d}"
    elif name_d and dob_d:
        raw = f"name_dob:{name_d}|{dob_d}"
    elif name_d and len(phone_d) >= 10:
        raw = f"name_phone:{name_d}|{phone_d}"
    elif name_d:
        raw = f"name:{name_d}"
    else:
        return None

    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def _load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _manifest(paths: list[Path]) -> list[dict[str, str]]:
    return [{"path": str(p), "sha256": file_sha256(p)} for p in paths if p.exists()]


def _review_pack_html(pack: dict) -> str:
    tl = "".join(
        f"<tr><td>{r.get('timestamp','')}</td><td>{r.get('event','')}</td></tr>"
        for r in pack.get("timeline", [])
    )
    ids = "".join(
        f"<tr><td>{r.get('event_id','')}</td><td>{r.get('score','')}</td>"
        f"<td>{r.get('explain','')}</td></tr>"
        for r in pack.get("identity_scores", [])
    )
    cls_rows = "".join(
        f"<tr><td>{tier}</td><td>{count}</td></tr>"
        for tier, count in pack.get("sensitivity_classification", {}).items()
    )
    aff = "".join(
        f"<tr><td>{p.get('name','')}</td><td>{p.get('email','')}</td>"
        f"<td>{p.get('confidence','')}</td></tr>"
        for p in pack.get("affected_people", [])
    )
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Vectorian Review Pack</title>
<style>
  body{{font-family:Arial,sans-serif;margin:24px;color:#1a1a1a;}}
  h1{{color:#07111D;}} h2{{color:#1D4ED8;border-bottom:2px solid #1D4ED8;padding-bottom:6px;}}
  table{{border-collapse:collapse;width:100%;margin-bottom:20px;}}
  th,td{{border:1px solid #ddd;padding:8px;text-align:left;}}
  th{{background:#f0f4fa;font-weight:700;}}
  .disclaimer{{font-size:11px;color:#666;border-top:1px solid #ddd;padding-top:10px;margin-top:20px;}}
  pre{{background:#f5f5f5;padding:14px;border-radius:6px;white-space:pre-wrap;font-size:12px;}}
</style>
</head><body>
<h1>Vectorian Review Pack — {pack.get('incident',{}).get('incident_id','unknown')}</h1>
<p><strong>Generated:</strong> {pack.get('generated_at','')}</p>

<h2>Incident</h2>
<pre>{json.dumps(pack.get('incident',{}), indent=2)}</pre>

<h2>Data Sensitivity Classification</h2>
<table><tr><th>Tier</th><th>Records</th></tr>{cls_rows}</table>

<h2>Affected Individuals ({len(pack.get('affected_people',[]))})</h2>
<table><tr><th>Name</th><th>Email</th><th>Confidence</th></tr>{aff}</table>

<h2>Timeline</h2>
<table><tr><th>Timestamp</th><th>Event</th></tr>{tl}</table>

<h2>Identity Resolution Scores</h2>
<table><tr><th>Record</th><th>Score</th><th>Match Factors</th></tr>{ids}</table>

<h2>Draft Notification</h2>
<pre>{pack.get('notification_draft','')}</pre>

<p class='disclaimer'>{pack.get('disclaimer','')}</p>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# VAULT LOADING
# ─────────────────────────────────────────────────────────────────────────────

def _load_vault_index(vault_dir: Path) -> list[dict]:
    idx = vault_dir / "_index.json"
    if idx.exists():
        try:
            return json.loads(idx.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _vault_evidence_files(vault_dir: Path, vault_index: list[dict]) -> list[dict]:
    return [
        {
            "path":          str(vault_dir / f["filename"]),
            "sha256":        f.get("sha256", ""),
            "original_name": f.get("original_name", f["filename"]),
            "type_label":    f.get("type_label", ""),
            "method":        f.get("method", ""),
        }
        for f in vault_index
    ]


# ─────────────────────────────────────────────────────────────────────────────
# STAGE MAPPING  numeric id → legacy letter (for internal routing only)
# ─────────────────────────────────────────────────────────────────────────────

_STAGE_TO_LETTER = {
    "1": "A",  # Confirmed Scope Handoff & Data Intake
    "2": "B",  # Data Normalization & Structuring
    "3": "C",  # Sensitive Information Classification
    "4": "D",  # Entity Resolution & Record Consolidation
    "5": "E",  # Impact Quantification & Jurisdictional Mapping
    "6": "F",  # Regulatory Trigger & Legal Determination
    "7": "G",  # Individual Notification Preparation
    "8": "H",  # Regulatory Reporting & Filing Preparation
    "9": "I",  # Public Disclosure & Stakeholder Communication
}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_layer(
    state: dict,
    layer: str,
    data_dir: Path,
    exports_dir: Path,
    vault_dir: Path | None = None,
    engagement_id: str | None = None,
    context: dict | None = None,
) -> dict:
    """
    Execute one stage of the breach response runbook.

    Args:
        state:         The runbook sub-state dict (persisted between stages).
        layer:         Stage ID ("1"–"9" or "custom_*").
        data_dir:      Path to static demo data directory.
        exports_dir:   Path for generated export files.
        vault_dir:     Path to the engagement's vault directory (optional).
        engagement_id: The engagement ID string (optional, for labelling).
        context:       Full engagement state dict including client info (optional).
    """

    # ── Custom stages ────────────────────────────────────────────────────────
    if layer.startswith("custom_"):
        state["last_layer"] = layer
        state["layer_description"] = "Manual step"
        state["status"] = "custom_stage"
        state["note"] = "Custom stage — complete manually and proceed."
        return state

    letter = _STAGE_TO_LETTER.get(layer)
    if letter is None:
        state["last_layer"] = layer
        state["layer_description"] = f"Unknown stage {layer}"
        return state

    # Shared sub-state refs
    incident  = state.setdefault("incident",  {})
    evidence  = state.setdefault("evidence",  [])
    extracted = state.setdefault("extracted", [])

    # Resolve vault availability
    vault_index: list[dict] = []
    if vault_dir and vault_dir.exists():
        vault_index = _load_vault_index(vault_dir)

    # Client metadata (for notification drafts and incident labelling)
    client: dict = {}
    if context:
        client = context.get("client", {})

    # ── Stage A — Confirmed Scope Handoff & Data Intake ───────────────────────
    if letter == "A":
        if vault_index and vault_dir:
            from vectrion.normalizer import normalize_vault, raw_rows_from_vault
            records = normalize_vault(vault_index, vault_dir)

            state["incident"] = {
                "incident_id":     engagement_id or context.get("incident_id", "unknown") if context else "unknown",
                "reporter_name":   client.get("contact_name", ""),
                "reporter_email":  client.get("contact_email", ""),
                "reporter_phone":  client.get("contact_phone", ""),
                "company":         client.get("company_name", ""),
                "industry":        client.get("industry", ""),
                "breach_type":     client.get("breach_type", ""),
                "date_discovered": client.get("date_discovered", ""),
                "summary":         client.get("summary", ""),
            }
            state["evidence"] = records
            state["evidence_files"] = _vault_evidence_files(vault_dir, vault_index)
            state["ingest"] = {
                "source":        "vault",
                "file_count":    len(vault_index),
                "record_count":  len(records),
                "files":         [f.get("original_name") for f in vault_index],
            }

            # ── Bronze write ──────────────────────────────────────────────────
            if engagement_id:
                try:
                    from vectrion.analysis_db import get_db_path, write_bronze_structured, write_bronze_text
                    _workdir = (context or {}).get("workdir", ".vectrion")
                    db_path = get_db_path(_workdir, engagement_id)
                    raw_by_file = raw_rows_from_vault(vault_index, vault_dir)
                    for orig_name, rows in raw_by_file.items():
                        if rows and "_text" in rows[0]:
                            write_bronze_text(db_path, orig_name, [r.get("_text", "") for r in rows])
                        else:
                            write_bronze_structured(db_path, orig_name, rows)
                except Exception:
                    pass
        else:
            # Demo data fallback
            incident_csv = data_dir / "incident.csv"
            ev_csv = data_dir / "evidence.csv"
            incident_row = _load_csv(incident_csv)[0]
            state["incident"] = incident_row
            state["evidence"] = _load_csv(ev_csv)
            state["evidence_files"] = [
                {"path": str(incident_csv), "sha256": file_sha256(incident_csv)},
                {"path": str(ev_csv),       "sha256": file_sha256(ev_csv)},
            ]
            state["ingest"] = {
                "source":         "demo",
                "incident_hash":  file_sha256(incident_csv),
                "evidence_hash":  file_sha256(ev_csv),
            }

    # ── Stage B — Data Normalization & Structuring ───────────────────────────
    elif letter == "B":
        # Extend field map with user-defined aliases before extraction
        field_config = (context or {}).get("field_config", state.get("field_config", {}))
        if field_config.get("user_fields"):
            try:
                from vectrion.normalizer import extend_field_map
                extend_field_map(field_config["user_fields"])
            except Exception:
                pass

        # Build source_file → file_id (sha256) lookup from evidence_files
        _file_id_map: dict[str, str] = {}
        for ef in state.get("evidence_files", []):
            orig = ef.get("original_name", "")
            sha  = ef.get("sha256", "")
            if orig and sha:
                _file_id_map[orig] = sha
                # also index by basename of path in case source_file uses it
                _file_id_map[Path(ef.get("path", orig)).name] = sha

        extractor = DeterministicExtractor()
        extracted_rows = []
        pii_summary = []
        for row in evidence:
            ex = extractor.extract(row)
            # Detect PII on all available text fields concatenated
            full_text = " ".join(filter(None, [
                ex.get("detail", ""), ex.get("name", ""),
                ex.get("email", ""), ex.get("phone", ""),
                ex.get("ssn", ""), ex.get("dob", ""), ex.get("mrn", ""),
            ]))
            ex["detail_redacted"] = redact_text(ex.get("detail", ""))
            hits = detect_pii(full_text, event_id=ex.get("event_id", ""))
            ex["pii_hits"] = [h.__dict__ for h in hits]
            ex["pii_tiers"] = classify_hits(hits)
            pii_summary.extend(ex["pii_hits"])
            # Stamp file_id (sha256 of source file) for traceability
            src = ex.get("source_file", "")
            ex["file_id"] = _file_id_map.get(src) or _file_id_map.get(Path(src).name, "")
            # Stamp person_key for cross-file deduplication
            ex["person_key"] = _make_person_key(
                ssn=ex.get("ssn", ""),
                email=ex.get("email", ""),
                name=ex.get("name", ""),
                dob=ex.get("dob", ""),
                phone=ex.get("phone", ""),
            )
            extracted_rows.append(ex)

        state["extracted"] = extracted_rows
        state["pii_summary"] = pii_summary
        state["normalization_stats"] = {
            "records_processed": len(extracted_rows),
            "total_pii_hits":    len(pii_summary),
            "pii_kinds":         list({h["kind"] for h in pii_summary}),
        }

        # Secrets scan — runs on vault files when available, no-op on demo data
        if vault_dir and vault_dir.exists() and vault_index:
            scanner = SecretsScanner()
            state["secrets_scan"] = scanner.scan_vault(vault_dir, vault_index)
        else:
            state.setdefault("secrets_scan", {
                "findings": [], "files_scanned": [], "total_findings": 0,
                "severity_counts": {}, "critical_count": 0, "high_count": 0,
                "medium_count": 0, "method": "regex",
            })

        # Run additional enabled analysis plugins
        from vectrion.plugins.registry import is_plugin_enabled, _get_scanner_map
        _run_workdir = (context or {}).get("workdir", ".vectrion")
        plugin_results = {}
        if vault_dir and vault_dir.exists() and vault_index:
            for pid, cls in _get_scanner_map(_run_workdir).items():
                if is_plugin_enabled(pid, _run_workdir):
                    plugin_results[pid] = cls().scan_vault(vault_dir, vault_index)
        state["plugin_results"] = plugin_results

        # ── Silver write ──────────────────────────────────────────────────────
        if engagement_id and vault_index:
            try:
                from vectrion.analysis_db import get_db_path, write_silver
                _workdir = (context or {}).get("workdir", ".vectrion")
                db_path = get_db_path(_workdir, engagement_id)
                write_silver(db_path, field_config, extracted_rows)
            except Exception:
                pass

    # ── Stage C — Sensitive Information Classification ───────────────────────
    elif letter == "C":
        from vectrion.normalizer import summarize_records
        summary = summarize_records(extracted)

        # Classify each record into sensitivity tier
        tier_counts: dict[str, int] = {}
        classified: list[dict] = []
        for rec in extracted:
            hits = detect_pii(rec.get("detail", "") or rec.get("raw_text", ""))
            tiers = classify_hits(hits)
            primary_tier = tiers[0] if tiers else "Other"
            tier_counts[primary_tier] = tier_counts.get(primary_tier, 0) + 1
            classified.append({**rec, "sensitivity_tier": primary_tier, "tiers": tiers})

        state["extracted"] = classified
        state["sensitivity_classification"] = {
            **tier_counts,
            "_total": sum(tier_counts.values()),
        }
        state["data_summary"] = summary
        state["applicable_laws"] = _infer_applicable_laws(tier_counts, client)

        # ── Gold write (initial pass) ─────────────────────────────────────────
        if engagement_id:
            try:
                from vectrion.analysis_db import get_db_path, write_gold
                _workdir = (context or {}).get("workdir", ".vectrion")
                write_gold(get_db_path(_workdir, engagement_id), state)
            except Exception:
                pass

    # ── Stage D — Entity Resolution & Record Consolidation ───────────────────
    elif letter == "D":
        # ── Group records by person_key ───────────────────────────────────────
        # person_key was stamped during Stage B extraction.
        # Records without a key (no identity signal) are kept as singletons.
        _TIER_ORDER = {"PHI/PII": 0, "PII": 1, "PHI": 2, "PCI": 3, "Financial": 4,
                       "Credentials": 5, "Other": 99}

        groups: dict[str, list[dict]] = {}   # person_key → [records]
        no_key_records: list[dict] = []

        for row in extracted:
            pk = row.get("person_key") or _make_person_key(
                ssn=row.get("ssn", ""), email=row.get("email", ""),
                name=row.get("name", ""), dob=row.get("dob", ""),
                phone=row.get("phone", ""),
            )
            if pk:
                groups.setdefault(pk, []).append(row)
            else:
                no_key_records.append(row)

        # ── Merge each group into a single canonical person record ────────────
        def _best(vals):
            """Return first non-empty value from a list."""
            return next((v for v in vals if v), "")

        affected_people: list[dict] = []

        for pk, recs in groups.items():
            src_files = list(dict.fromkeys(r.get("source_file", "") for r in recs if r.get("source_file")))
            file_ids  = list(dict.fromkeys(r.get("file_id", "")    for r in recs if r.get("file_id")))
            pii_types = sorted({pt for r in recs for pt in (r.get("pii_types") or [])})
            tiers     = [r.get("sensitivity_tier", "Other") for r in recs]
            best_tier = min(tiers, key=lambda t: _TIER_ORDER.get(t, 99))
            affected_people.append({
                "person_key":    pk,
                "record_id":     _best([r.get("event_id") or r.get("record_id", "") for r in recs]),
                "name":          _best([r.get("name", "") for r in recs]),
                "email":         _best([r.get("email", "") for r in recs]),
                "phone":         _best([r.get("phone", "") for r in recs]),
                "ssn":           "[PRESENT]" if any(r.get("ssn") for r in recs) else "",
                "dob":           "[PRESENT]" if any(r.get("dob") for r in recs) else "",
                "mrn":           "[PRESENT]" if any(r.get("mrn") for r in recs) else "",
                "cc":            "[PRESENT]" if any(r.get("cc") for r in recs) else "",
                "account":       "[PRESENT]" if any(r.get("account") for r in recs) else "",
                "source_files":  src_files,
                "file_ids":      file_ids,
                "record_count":  len(recs),
                "cross_file":    len(src_files) > 1,
                "pii_types":     pii_types,
                "sensitivity_tier": best_tier,
                "confidence":    "high" if any(r.get("ssn") for r in recs) else
                                 "medium" if any(r.get("email") for r in recs) else "low",
            })

        # Singletons: records with no identity anchor (keep them, mark unknown)
        for row in no_key_records:
            has_id = bool(row.get("email") or row.get("ssn") or row.get("phone") or row.get("name"))
            if has_id:
                affected_people.append({
                    "person_key":    None,
                    "record_id":     row.get("event_id") or row.get("record_id", ""),
                    "name":          row.get("name", ""),
                    "email":         row.get("email", ""),
                    "phone":         row.get("phone", ""),
                    "ssn":           "[PRESENT]" if row.get("ssn") else "",
                    "dob":           "[PRESENT]" if row.get("dob") else "",
                    "mrn":           "[PRESENT]" if row.get("mrn") else "",
                    "cc":            "[PRESENT]" if row.get("cc") else "",
                    "account":       "[PRESENT]" if row.get("account") else "",
                    "source_files":  [row.get("source_file", "")],
                    "file_ids":      [row.get("file_id", "")],
                    "record_count":  1,
                    "cross_file":    False,
                    "pii_types":     list(row.get("pii_types") or []),
                    "sensitivity_tier": row.get("sensitivity_tier", "Other"),
                    "confidence":    "low",
                })

        cross_file_count = sum(1 for p in affected_people if p.get("cross_file"))
        duplicate_records = sum(p["record_count"] - 1 for p in affected_people if p.get("person_key"))

        state["affected_people"] = affected_people
        state["entity_resolution"] = {
            "total_records":          len(extracted),
            "unique_affected_people": len(affected_people),
            "cross_file_matches":     cross_file_count,
            "duplicate_records_merged": duplicate_records,
            "records_without_identity": len(no_key_records),
            "dedup_method":           "person_key",
        }
        # Keep identity_scores for backward compat (summary only, not per-record)
        state["identity_scores"] = []

        # ── Gold write (with affected_people populated) ───────────────────────
        if engagement_id:
            try:
                from vectrion.analysis_db import get_db_path, write_gold
                _workdir = (context or {}).get("workdir", ".vectrion")
                write_gold(get_db_path(_workdir, engagement_id), state)
            except Exception:
                pass

    # ── Stage E — Impact Quantification & Jurisdictional Mapping ────────────
    elif letter == "E":
        affected = state.get("affected_people", [])
        sensitivity = state.get("sensitivity_classification", {})
        timeline = [
            {"timestamp": r.get("timestamp", ""), "event": r.get("subject", "") or r.get("source_file", "")}
            for r in extracted
            if r.get("timestamp") or r.get("subject")
        ]
        state["timeline"] = timeline
        state["impact_summary"] = {
            "affected_count":         len(affected),
            "affected_with_ssn":      sum(1 for p in affected if p.get("ssn")),
            "affected_with_health":   sum(1 for p in affected if p.get("mrn") or p.get("dob")),
            "affected_with_financial":sum(1 for r in extracted if r.get("cc") or r.get("account")),
            "sensitivity_breakdown":  {k: v for k, v in sensitivity.items() if not k.startswith("_")},
            "jurisdictions":          client.get("jurisdictions", "Unknown"),
            "estimated_regulatory_exposure": _estimate_exposure(len(affected), sensitivity),
        }
        state["chain_of_custody"] = {
            "engagement_id":  engagement_id or "unknown",
            "evidence_files": state.get("evidence_files", []),
            "stage_hashes":   {},
        }

    # ── Stage F — Regulatory Trigger & Legal Determination ──────────────────
    elif letter == "F":
        affected_count = len(state.get("affected_people", []))
        sensitivity = state.get("sensitivity_classification", {})
        applicable = state.get("applicable_laws", _infer_applicable_laws(sensitivity, client))
        triggers = []
        for law, details in applicable.items():
            triggers.append({
                "law":              law,
                "triggered":        details.get("triggered", False),
                "threshold":        details.get("threshold", ""),
                "deadline":         details.get("deadline", ""),
                "filing_required":  details.get("filing_required", False),
                "notes":            details.get("notes", ""),
            })
        state["regulatory_triggers"] = triggers
        state["notification_required"] = any(t["triggered"] for t in triggers)
        state["legal_determination"] = {
            "affected_count":     affected_count,
            "notification_required": state["notification_required"],
            "triggered_laws":     [t["law"] for t in triggers if t["triggered"]],
            "earliest_deadline":  _earliest_deadline(triggers),
            "note": "This determination requires review by qualified legal counsel.",
        }

    # ── Stage G — Individual Notification Preparation ────────────────────────
    elif letter == "G":
        notifier = DraftOnlyNotifier()
        incident_meta = {
            **incident,
            "affected_count": len(state.get("affected_people", [])),
            "jurisdictions":  client.get("jurisdictions", ""),
            "regulations":    client.get("regulations", []),
            "breach_type":    client.get("breach_type", ""),
        }
        draft = notifier.draft(incident_meta)
        state["notification_draft"] = draft
        state["notification_sent"] = False
        state["notification_queue"] = [
            {
                "recipient_id": p.get("record_id", ""),
                "name":         p.get("name", "[unknown]"),
                "email":        p.get("email", ""),
                "status":       "queued_for_review",
                "draft":        "See notification_draft field — requires customization per recipient.",
            }
            for p in state.get("affected_people", [])[:100]  # cap preview at 100
        ]

    # ── Stage H — Regulatory Reporting & Filing Preparation ──────────────────
    elif letter == "H":
        from datetime import datetime
        iid = incident.get("incident_id", engagement_id or "unknown")
        pack = {
            "incident":                    incident,
            "timeline":                    state.get("timeline", []),
            "impact_summary":              state.get("impact_summary", {}),
            "sensitivity_classification":  state.get("sensitivity_classification", {}),
            "identity_scores":             state.get("identity_scores", []),
            "affected_people":             state.get("affected_people", []),
            "regulatory_triggers":         state.get("regulatory_triggers", []),
            "legal_determination":         state.get("legal_determination", {}),
            "notification_draft":          state.get("notification_draft", ""),
            "disclaimer":                  LEGAL_DISCLAIMER,
            "generated_at":                datetime.utcnow().isoformat() + "Z",
        }
        json_out     = exports_dir / f"review-pack-{iid}.json"
        html_out     = exports_dir / f"review-pack-{iid}.html"
        manifest_out = exports_dir / f"review-pack-{iid}.manifest.json"
        exports_dir.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
        html_out.write_text(_review_pack_html(pack), encoding="utf-8")
        manifest = {
            "incident_id":   iid,
            "artifacts":     _manifest([json_out, html_out]),
            "note":          "HTML artifact is print-to-PDF friendly via browser.",
        }
        manifest_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        state["review_pack_path"]     = str(json_out)
        state["review_pack_html_path"] = str(html_out)
        state["review_pack_manifest"]  = str(manifest_out)

    # ── Stage I — Public Disclosure & Stakeholder Communication ──────────────
    elif letter == "I":
        state["status"] = "awaiting_final_approval"
        state["disclosure_checklist"] = [
            {"item": "Press release draft reviewed by legal",           "complete": False},
            {"item": "Website notice published",                        "complete": False},
            {"item": "Regulatory filings submitted",                    "complete": False},
            {"item": "All individual notifications sent",               "complete": False},
            {"item": "Investor/board communications issued",            "complete": False},
            {"item": "Internal staff notification sent",                "complete": False},
            {"item": "Breach response hotline activated",               "complete": False},
            {"item": "Post-incident review scheduled",                  "complete": False},
        ]
        state["final_note"] = (
            "Final stage reached. All checklist items require human confirmation "
            "before this engagement can be closed. " + LEGAL_DISCLAIMER
        )

    state["last_layer"]        = layer
    state["layer_description"] = get_stage_name(layer)
    return state


# ─────────────────────────────────────────────────────────────────────────────
# STAGE NAVIGATION
# ─────────────────────────────────────────────────────────────────────────────

def next_layer(current: str, workdir: str = ".vectrion") -> str | None:
    order = get_stage_order(workdir)
    try:
        idx = order.index(current)
    except ValueError:
        return None
    return order[idx + 1] if idx + 1 < len(order) else None


# ─────────────────────────────────────────────────────────────────────────────
# REGULATORY ANALYSIS HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _infer_applicable_laws(sensitivity: dict, client: dict) -> dict:
    """Infer applicable breach notification laws from detected data types and client profile."""
    regs = client.get("regulations", [])
    if isinstance(regs, str):
        regs = [regs]
    regs_set = {r.upper() for r in regs}

    laws: dict[str, dict] = {}

    has_phi = sensitivity.get("PHI", 0) > 0 or sensitivity.get("PHI/PII", 0) > 0
    has_pci = sensitivity.get("PCI", 0) > 0
    has_pii = (sensitivity.get("PII", 0) + sensitivity.get("PHI/PII", 0)) > 0
    has_eu  = "GDPR" in regs_set or "EU" in str(client.get("jurisdictions", "")).upper()
    has_ca  = "CALIFORNIA" in str(client.get("jurisdictions", "")).upper() or "CCPA" in regs_set

    if has_phi or "HIPAA" in regs_set:
        laws["HIPAA"] = {
            "triggered":       True,
            "threshold":       "Any PHI access by unauthorized party",
            "deadline":        "60 days from discovery (individual); annual report if <500/state",
            "filing_required": True,
            "notes":           "OCR breach notification required if 500+ affected in any state.",
        }
    if has_eu:
        laws["GDPR"] = {
            "triggered":       True,
            "threshold":       "Any personal data breach",
            "deadline":        "72 hours to supervisory authority",
            "filing_required": True,
            "notes":           "Article 33/34 — notify DPA within 72h; notify individuals without undue delay.",
        }
    if has_ca:
        laws["CCPA/CPRA"] = {
            "triggered":       has_pii,
            "threshold":       "Unauthorized access to California residents' personal information",
            "deadline":        "Most expedient time; no more than 30 days recommended",
            "filing_required": False,
            "notes":           "AG notification if 500+ Californians affected.",
        }
    if has_pci:
        laws["PCI-DSS"] = {
            "triggered":       True,
            "threshold":       "Any cardholder data compromise",
            "deadline":        "Immediate notification to card brands and acquiring bank",
            "filing_required": True,
            "notes":           "Contact Visa/MC/Amex/Discover within 24h of confirmed compromise.",
        }
    if has_pii and not laws:
        laws["State Breach Laws (US)"] = {
            "triggered":       True,
            "threshold":       "Varies by state (typically 500 or 1 resident)",
            "deadline":        "30–90 days depending on state (varies)",
            "filing_required": False,
            "notes":           "All 50 states have breach notification laws. Review each applicable state.",
        }
    return laws


def _earliest_deadline(triggers: list[dict]) -> str:
    deadlines_priority = ["72 hours", "24h", "30 days", "45 days", "60 days", "90 days"]
    found = set(t.get("deadline", "") for t in triggers if t.get("triggered"))
    for d in deadlines_priority:
        if any(d.lower() in f.lower() for f in found):
            return d
    return "Review applicable deadlines with legal counsel"


def _estimate_exposure(affected_count: int, sensitivity: dict) -> str:
    if not affected_count:
        return "Insufficient data"
    phi = sensitivity.get("PHI", 0) + sensitivity.get("PHI/PII", 0)
    pci = sensitivity.get("PCI", 0)
    base = affected_count * 150  # HIPAA average settlement per record
    if phi > 0:
        base = max(base, phi * 200)
    if pci > 0:
        base = max(base, pci * 100)
    if base < 10_000:
        return f"Est. < $10,000 (limited scope)"
    if base < 1_000_000:
        return f"Est. ${base:,.0f} (moderate exposure)"
    return f"Est. ${base:,.0f}+ (significant — engage legal counsel immediately)"
