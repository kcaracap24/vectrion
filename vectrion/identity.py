from __future__ import annotations


def _norm_phone(v: str) -> str:
    return "".join(filter(str.isdigit, v or ""))[-10:]


def explain_identity_match(a: dict, b: dict) -> dict:
    factors: list[dict] = []
    score = 0.0

    email_match = bool(a.get("email") and b.get("email") and a["email"].lower() == b["email"].lower())
    factors.append({"field": "email", "match": email_match, "weight": 0.6})
    if email_match:
        score += 0.6

    phone_match = bool(a.get("phone") and b.get("phone") and _norm_phone(a["phone"]) == _norm_phone(b["phone"]))
    factors.append({"field": "phone", "match": phone_match, "weight": 0.3})
    if phone_match:
        score += 0.3

    name_match = bool(a.get("name") and b.get("name") and a["name"].strip().lower() == b["name"].strip().lower())
    factors.append({"field": "name", "match": name_match, "weight": 0.1})
    if name_match:
        score += 0.1

    score = round(min(score, 1.0), 4)
    confidence = "high" if score >= 0.8 else "medium" if score >= 0.5 else "low"
    summary = ", ".join([f"{f['field']}={'yes' if f['match'] else 'no'}" for f in factors])
    return {"score": score, "confidence": confidence, "factors": factors, "summary": summary}


def score_identity_match(a: dict, b: dict) -> float:
    return explain_identity_match(a, b)["score"]
