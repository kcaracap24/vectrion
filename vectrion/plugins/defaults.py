from __future__ import annotations

from vectrion.constants import LEGAL_DISCLAIMER
from vectrion.plugins.base import ExtractorPlugin, NotificationPlugin


class DeterministicExtractor(ExtractorPlugin):
    """
    Deterministic field extractor compatible with both:
      - Legacy evidence.csv format  (event_id, timestamp, subject, detail, email, phone)
      - Vault-normalized records     (record_id, source_file, name, email, ssn, dob, raw_text, …)
    """
    name = "deterministic"

    def extract(self, record: dict) -> dict:
        # Resolve the text field — prefer raw_text (vault) then detail (legacy)
        raw = record.get("raw_text") or record.get("detail") or ""

        return {
            # Core identity
            "event_id":   record.get("event_id")  or record.get("record_id") or "",
            "timestamp":  record.get("timestamp") or record.get("uploaded_at") or "",
            "subject":    record.get("subject")   or record.get("source_file") or "",
            "detail":     raw,
            # Contact / PII
            "name":       record.get("name", ""),
            "email":      record.get("email", ""),
            "phone":      record.get("phone", ""),
            # Health
            "ssn":        record.get("ssn", ""),
            "dob":        record.get("dob", ""),
            "mrn":        record.get("mrn", ""),
            # Financial
            "cc":         record.get("cc", ""),
            "account":    record.get("account", ""),
            "routing":    record.get("routing", ""),
            # Network
            "ip":         record.get("ip", ""),
            # Auth
            "username":   record.get("username", ""),
            # Source metadata
            "source_file":  record.get("source_file", ""),
            "source_type":  record.get("source_type", ""),
            "pii_types":    record.get("pii_types", []),
        }


class DraftOnlyNotifier(NotificationPlugin):
    """
    Produces a draft notification text — never sends automatically.
    Incorporates real breach metadata when available.
    """
    name = "draft-only"

    def draft(self, incident: dict) -> str:
        iid    = incident.get("incident_id", "unknown")
        total  = incident.get("affected_count", "")
        juris  = incident.get("jurisdictions", "")
        regs   = incident.get("regulations", [])
        btype  = incident.get("breach_type", "")
        if isinstance(btype, list):
            btype = ", ".join(btype)

        lines = [
            f"DRAFT BREACH NOTIFICATION — {iid}",
            "=" * 60,
            "",
            "TO: [Affected Individual]",
            "FROM: [Organization Name]",
            f"RE: Notice of Data Security Incident — {iid}",
            "",
            "We are writing to inform you that we recently discovered",
            "unauthorized access to systems containing your personal",
            "information.",
        ]

        if btype:
            lines.append(f"\nType of incident: {btype}")
        if total:
            lines.append(f"Estimated affected individuals: {total}")
        if juris:
            lines.append(f"Affected jurisdictions: {juris}")
        if regs:
            lines.append(f"Applicable regulations: {', '.join(regs) if isinstance(regs, list) else regs}")

        lines += [
            "",
            "WHAT INFORMATION WAS INVOLVED",
            "The following categories of information may have been exposed:",
            "[TO BE COMPLETED BY LEGAL COUNSEL BASED ON STAGE 3 CLASSIFICATION]",
            "",
            "WHAT WE ARE DOING",
            "We have engaged cybersecurity experts and legal counsel.",
            "We are notifying affected individuals and relevant regulators",
            "as required by applicable law.",
            "",
            "WHAT YOU CAN DO",
            "- Place a fraud alert or credit freeze with the major bureaus",
            "- Monitor your financial accounts for unusual activity",
            "- Contact us at [BREACH RESPONSE HOTLINE] with questions",
            "",
            f"{LEGAL_DISCLAIMER}",
            "",
            "NOTE: This is a DRAFT only. No notification has been sent.",
            "This draft requires review and approval by qualified legal counsel",
            "before any distribution.",
        ]

        return "\n".join(lines)
