from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,2}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

CONFIDENCE = {
    "email": 0.99,
    "phone": 0.95,
    "ssn": 0.99,
    "ip": 0.8,
    "credit_card": 0.93,
}


@dataclass
class PIIHit:
    kind: str
    value: str
    confidence: float = 0.9
    evidence_ref: str = ""


def detect_pii(text: str, event_id: str = "") -> list[PIIHit]:
    hits: list[PIIHit] = []
    for m in EMAIL_RE.finditer(text):
        hits.append(PIIHit("email", m.group(0), CONFIDENCE["email"], f"event:{event_id}:char:{m.start()}-{m.end()}"))
    for m in PHONE_RE.finditer(text):
        hits.append(PIIHit("phone", m.group(0), CONFIDENCE["phone"], f"event:{event_id}:char:{m.start()}-{m.end()}"))
    for m in SSN_RE.finditer(text):
        hits.append(PIIHit("ssn", m.group(0), CONFIDENCE["ssn"], f"event:{event_id}:char:{m.start()}-{m.end()}"))
    for m in IP_RE.finditer(text):
        hits.append(PIIHit("ip", m.group(0), CONFIDENCE["ip"], f"event:{event_id}:char:{m.start()}-{m.end()}"))
    for m in CC_RE.finditer(text):
        value = re.sub(r"[ -]", "", m.group(0))
        if 13 <= len(value) <= 16:
            hits.append(PIIHit("credit_card", m.group(0), CONFIDENCE["credit_card"], f"event:{event_id}:char:{m.start()}-{m.end()}"))
    return hits
