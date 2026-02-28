from __future__ import annotations

from vectrion.detectors import detect_pii

# Replacement tokens for each PII kind
_TOKENS: dict[str, str] = {
    "email":           "[REDACTED_EMAIL]",
    "phone":           "[REDACTED_PHONE]",
    "ssn":             "[REDACTED_SSN]",
    "ein":             "[REDACTED_EIN]",
    "dob":             "[REDACTED_DOB]",
    "mrn":             "[REDACTED_MRN]",
    "npi":             "[REDACTED_NPI]",
    "credit_card":     "[REDACTED_CC]",
    "iban":            "[REDACTED_IBAN]",
    "routing":         "[REDACTED_ROUTING]",
    "account":         "[REDACTED_ACCOUNT]",
    "ip":              "[REDACTED_IP]",
    "mac":             "[REDACTED_MAC]",
    "password":        "[REDACTED_CREDENTIAL]",
    "passport":        "[REDACTED_PASSPORT]",
    "drivers_license": "[REDACTED_DL]",
    "insurance_id":    "[REDACTED_INSURANCE_ID]",
}


def redact_text(text: str) -> str:
    """Replace all detected PII values with placeholder tokens."""
    out = text
    for hit in detect_pii(text):
        token = _TOKENS.get(hit.kind, f"[REDACTED_{hit.kind.upper()}]")
        out = out.replace(hit.value, token)
    return out
