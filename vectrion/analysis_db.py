"""Vectrion Medallion Architecture — Bronze / Silver / Gold SQLite persistence.

Writes a persistent per-engagement analysis.db file with three layers:
  Bronze — raw source columns, one table per uploaded file
  Silver — dynamic wide table: user-defined + preset + auto-discovered columns
  Gold   — fixed business aggregation views (affected people, risk, exposure)
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

DB_FILENAME = "analysis.db"

PRESET_COLUMNS: dict[str, list[str]] = {
    "identity":    ["name", "email", "phone", "address", "dob", "ssn", "passport", "drivers_license"],
    "financial":   ["account", "routing", "cc", "iban", "salary"],
    "medical":     ["mrn", "diagnosis", "insurance_id", "provider"],
    "credentials": ["username", "password", "password_hash"],
    "network":     ["ip", "mac"],
}

# ── HELPERS ──────────────────────────────────────────────────────────────────

def get_db_path(workdir: str, engagement_id: str) -> Path:
    """Returns Path to analysis.db inside the engagement's upload directory."""
    return Path(workdir) / "uploads" / engagement_id / DB_FILENAME


def _bronze_table_name(source_file: str) -> str:
    """'employees_2024.csv' → 'bronze_employees_2024_csv'"""
    safe = re.sub(r"[^a-zA-Z0-9]", "_", Path(source_file).name)
    return f"bronze_{safe}"


def _col_list(cols: list[str]) -> str:
    return ", ".join(f'"{c}"' for c in cols)


def _placeholder(cols: list[str]) -> str:
    return ", ".join("?" for _ in cols)


def _ensure_registry(c: sqlite3.Cursor) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS _bronze_registry (
            table_name   TEXT PRIMARY KEY,
            source_file  TEXT,
            row_count    INTEGER,
            columns_json TEXT
        )
    """)


# ── BRONZE ───────────────────────────────────────────────────────────────────

def write_bronze_structured(db_path: Path, source_file: str, raw_rows: list[dict]) -> int:
    """
    Create/replace bronze_<filename> table with exact columns from source data.
    No _FIELD_MAP normalization.  Stores raw column names and values as-is.
    Returns row count written.
    """
    if not raw_rows:
        return 0
    db_path.parent.mkdir(parents=True, exist_ok=True)
    table = _bronze_table_name(source_file)

    # Collect all column names across all rows (preserving insertion order)
    seen: dict[str, None] = {}
    for row in raw_rows:
        for k in row.keys():
            seen[k] = None
    all_cols = list(seen.keys())
    internal_cols = ["_row_num"] + all_cols

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute(f'DROP TABLE IF EXISTS "{table}"')
    col_defs = ", ".join(f'"{col}" TEXT' for col in internal_cols)
    c.execute(f'CREATE TABLE "{table}" ({col_defs})')

    for i, row in enumerate(raw_rows):
        vals = [str(i)] + [str(row.get(col) or "") for col in all_cols]
        c.execute(
            f'INSERT INTO "{table}" VALUES ({_placeholder(internal_cols)})',
            vals,
        )

    _ensure_registry(c)
    c.execute(
        "INSERT OR REPLACE INTO _bronze_registry "
        "(table_name, source_file, row_count, columns_json) VALUES (?,?,?,?)",
        (table, source_file, len(raw_rows), json.dumps(all_cols)),
    )
    conn.commit()
    conn.close()
    return len(raw_rows)


def write_bronze_text(db_path: Path, source_file: str, chunks: list[str]) -> int:
    """Create bronze_<filename> for unstructured files.
    Columns: _row_num, _chunk_num, _text, _char_count."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    table = _bronze_table_name(source_file)
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute(f'DROP TABLE IF EXISTS "{table}"')
    c.execute(
        f'CREATE TABLE "{table}" '
        '(_row_num TEXT, _chunk_num TEXT, _text TEXT, _char_count TEXT)'
    )
    for i, chunk in enumerate(chunks):
        c.execute(
            f'INSERT INTO "{table}" VALUES (?,?,?,?)',
            (str(i), str(i), chunk, str(len(chunk))),
        )
    _ensure_registry(c)
    c.execute(
        "INSERT OR REPLACE INTO _bronze_registry "
        "(table_name, source_file, row_count, columns_json) VALUES (?,?,?,?)",
        (table, source_file, len(chunks),
         json.dumps(["_chunk_num", "_text", "_char_count"])),
    )
    conn.commit()
    conn.close()
    return len(chunks)


