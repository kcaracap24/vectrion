from __future__ import annotations

from vectrion.constants import LEGAL_DISCLAIMER
from vectrion.plugins.base import ExtractorPlugin, NotificationPlugin


class DeterministicExtractor(ExtractorPlugin):
    name = "deterministic"

    def extract(self, record: dict) -> dict:
        # deterministic-first extraction: pure field mapping
        return {
            "event_id": record.get("event_id", ""),
            "timestamp": record.get("timestamp", ""),
            "subject": record.get("subject", ""),
            "detail": record.get("detail", ""),
            "email": record.get("email", ""),
            "phone": record.get("phone", ""),
        }


class DraftOnlyNotifier(NotificationPlugin):
    name = "draft-only"

    def draft(self, incident: dict) -> str:
        return (
            f"Incident {incident.get('incident_id')} requires review.\n"
            "Recommended audience: Security + Legal + Compliance\n"
            f"{LEGAL_DISCLAIMER}\n"
            "NOTE: This is a draft only. No notifications were sent."
        )
