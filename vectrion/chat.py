from __future__ import annotations

import json
import os
from typing import Any

_SYSTEM_PROMPT = (
    "You are Vectorian, a professional AI breach response agent. "
    "You guide operators through a structured 9-stage breach response workflow: "
    "1) Confirmed Scope Handoff & Data Intake, "
    "2) Data Normalization & Structuring, "
    "3) Sensitive Information Classification, "
    "4) Entity Resolution & Record Consolidation, "
    "5) Impact Quantification & Jurisdictional Mapping, "
    "6) Regulatory Trigger & Legal Determination Analysis, "
    "7) Individual Notification Preparation, "
    "8) Regulatory Reporting & Filing Preparation, "
    "9) Public Disclosure & Stakeholder Communication Support. "
    "You are helpful, precise, and professional. "
    "You never provide legal advice — always recommend human review by qualified legal, "
    "compliance, and security personnel. "
    "Keep answers concise and actionable."
)


def chat(message: str, incident_context: dict[str, Any] | None = None) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return (
            "Vectorian AI is not configured. "
            "Please set the ANTHROPIC_API_KEY environment variable to enable the chat agent."
        )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        user_content = message
        if incident_context:
            ctx_json = json.dumps(incident_context, indent=2)
            user_content = f"[Incident context]\n{ctx_json}\n\n[Operator question]\n{message}"

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text
    except Exception as exc:
        return f"Vectorian encountered an error: {exc}"
