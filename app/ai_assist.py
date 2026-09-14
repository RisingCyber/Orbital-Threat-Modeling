"""
Optional AI-assisted narrative generation.

This module is a thin, deliberately constrained add-on:
- It never chooses which techniques are relevant - app/engine.py already
  did that deterministically. This module only asks a model to write a
  human-readable analyst narrative ABOUT technique IDs it is explicitly
  given.
- The prompt lists the exact allowed technique IDs and instructs the model
  to use only those. After the response comes back, _validate_output()
  independently scans for anything that looks like a SPARTA technique ID
  (e.g. "DE-0001") and rejects the narrative if it references any ID
  outside the allowed set - a second, code-level check that does not rely
  on the model following instructions correctly.
- If ANTHROPIC_API_KEY is not configured, or the anthropic package is not
  installed, every function here returns None and the rest of the app
  keeps working using engine.py's output alone. AI assistance is an
  enhancement, never a dependency.
"""
import re
from typing import Optional

_TECHNIQUE_ID_RE = re.compile(r"\b[A-Z]{2,3}-\d{4}(?:\.\d{2})?\b")


def _validate_output(text: str, allowed_ids: set[str]) -> bool:
    mentioned = set(_TECHNIQUE_ID_RE.findall(text))
    return mentioned <= allowed_ids


def generate_narrative(system, findings, api_key: Optional[str]) -> Optional[str]:
    """findings: iterable of app.engine.SuggestedFinding, already selected
    by the deterministic engine. Returns plain text, or None if AI
    assistance is unavailable or its output failed validation."""
    if not api_key or not findings:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    allowed_ids = {f.technique_id for f in findings}
    finding_lines = "\n".join(
        f"- {f.technique_id} (severity: {f.severity}): {f.rationale}" for f in findings[:25]
    )

    prompt = (
        "You are assisting a security analyst reviewing a space/satellite system. "
        "Below is a system summary and a fixed list of SPARTA technique IDs that a "
        "rule-based engine already selected as relevant. Write a short prioritization "
        "narrative (roughly 150-250 words) for the analyst.\n\n"
        "Hard constraint: refer ONLY to the technique IDs listed below. Do not invent, "
        "rename, or introduce any technique ID that is not in this list.\n\n"
        f"System: {system.name}\n"
        f"Mission type: {system.mission_type or 'unspecified'}\n"
        f"Declared segments: {', '.join(system.segments) or 'none'}\n\n"
        f"Candidate findings:\n{finding_lines}\n"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
    except Exception:
        # Any API/network failure degrades to "no AI narrative", never to a crash.
        return None

    if not text or not _validate_output(text, allowed_ids):
        return None
    return text
