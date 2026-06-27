"""
Missing information detection for the Medet triage pipeline.

Analyzes the results of symptom extraction, severity detection, and
duration detection to identify *gaps* — critical information that the
user has **not** provided.  The gaps are used by the follow-up question
engine to prioritize the most relevant questions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.services.symptom_extractor import ExtractionResult


@dataclass(frozen=True)
class MissingInfo:
    """Gaps detected in the user's message."""

    gaps: list[str] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)


def detect_missing_info(
    extraction: ExtractionResult,
    severity: str,
    duration: str | None,
) -> MissingInfo:
    """Return a :class:`MissingInfo` describing what is *not* present."""
    gaps: list[str] = []
    descriptions: list[str] = []

    # ----- Duration missing ------------------------------------------------
    if duration is None:
        gaps.append("duration")
        descriptions.append("How long have you had these symptoms?")

    # ----- Severity ambiguous ----------------------------------------------
    # If severity is "low" but the user clearly has a medical complaint
    # (i.e. category is not "general"), we probably just lack intensity
    # descriptors rather than it truly being a low-severity case.
    if severity == "low" and extraction.category != "general":
        gaps.append("severity")
        descriptions.append("How severe are your symptoms?")

    # ----- Too few symptoms (need more context) ----------------------------
    if len(extraction.symptoms) == 1:
        gaps.append("symptom_detail")
        descriptions.append("Do you have any other symptoms?")

    # ----- Respiratory + fever but no temperature --------------------------
    if (
        extraction.category == "respiratory"
        and "fever" in extraction.symptoms
    ):
        gaps.append("temperature")
        descriptions.append("What is your temperature?")

    # ----- Bleeding mentioned but no severity qualifier --------------------
    if "bleeding" in extraction.symptoms and severity != "high":
        gaps.append("bleeding_detail")
        descriptions.append("How much bleeding is there?")

    return MissingInfo(gaps=gaps, descriptions=descriptions)
