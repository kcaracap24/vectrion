from pathlib import Path


def test_core_migration_exists_and_mentions_tables():
    sql = (Path(__file__).resolve().parents[1] / "migrations" / "001_core_entities.sql").read_text(encoding="utf-8")
    for table in [
        "incidents",
        "runs",
        "evidence_files",
        "normalized_records",
        "pii_findings",
        "identity_links",
        "affected_people",
        "drafts",
        "audit_logs",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