def get_bronze_schema(db_path: Path) -> dict[str, list[str]]:
    """Return {table_name: [column_names]} for all bronze_ tables."""
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'bronze_%'"
        ).fetchall()
        schema: dict[str, list[str]] = {}
        for (tbl,) in tables:
            if tbl == "_bronze_registry":
                continue
            cols = [row[1] for row in conn.execute(f'PRAGMA table_info("{tbl}")').fetchall()]
            schema[tbl] = cols
        return schema
    finally:
        conn.close()


# ── SILVER ───────────────────────────────────────────────────────────────────

def _build_silver_columns(db_path: Path, field_config: dict) -> list[str]:
    """
    Returns ordered list of column names for silver table.
    1. User-defined custom fields (from field_config["user_fields"])
    2. Standard preset columns based on enabled presets
    3. Auto-discovered: all bronze data columns not yet included
    """
    # 1. User-defined
    user_cols: list[str] = []
    for f in field_config.get("user_fields", []):
        name = (f.get("name") or "").strip()
        if name and name not in user_cols:
            user_cols.append(name)

    # 2. Presets
    enabled = field_config.get("presets", list(PRESET_COLUMNS.keys()))
    preset_cols: list[str] = []
    for preset in enabled:
        for col in PRESET_COLUMNS.get(preset, []):
            if col not in user_cols and col not in preset_cols:
                preset_cols.append(col)

    # 3. Auto-discovered bronze columns
    auto_cols: list[str] = []
    if field_config.get("auto_discover", True) and db_path.exists():
        already = set(user_cols + preset_cols)
        bronze_schema = get_bronze_schema(db_path)
        for tbl_cols in bronze_schema.values():
            for col in tbl_cols:
                if col.startswith("_"):
                    continue
                if col not in already and col not in auto_cols:
                    auto_cols.append(col)

    return user_cols + preset_cols + auto_cols


def _classify_entity_type(row: dict) -> str:
    if row.get("ssn") or row.get("dob") or row.get("mrn") or row.get("name") or row.get("email"):
        return "person"
    if row.get("cc") or row.get("account") or row.get("routing"):
        return "financial"
    if row.get("username") or row.get("password"):
        return "credential"
    return "other"


def _classify_sensitivity(row: dict) -> str:
    if row.get("ssn") or row.get("cc") or row.get("mrn") or row.get("passport"):
        return "critical"
    if row.get("dob") or row.get("account") or row.get("routing") or row.get("insurance_id"):
        return "high"
    if row.get("email") or row.get("phone") or row.get("name"):
        return "medium"
    return "low"


