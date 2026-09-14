"""
The threat-suggestion engine.

Design goal: every suggestion this module produces must be traceable to (a)
a real SPARTA technique ID loaded from app/data/sparta_techniques.json, and
(b) an explicit rule below. There is no free-text generation in this file -
that keeps the core matching deterministic, reproducible, and reviewable by
a human analyst, which matters given the "do not hallucinate" requirement.
A separate, optional layer (app/ai_assist.py) can add AI-written narrative
on TOP of this module's output, but never in place of it, and it is
constrained to only reference technique IDs this module already selected.

Segment-matching is a heuristic, not an official SPARTA mapping (SPARTA
itself does not publish a technique-to-deployment-segment matrix). It flags
techniques whose text mentions a segment the system under review actually
has, which is a reasonable first pass for an analyst - not a substitute for
expert review. This limitation is stated again in the UI (see
templates/matrix.html) and README.md.
"""
from dataclasses import dataclass

from app.models import Technique, SEVERITY_ORDER


# Techniques that keyword-match "space" fire for almost every mission, since
# the SPARTA taxonomy is itself spacecraft-centric. To keep a first-pass
# result useful rather than overwhelming, only tactics most associated with
# externally-reachable attack surface are auto-selected for a bare-minimum
# system (space segment only, nothing else declared); everything else still
# shows up in the matrix as an available, filterable question.
BASELINE_SEVERITY_BY_TACTIC = {
    "ST0001": "low",     # Reconnaissance
    "ST0002": "low",     # Resource Development
    "ST0003": "high",    # Initial Access
    "ST0004": "high",    # Execution
    "ST0005": "medium",  # Persistence
    "ST0006": "medium",  # Defense Evasion
    "ST0007": "high",    # Lateral Movement
    "ST0008": "medium",  # Exfiltration
    "ST0009": "critical",  # Impact
}

# Conditions that bump severity for specific, named risk patterns. Each rule
# is intentionally narrow and documented, rather than a general-purpose
# scoring formula, so a reviewer can see exactly why a finding was raised.
RISK_MODIFIERS = [
    {
        "id": "unencrypted_tt_and_c",
        "condition": lambda sysrow: not sysrow.has_encrypted_tt_and_c,
        "applies_to_segments": {"link"},
        "bump": 1,
        "note": "TT&C link is not marked as encrypted - link-segment command/telemetry techniques are more likely to succeed.",
    },
    {
        "id": "third_party_auth",
        "condition": lambda sysrow: sysrow.uses_third_party_auth,
        "applies_to_segments": {"user", "ground"},
        "bump": 1,
        "note": "Third-party authentication is in use - account-takeover and credential-based techniques against ground/user segments are more relevant.",
    },
    {
        "id": "no_supply_chain_program",
        "condition": lambda sysrow: not sysrow.has_supply_chain_program,
        "applies_to_segments": {"supply_chain"},
        "bump": 1,
        "note": "No supply-chain security program declared - supply-chain techniques are more likely to be unmitigated.",
    },
    {
        "id": "constellation",
        "condition": lambda sysrow: sysrow.is_constellation,
        "applies_to_segments": {"link"},
        "bump": 1,
        "note": "Constellation architecture - cross-link/lateral-movement techniques between satellites gain relevance.",
    },
]


def _bump_severity(base: str, bump: int) -> str:
    order = ["low", "medium", "high", "critical"]
    idx = min(order.index(base) + bump, len(order) - 1)
    return order[idx]


@dataclass
class SuggestedFinding:
    technique_id: str
    severity: str
    rationale: str


def suggest_findings(space_system) -> list[SuggestedFinding]:
    """Return candidate findings for a SpaceSystem based on its declared
    segments and risk flags. Pure function of the system's own fields and
    the loaded technique catalog - no network calls, no randomness."""
    system_segments = set(space_system.segments)
    if not system_segments:
        return []

    candidates = (
        Technique.query.filter(Technique.is_subtechnique.is_(False)).all()
    )

    results = []
    for tech in candidates:
        tech_segments = set(tech.segments)
        overlap = tech_segments & system_segments
        if not overlap:
            continue

        base_severity = BASELINE_SEVERITY_BY_TACTIC.get(tech.tactic_id, "medium")
        notes = [
            f"Technique targets the {', '.join(sorted(overlap))} segment(s), "
            f"which this system has declared."
        ]

        bump_total = 0
        for rule in RISK_MODIFIERS:
            if overlap & rule["applies_to_segments"] and rule["condition"](space_system):
                bump_total += rule["bump"]
                notes.append(rule["note"])

        # Cap the total bump at one severity tier. Multiple risk factors
        # firing at once is a reason to flag them all in the rationale, but
        # each is an independent heuristic signal, not an additive score -
        # stacking them unbounded pushed most findings straight to
        # "critical" in testing and made the matrix useless for
        # prioritization. One confirmed elevated-risk condition is enough
        # to move a finding up a tier; more than one doesn't move it twice.
        bump_total = min(bump_total, 1)
        severity = _bump_severity(base_severity, bump_total)
        results.append(
            SuggestedFinding(
                technique_id=tech.id,
                severity=severity,
                rationale=" ".join(notes),
            )
        )

    results.sort(key=lambda r: SEVERITY_ORDER[r.severity], reverse=True)
    return results
