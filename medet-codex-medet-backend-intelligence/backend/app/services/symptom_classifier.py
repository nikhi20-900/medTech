"""
Symptom classifier — triage pipeline orchestrator.

This module is the single entry point for the triage pipeline.  It
composes the individual stages (extraction, severity, duration, missing
info) and returns a :class:`TriageContext` that captures the full
structured understanding of a user's message.

Follow-up questions are **not** determined here — they are computed by
the conversation state engine which has multi-turn context.

Pipeline:
    Symptom Patterns  →  Extraction  →  Severity  →  Duration
        →  Missing Info  →  **TriageContext**
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.services.duration_detector import extract_duration
from backend.app.services.missing_info_detector import detect_missing_info
from backend.app.services.severity_detector import detect_severity
from backend.app.services.symptom_extractor import extract_symptoms


@dataclass(frozen=True)
class TriageContext:
    """Structured output of the full triage pipeline."""

    category: str
    symptoms: list[str] = field(default_factory=list)
    severity: str = "low"
    duration: str | None = None
    emergency_candidate: bool = False
    confidence: float = 0.0
    missing_info: list[str] = field(default_factory=list)
    followup_questions: list[str] = field(default_factory=list)


def classify_symptom(message: str) -> TriageContext:
    """Run the full triage pipeline and return a :class:`TriageContext`.

    This function replaces the old ``classify_symptom`` that returned a
    simple ``SymptomCategory(name, severity)``.  The function name is
    preserved so existing call-sites need only adapt to the richer
    return type.

    .. note::
        Follow-up questions are **not** populated here.  They are
        determined by the conversation state engine which has access
        to multi-turn context.
    """
    # Stage 2 — Symptom Extraction
    extraction = extract_symptoms(message)

    # Stage 3 — Severity Detection
    severity = detect_severity(message)

    # Stage 4 — Duration Detection
    duration = extract_duration(message)

    # Stage 5 — Missing Information Detection
    missing = detect_missing_info(extraction, severity, duration)

    # Stage 6 — Assemble TriageContext
    return TriageContext(
        category=extraction.category,
        symptoms=extraction.symptoms,
        severity=severity,
        duration=duration,
        emergency_candidate=extraction.emergency_candidate,
        confidence=extraction.confidence,
        missing_info=missing.gaps,
    )