def write_silver(db_path: Path, field_config: dict, extracted_rows: list[dict]) -> None:
    """
    Build silver table from already-normalized runbook extracted rows.
    Columns = user_fields + preset_columns + all_discovered_bronze_columns.
    All values stored as-is (including SSN, CC#).
    Also writes _silver_schema: (field_name, source, sensitivity, populated_count).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    data_cols = _build_silver_columns(db_path, field_config)

    # Load bronze rows for auto-discovered column value lookup
    # {table_name: {row_num_int: {col: val}}}
    bronze_data: dict[str, dict[int, dict]] = {}
    if db_path.exists():
        try:
            conn_ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                tbls = conn_ro.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name LIKE 'bronze_%' "
                    "AND name != '_bronze_registry'"
                ).fetchall()
                for (tbl,) in tbls:
                    tbl_col_names = [
                        row[1]
                        for row in conn_ro.execute(f'PRAGMA table_info("{tbl}")').fetchall()
                    ]
                    all_rows = conn_ro.execute(f'SELECT * FROM "{tbl}"').fetchall()
                    bronze_data[tbl] = {}
                    for db_row in all_rows:
                        row_dict = dict(zip(tbl_col_names, db_row))
                        rn = row_dict.get("_row_num")
                        if rn is not None:
                            try:
                                bronze_data[tbl][int(rn)] = row_dict
                            except (ValueError, TypeError):
                                pass
            finally:
                conn_ro.close()
        except Exception:
            pass

    # Build silver rows
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS silver")

    meta_cols = [
        "_source_table", "_source_row", "_entity_type",
        "_sensitivity_tier", "_source_file",
    ]
    all_cols = meta_cols + data_cols
    col_defs = (
        '"_id" INTEGER PRIMARY KEY, '
        + ", ".join(f'"{col}" TEXT' for col in all_cols)
    )
    c.execute(f"CREATE TABLE silver ({col_defs})")

    user_fields_map: dict[str, list[str]] = {
        f.get("name", ""): f.get("search_terms", [])
        for f in field_config.get("user_fields", [])
        if f.get("name")
    }

    for idx, row in enumerate(extracted_rows):
        src_file = row.get("source_file", "")
        tbl_name = _bronze_table_name(src_file) if src_file else ""

        # Parse row_num from record_id
        record_id = row.get("event_id") or row.get("record_id", "")
        row_num: int | None = None
        if ":row:" in record_id:
            try:
                row_num = int(record_id.split(":row:", 1)[1])
            except (ValueError, IndexError):
                pass

        # Fetch matching bronze row for auto-discovered column values
        bronze_row: dict = {}
        if tbl_name and row_num is not None:
            bronze_row = bronze_data.get(tbl_name, {}).get(row_num, {})

        entity_type = _classify_entity_type(row)
        sensitivity = row.get("sensitivity_tier") or _classify_sensitivity(row)

        row_vals: dict[str, str] = {
            "_source_table":    tbl_name,
            "_source_row":      str(row_num) if row_num is not None else "",
            "_entity_type":     entity_type,
            "_sensitivity_tier": sensitivity,
            "_source_file":     src_file,
        }

        for col in data_cols:
            if col in row_vals:
                continue

            val = ""
            # Check if it's a user-defined field with aliases
            if col in user_fields_map:
                val = str(row.get(col) or "")
                if not val:
                    for term in user_fields_map[col]:
                        val = str(bronze_row.get(term) or "")
                        if val:
                            break
            elif col in row:
                raw = row[col]
                if isinstance(raw, list):
                    val = json.dumps(raw)
                else:
                    val = str(raw) if raw else ""
            elif col in bronze_row:
                val = str(bronze_row[col]) if bronze_row[col] else ""

            row_vals[col] = val

        insert_cols = all_cols
        vals = [row_vals.get(col, "") for col in insert_cols]
        c.execute(
            f'INSERT INTO silver ("_id", {_col_list(insert_cols)}) '
            f'VALUES (?, {_placeholder(insert_cols)})',
            [idx] + vals,
        )

    # Write _silver_schema
    c.execute("DROP TABLE IF EXISTS _silver_schema")
    c.execute("""
        CREATE TABLE _silver_schema (
            field_name       TEXT PRIMARY KEY,
            source           TEXT,
            sensitivity      TEXT,
            populated_count  INTEGER
        )
    """)

    user_names = set(f.get("name", "") for f in field_config.get("user_fields", []))
    preset_names: set[str] = set()
    for cols in PRESET_COLUMNS.values():
        preset_names.update(cols)
    high_sens = {"ssn", "cc", "mrn", "passport", "password", "password_hash"}

    for col in data_cols:
        if col.startswith("_"):
            continue
        try:
            count = c.execute(
                f'SELECT COUNT(*) FROM silver WHERE "{col}" IS NOT NULL AND "{col}" != ""'
            ).fetchone()[0]
        except Exception:
            count = 0

        if col in user_names:
            source = "user_defined"
        elif col in preset_names:
            source = "preset"
        else:
            source = "auto_discovered"

        sens = "high" if col in high_sens else "medium"
        c.execute(
            "INSERT OR REPLACE INTO _silver_schema VALUES (?,?,?,?)",
            (col, source, sens, count),
        )

    conn.commit()
    conn.close()


# ── GOLD ─────────────────────────────────────────────────────────────────────

def write_gold(db_path: Path, runbook: dict) -> None:
    """
    Build gold tables from runbook state (populated by stages 3+).
    - gold_affected_people  — one row per unique affected person
    - gold_pii_by_field     — COUNT per field type in silver
    - gold_file_risk        — per bronze table total/sensitive rows
    - gold_exposure_summary — single-row aggregate
    """
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # ── gold_affected_people ──────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS gold_affected_people")
    c.execute("""
        CREATE TABLE gold_affected_people (
            record_id      TEXT,
            name           TEXT,
            email          TEXT,
            phone          TEXT,
            ssn_present    INTEGER,
            dob_present    INTEGER,
            mrn_present    INTEGER,
            source_file    TEXT,
            confidence     TEXT,
            entity_type    TEXT,
            sensitivity_tier TEXT
        )
    """)
    for p in runbook.get("affected_people", []):
        c.execute(
            "INSERT INTO gold_affected_people VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                p.get("record_id", ""), p.get("name", ""),
                p.get("email", ""), p.get("phone", ""),
                1 if p.get("ssn") else 0,
                1 if p.get("dob") else 0,
                1 if p.get("mrn") else 0,
                p.get("source", ""), str(p.get("confidence", "")),
                "person", "",
            ),
        )

    # ── gold_pii_by_field ─────────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS gold_pii_by_field")
    c.execute("""
        CREATE TABLE gold_pii_by_field (
            field_type   TEXT PRIMARY KEY,
            record_count INTEGER,
            source       TEXT
        )
    """)
    silver_exists = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='silver'"
    ).fetchone()
    if silver_exists:
        try:
            silver_cols = [
                row[1] for row in c.execute("PRAGMA table_info(silver)").fetchall()
            ]
            pii_fields = [
                "ssn", "cc", "mrn", "email", "phone", "name", "dob",
                "account", "routing", "ip", "username", "password",
            ]
            for field in pii_fields:
                if field in silver_cols:
                    count = c.execute(
                        f'SELECT COUNT(*) FROM silver '
                        f'WHERE "{field}" IS NOT NULL AND "{field}" != ""'
                    ).fetchone()[0]
                    if count > 0:
                        c.execute(
                            "INSERT OR REPLACE INTO gold_pii_by_field VALUES (?,?,?)",
                            (field, count, "silver"),
                        )
        except Exception:
            pass

    # Fallback: use pii_summary from runbook state
    if not c.execute("SELECT 1 FROM gold_pii_by_field LIMIT 1").fetchone():
        pii_counts: dict[str, int] = {}
        for hit in runbook.get("pii_summary", []):
            k = hit.get("kind", "")
            if k:
                pii_counts[k] = pii_counts.get(k, 0) + 1
        for field, count in pii_counts.items():
            c.execute(
                "INSERT OR REPLACE INTO gold_pii_by_field VALUES (?,?,?)",
                (field, count, "runbook"),
            )

    # ── gold_file_risk ────────────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS gold_file_risk")
    c.execute("""
        CREATE TABLE gold_file_risk (
            source_file      TEXT PRIMARY KEY,
            bronze_table     TEXT,
            total_rows       INTEGER,
            sensitive_rows   INTEGER,
            field_types      TEXT
        )
    """)
    if silver_exists:
        try:
            rows = c.execute("""
                SELECT _source_file, _source_table,
                       COUNT(*) AS total,
                       SUM(CASE WHEN _sensitivity_tier IN ('critical','high') THEN 1 ELSE 0 END) AS sensitive
                FROM silver
                GROUP BY _source_file, _source_table
            """).fetchall()
            for (src_file, src_tbl, total, sensitive) in rows:
                c.execute(
                    "INSERT OR REPLACE INTO gold_file_risk VALUES (?,?,?,?,?)",
                    (src_file, src_tbl or "", total, sensitive or 0, ""),
                )
        except Exception:
            pass

    # ── gold_exposure_summary ─────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS gold_exposure_summary")
    c.execute("""
        CREATE TABLE gold_exposure_summary (
            total_files      INTEGER,
            total_records    INTEGER,
            affected_people  INTEGER,
            critical_records INTEGER,
            high_records     INTEGER,
            medium_records   INTEGER,
            low_records      INTEGER,
            unique_ssns      INTEGER,
            unique_emails    INTEGER
        )
    """)
    if silver_exists:
        try:
            silver_cols = [
                row[1] for row in c.execute("PRAGMA table_info(silver)").fetchall()
            ]
            total_rec = c.execute("SELECT COUNT(*) FROM silver").fetchone()[0]
            crit   = c.execute("SELECT COUNT(*) FROM silver WHERE _sensitivity_tier='critical'").fetchone()[0]
            high   = c.execute("SELECT COUNT(*) FROM silver WHERE _sensitivity_tier='high'").fetchone()[0]
            med    = c.execute("SELECT COUNT(*) FROM silver WHERE _sensitivity_tier='medium'").fetchone()[0]
            low    = c.execute("SELECT COUNT(*) FROM silver WHERE _sensitivity_tier='low'").fetchone()[0]
            u_emails = (
                c.execute(
                    "SELECT COUNT(DISTINCT email) FROM silver WHERE email != ''"
                ).fetchone()[0]
                if "email" in silver_cols else 0
            )
            u_ssns = (
                c.execute(
                    "SELECT COUNT(DISTINCT ssn) FROM silver WHERE ssn != ''"
                ).fetchone()[0]
                if "ssn" in silver_cols else 0
            )
            n_files = c.execute(
                "SELECT COUNT(DISTINCT _source_file) FROM silver"
            ).fetchone()[0]
            c.execute(
                "INSERT INTO gold_exposure_summary VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    n_files, total_rec,
                    len(runbook.get("affected_people", [])),
                    crit, high, med, low, u_ssns, u_emails,
                ),
            )
        except Exception:
            c.execute(
                "INSERT OR IGNORE INTO gold_exposure_summary "
                "VALUES (0,0,0,0,0,0,0,0,0)"
            )
    else:
        c.execute(
            "INSERT INTO gold_exposure_summary VALUES (?,?,?,?,?,?,?,?,?)",
            (0, 0, len(runbook.get("affected_people", [])), 0, 0, 0, 0, 0, 0),
        )

    conn.commit()
    conn.close()


# ── QUERY ─────────────────────────────────────────────────────────────────────

def open_db(db_path: Path) -> sqlite3.Connection | None:
    """Open analysis.db read-only. Returns None if file doesn't exist."""
    if not db_path.exists():
        return None
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def get_full_schema(db_path: Path) -> dict:
    """
    Read sqlite_master to discover all tables.
    Returns {"bronze": {tbl: {columns, rows}}, "silver": {...}, "gold": {...}}
    Used by /schema route for dynamic schema browser.
    """
    if not db_path.exists():
        return {"bronze": {}, "silver": {}, "gold": {}}

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        result: dict[str, dict] = {"bronze": {}, "silver": {}, "gold": {}}
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        for (tbl,) in tables:
            if tbl.startswith("_"):
                continue
            cols = [
                row[1]
                for row in conn.execute(f'PRAGMA table_info("{tbl}")').fetchall()
            ]
            try:
                row_count = conn.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
            except Exception:
                row_count = 0

            entry = {"columns": cols, "rows": row_count}
            if tbl.startswith("bronze_"):
                result["bronze"][tbl] = entry
            elif tbl.startswith("gold_"):
                result["gold"][tbl] = entry
            elif tbl == "silver":
                result["silver"][tbl] = entry
        return result
    finally:
        conn.close()
