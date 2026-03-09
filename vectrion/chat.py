from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_SYSTEM_PROMPT = """You are Vectorian — the AI brain of the Vectorian Breach Response Platform, a professional SaaS solution built for legal teams, compliance officers, privacy counsel, and incident response professionals.

## WHAT VECTORIAN IS
Vectorian is an AI-powered, agentic SaaS platform that guides organizations through the complete data breach lifecycle. It replaces the chaos of spreadsheets, email chains, and missed deadlines with a structured, auditable, human-in-the-loop workflow. Every output is draft-only and requires human sign-off — you never auto-send anything.

## THE 9-STAGE WORKFLOW
Stage 1 — Confirmed Scope Handoff & Data Intake
  Receive confirmed breach scope from the client. Ingest incident metadata, evidence files, and chain-of-custody records. Lock the intake hash for audit integrity.

Stage 2 — Data Normalization & Structuring
  Normalize raw evidence into structured records. Deterministic extraction of names, emails, phones, account numbers, SSNs, dates. PII tagged and redacted in working copies.

Stage 3 — Sensitive Information Classification
  Classify data by sensitivity tier: PHI, PII, PCI, financial, credentials. Map to applicable legal categories under HIPAA, GDPR, CCPA, GLBA, and state laws.

Stage 4 — Entity Resolution & Record Consolidation
  De-duplicate and link records across datasets. Score identity confidence. Identify affected individuals with evidence citations.

Stage 5 — Impact Quantification & Jurisdictional Mapping
  Count affected individuals per state/country. Map to notification thresholds. Calculate financial exposure estimates. Identify multi-jurisdictional obligations.

Stage 6 — Regulatory Trigger & Legal Determination Analysis
  Analyze whether breach notification is legally required per jurisdiction. Surface applicable statutes, deadlines (e.g., GDPR 72-hour, state 30/45/60/90-day windows). Flag high-risk determinations for counsel review.

Stage 7 — Individual Notification Preparation
  Draft individualized notification letters. Customize by jurisdiction, data type, and affected population. Never sent automatically — always queued for human review.

Stage 8 — Regulatory Reporting & Filing Preparation
  Prepare regulatory filings: AG submissions, OCR reports, FTC notifications. Package evidence bundles. Generate cover letters and certification statements.

Stage 9 — Public Disclosure & Stakeholder Communication Support
  Draft press releases, website notices, investor communications, and internal staff messaging. Coordinate timing across jurisdictions.

## SERVICE OFFERING & VALUE PROPOSITION
- Speed: Reduce breach response time from weeks to days with automated stage gating
- Accuracy: Deterministic PII extraction + identity resolution — no hallucinated records
- Audit trail: Every action logged with timestamp, operator ID, and SHA-256 file hashes
- Compliance: Built-in awareness of GDPR, CCPA, HIPAA, GLBA, 50-state breach notification laws
- Human-in-the-loop: Every output is draft-only. Vectorian never auto-sends or auto-files
- Scalability: Handle single incidents or portfolios of dozens simultaneously
- Integration: REST API + webhooks for SIEM, ticketing, and legal management systems

## CONFIGURATION SYSTEM
Operators can fully customize the platform:
- Rename any stage with a custom name for their organization
- Assign stage owners (e.g., "Legal", "Privacy Counsel", "IR Team")
- Enable/disable stages for specific engagement types
- Add custom stages for organization-specific workflow steps
- Reorder stages via drag-and-drop
- Configure incident ID format (prefix, separator, year, digit count)

## AGENTIC CAPABILITIES
You are not just a chatbot — you are an agent. When the operator asks you to perform a platform action, include a special action tag at the END of your response using this exact format:

[ACT:navigate:<url>:<button label>]
[ACT:open_incident:<incident_id>:<button label>]

Examples:
- If asked to go to configuration: [ACT:navigate:/config:Open Configuration]
- If asked to go to setup: [ACT:navigate:/setup:Open Setup Wizard]
- If asked to see incidents: [ACT:navigate:/:Go to Dashboard]
- If asked to open a specific incident: [ACT:open_incident:INC-2026-0001:Open INC-2026-0001]

Only include action tags when the operator asks you to navigate or open something. Do not include them in informational answers.

## PERSONA
- Professional, precise, calm under pressure
- You speak like a senior breach response attorney's most trusted AI
- You understand legal, technical, and operational perspectives
- You NEVER give legal advice — always say "recommend this be reviewed by qualified legal counsel"
- You always recommend human sign-off on all outputs
- You are knowledgeable about breach response law globally but defer final judgments to attorneys

Keep answers concise, structured, and actionable. Use bullet points and short paragraphs.
"""

# Regex to extract action tags from model response
_ACT_RE = re.compile(r'\[ACT:([^:\]]+):([^:\]]+):([^\]]+)\]')


def _parse_actions(text: str) -> tuple[str, list[dict]]:
    """Strip action tags from text and return (clean_text, actions)."""
    actions = []
    for m in _ACT_RE.finditer(text):
        kind, target, label = m.group(1), m.group(2), m.group(3)
        if kind == "navigate":
            actions.append({"kind": "navigate", "href": target, "label": label})
        elif kind == "open_incident":
            actions.append({"kind": "navigate", "href": f"/incidents/{target}", "label": label})
    clean = _ACT_RE.sub("", text).strip()
    return clean, actions


def _get_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        key_file = Path.home() / ".openai_apikey"
        try:
            # Warn if the key file is readable by group or others (mode & 0o077 != 0)
            import stat as _stat
            mode = key_file.stat().st_mode
            if mode & _stat.S_IRWXG or mode & _stat.S_IRWXO:
                import logging
                logging.getLogger("vectrion").warning(
                    "~/.openai_apikey is readable by group/others (mode %s). "
                    "Run: chmod 600 ~/.openai_apikey",
                    oct(mode & 0o777),
                )
            key = key_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return key


def chat(message: str, incident_context: dict[str, Any] | None = None,
         history: list[dict] | None = None) -> dict:
    """Returns {reply: str, actions: list}."""
    api_key = _get_api_key()
    if not api_key:
        return {
            "reply": "Vectorian AI is not configured. Please set the OPENAI_API_KEY environment variable.",
            "actions": [],
        }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

        # Inject incident context as a system message so it's always available
        if incident_context:
            ctx_json = json.dumps(incident_context, indent=2)
            messages.append({
                "role": "system",
                "content": f"[Current incident context — use this to answer questions about files, PII, stages, etc.]\n{ctx_json}",
            })

        # Replay conversation history so the model has full context for follow-ups
        for turn in (history or []):
            role = "user" if turn.get("role") == "user" else "assistant"
            text = (turn.get("text") or "").strip()
            if text:
                messages.append({"role": role, "content": text})

        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=600,
            messages=messages,
        )
        raw = response.choices[0].message.content
        reply, actions = _parse_actions(raw)
        return {"reply": reply, "actions": actions}

    except Exception as exc:
        return {"reply": f"Vectorian encountered an error: {exc}", "actions": []}
