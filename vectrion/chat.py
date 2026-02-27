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
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return (
            "Vectorian AI is not configured. "
            "Please set the OPENAI_API_KEY environment variable to enable the chat agent."
        )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        user_content = message
        if incident_context:
            ctx_json = json.dumps(incident_context, indent=2)
            user_content = f"[Incident context]\n{ctx_json}\n\n[Operator question]\n{message}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=512,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content
    except Exception as exc:
        return f"Vectorian encountered an error: {exc}"
