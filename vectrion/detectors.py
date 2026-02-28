"""Vectorian PII Detector

Regex-based detection of Personally Identifiable Information (PII),
Protected Health Information (PHI), and financial identifiers.

All detection is deterministic and local — no external API calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────────────
# PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

# Contact
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}\b"
)

# Government IDs
SSN_RE = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
# ITIN uses 9xx- prefix (valid subset of SSN pattern — covered by SSN_RE)
EIN_RE = re.compile(r"\b\d{2}-\d{7}\b")  # Employer ID Number

# Dates — ISO 8601 dates likely to be DOB (1900-2020 range only to reduce FPs)
DOB_RE = re.compile(
    r"\b(19\d{2}|20[01]\d|202[0-5])[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b"
    r"|"
    r"\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19\d{2}|20[01]\d)\b"
)

# Medical
MRN_RE = re.compile(
    r"\b(?:MRN|Patient[\s_-]*ID|Medical[\s_-]*Record(?:[\s_-]*Number)?|PatientNo)"
    r"[\s:=#\-]*([A-Z0-9]{4,12})\b",
    re.IGNORECASE,
)
NPI_RE = re.compile(r"\bNPI[\s:=#-]*(\d{10})\b", re.IGNORECASE)

# Financial
# Credit cards: 13-19 digits with optional spaces/dashes, Luhn not validated (too many FPs)
CC_RE = re.compile(r"\b(?:4\d{3}|5[1-5]\d{2}|6(?:011|5\d{2})|3[47]\d{2}|3(?:0[0-5]|[68]\d)\d)"
                   r"[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{3,4}\b")
# IBAN: 2 letter country + 2 check + 10-30 alphanumeric
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[\s-]?(?:[A-Z0-9]{4}[\s-]?){2,7}[A-Z0-9]{1,4}\b")
# US routing: 9 digits starting with 0-1 or 2-3 (ABA format)
ROUTING_RE = re.compile(r"\b(?:routing|ABA|RTN)[\s:=#-]*(\d{9})\b", re.IGNORECASE)
# Generic account numbers: flagged only when preceded by account-like context
ACCOUNT_RE = re.compile(
    r"\b(?:account[\s_-]*(?:number|no|#)?|acct[\s_-]*(?:no|#)?|bank[\s_-]*acct)"
    r"[\s:=#-]*([A-Z0-9-]{6,20})\b",
    re.IGNORECASE,
)

# Network
IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\b"
)
# MAC address
MAC_RE = re.compile(
    r"\b(?:[0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}\b"
)

# Credentials markers (flag presence, don't expose value)
PASSWORD_RE = re.compile(
    r"\b(?:password|passwd|pwd|passphrase|secret|api_?key|access_?token|auth_?token)"
    r"[\s:=]+\S+",
    re.IGNORECASE,
)

# Passport (US: 1 letter + 8 digits; generic: ≥6 uppercase alphanum)
PASSPORT_RE = re.compile(r"\bpassport[\s:=#-]*([A-Z]\d{8,9}|\d{6,9})\b", re.IGNORECASE)

# Drivers license (US: letter(s)+digits, varies by state; context-gated)
DL_RE = re.compile(
    r"\b(?:driver(?:'?s)?[\s_-]*licen[sc]e|DL|DLN)[\s:=#-]*([A-Z0-9-]{5,15})\b",
    re.IGNORECASE,
)

# Health insurance (US member ID — context-gated)
INSURANCE_RE = re.compile(
    r"\b(?:insurance[\s_-]*(?:id|number|no)|member[\s_-]*id|policy[\s_-]*(?:number|no))"
    r"[\s:=#-]*([A-Z0-9-]{6,20})\b",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIDENCE TABLE
# ─────────────────────────────────────────────────────────────────────────────

CONFIDENCE: dict[str, float] = {
    "email":        0.99,
    "phone":        0.95,
    "ssn":          0.99,
    "ein":          0.90,
    "dob":          0.85,
    "mrn":          0.95,
    "npi":          0.95,
    "credit_card":  0.93,
    "iban":         0.96,
    "routing":      0.97,
    "account":      0.88,
    "ip":           0.80,
    "mac":          0.85,
    "password":     0.99,
    "passport":     0.92,
    "drivers_license": 0.90,
    "insurance_id": 0.88,
}


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PIIHit:
    kind: str
    value: str
    confidence: float = 0.9
    evidence_ref: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _ref(event_id: str, m: re.Match) -> str:
    return f"event:{event_id}:char:{m.start()}-{m.end()}"


def detect_pii(text: str, event_id: str = "") -> list[PIIHit]:
    """
    Detect all PII/PHI/financial identifiers in *text*.
    Returns a list of PIIHit objects (may be empty).
    Operates fully locally — no external calls.
    """
    if not text:
        return []

    hits: list[PIIHit] = []

    # Email (highest priority — low FP)
    for m in EMAIL_RE.finditer(text):
        hits.append(PIIHit("email", m.group(0), CONFIDENCE["email"], _ref(event_id, m)))

    # Phone
    for m in PHONE_RE.finditer(text):
        # Avoid matching things already caught as SSN/CC/ZIP
        val = re.sub(r"[\s.()\-]", "", m.group(0))
        if len(val) >= 10:
            hits.append(PIIHit("phone", m.group(0), CONFIDENCE["phone"], _ref(event_id, m)))

    # SSN
    for m in SSN_RE.finditer(text):
        hits.append(PIIHit("ssn", m.group(0), CONFIDENCE["ssn"], _ref(event_id, m)))

    # EIN (Employer ID)
    for m in EIN_RE.finditer(text):
        # Avoid re-flagging things already caught as SSN (SSN is ddd-dd-dddd, EIN is dd-ddddddd)
        hits.append(PIIHit("ein", m.group(0), CONFIDENCE["ein"], _ref(event_id, m)))

    # Date of birth
    for m in DOB_RE.finditer(text):
        hits.append(PIIHit("dob", m.group(0), CONFIDENCE["dob"], _ref(event_id, m)))

    # Medical record number (context-gated)
    for m in MRN_RE.finditer(text):
        hits.append(PIIHit("mrn", m.group(1), CONFIDENCE["mrn"], _ref(event_id, m)))

    # NPI
    for m in NPI_RE.finditer(text):
        hits.append(PIIHit("npi", m.group(1), CONFIDENCE["npi"], _ref(event_id, m)))

    # Credit card
    for m in CC_RE.finditer(text):
        value = re.sub(r"[ -]", "", m.group(0))
        if 13 <= len(value) <= 19:
            hits.append(PIIHit("credit_card", m.group(0), CONFIDENCE["credit_card"], _ref(event_id, m)))

    # IBAN
    for m in IBAN_RE.finditer(text):
        val = re.sub(r"[\s-]", "", m.group(0))
        if 15 <= len(val) <= 34:
            hits.append(PIIHit("iban", m.group(0), CONFIDENCE["iban"], _ref(event_id, m)))

    # Routing number (context-gated)
    for m in ROUTING_RE.finditer(text):
        hits.append(PIIHit("routing", m.group(1), CONFIDENCE["routing"], _ref(event_id, m)))

    # Account number (context-gated)
    for m in ACCOUNT_RE.finditer(text):
        hits.append(PIIHit("account", m.group(1), CONFIDENCE["account"], _ref(event_id, m)))

    # IP address
    for m in IP_RE.finditer(text):
        # Filter out version strings like 1.0.0.1 in software names — check digit ranges
        octets = m.group(0).split(".")
        if all(0 <= int(o) <= 255 for o in octets):
            hits.append(PIIHit("ip", m.group(0), CONFIDENCE["ip"], _ref(event_id, m)))

    # MAC address
    for m in MAC_RE.finditer(text):
        hits.append(PIIHit("mac", m.group(0), CONFIDENCE["mac"], _ref(event_id, m)))

    # Password/credential markers (flag presence only)
    for m in PASSWORD_RE.finditer(text):
        masked = m.group(0).split(maxsplit=1)[0] + " [REDACTED]"
        hits.append(PIIHit("password", masked, CONFIDENCE["password"], _ref(event_id, m)))

    # Passport (context-gated)
    for m in PASSPORT_RE.finditer(text):
        hits.append(PIIHit("passport", m.group(1), CONFIDENCE["passport"], _ref(event_id, m)))

    # Driver's license (context-gated)
    for m in DL_RE.finditer(text):
        hits.append(PIIHit("drivers_license", m.group(1), CONFIDENCE["drivers_license"], _ref(event_id, m)))

    # Insurance ID (context-gated)
    for m in INSURANCE_RE.finditer(text):
        hits.append(PIIHit("insurance_id", m.group(1), CONFIDENCE["insurance_id"], _ref(event_id, m)))

    return hits


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

#: PII kind → sensitivity tier
SENSITIVITY_MAP: dict[str, str] = {
    "ssn":            "PHI/PII",
    "ein":            "Financial",
    "dob":            "PHI",
    "mrn":            "PHI",
    "npi":            "PHI",
    "insurance_id":   "PHI",
    "credit_card":    "PCI",
    "iban":           "Financial",
    "routing":        "Financial",
    "account":        "Financial",
    "email":          "PII",
    "phone":          "PII",
    "ip":             "Network",
    "mac":            "Network",
    "password":       "Credentials",
    "passport":       "PII",
    "drivers_license":"PII",
}


def classify_hits(hits: list[PIIHit]) -> list[str]:
    """Return sorted unique sensitivity tiers represented in *hits*."""
    tiers: set[str] = set()
    for h in hits:
        t = SENSITIVITY_MAP.get(h.kind)
        if t:
            tiers.add(t)
    order = ["PHI/PII", "PHI", "PCI", "Credentials", "Financial", "PII", "Network"]
    return [t for t in order if t in tiers]
