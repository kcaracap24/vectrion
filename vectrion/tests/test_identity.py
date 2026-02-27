from vectrion.identity import explain_identity_match, score_identity_match


def test_identity_resolution_scoring():
    a = {"name": "Alex Morgan", "email": "alex@example.com", "phone": "+1 415 555 0199"}
    b = {"name": "alex morgan", "email": "alex@example.com", "phone": "415-555-0199"}
    assert score_identity_match(a, b) == 1.0


def test_identity_resolution_partial():
    a = {"name": "Alex Morgan", "email": "alex@example.com"}
    b = {"name": "Not Alex", "email": "alex@example.com"}
    assert score_identity_match(a, b) == 0.6


def test_identity_explainability_shape():
    a = {"name": "Alex Morgan", "email": "alex@example.com", "phone": "4155550100"}
    b = {"name": "Alex Morgan", "email": "alex@example.com", "phone": "4155550100"}
    info = explain_identity_match(a, b)
    assert info["confidence"] == "high"
    assert info["score"] == 1.0
    assert len(info["factors"]) == 3
    assert "email=yes" in info["summary"]
