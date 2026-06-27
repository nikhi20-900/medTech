"""
Severity detection for the Medet triage pipeline.

Simple keyword-based heuristic that returns ``"high"``, ``"medium"``,
or ``"low"`` for a given user message.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Severity keyword sets
# ---------------------------------------------------------------------------

_HIGH_KEYWORDS: tuple[str, ...] = (
    "severe",
    "unbearable",
    "worst",
    "cannot",
    "can't",
    "cant",
    "heavy",
    "extreme",
    "excruciating",
    "intense",
)

_MEDIUM_KEYWORDS: tuple[str, ...] = (
    "high fever",
    "persistent",
    "worsening",
    "many days",
    "getting worse",
    "not improving",
    "keeps coming back",
)


def detect_severity(message: str) -> str:
    """Return ``"high"``, ``"medium"``, or ``"low"`` for *message*."""
    text = message.lower().strip()

    for keyword in _HIGH_KEYWORDS:
        if keyword in text:
            return "high"

    for keyword in _MEDIUM_KEYWORDS:
        if keyword in text:
            return "medium"

    return "low"
