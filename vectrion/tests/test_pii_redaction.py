from vectrion.detectors import detect_pii
from vectrion.redaction import redact_text


def test_detect_pii_email_phone_ssn():
    text = "email a@b.com phone 415-555-0100 ssn 123-45-6789"
    hits = detect_pii(text, event_id="E1")
    kinds = sorted([h.kind for h in hits])
    assert kinds == ["email", "phone", "ssn"]
    assert all(h.confidence > 0.9 for h in hits)
    assert all(h.evidence_ref.startswith("event:E1:char:") for h in hits)


def test_redaction_policy():
    text = "Contact alex@example.com or 415-555-0100 ssn 123-45-6789"
    red = redact_text(text)
    assert "[REDACTED_EMAIL]" in red
    assert "[REDACTED_PHONE]" in red
    assert "[REDACTED_SSN]" in red
