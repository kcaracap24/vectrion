from __future__ import annotations

from vectrion.detectors import detect_pii


def redact_text(text: str) -> str:
    out = text
    for hit in detect_pii(text):
        if hit.kind == "email":
            out = out.replace(hit.value, "[REDACTED_EMAIL]")
        elif hit.kind == "phone":
            out = out.replace(hit.value, "[REDACTED_PHONE]")
        elif hit.kind == "ssn":
            out = out.replace(hit.value, "[REDACTED_SSN]")
        elif hit.kind == "ip":
            out = out.replace(hit.value, "[REDACTED_IP]")
        elif hit.kind == "credit_card":
            out = out.replace(hit.value, "[REDACTED_CREDIT_CARD]")
    return out
