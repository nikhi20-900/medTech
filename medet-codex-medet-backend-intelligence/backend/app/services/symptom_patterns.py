"""
Symptom keyword dictionaries for the Medet triage pipeline.

This module is pure data — no business logic.  Other pipeline stages
import these dictionaries to perform extraction and classification.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Category → symptom keywords
# ---------------------------------------------------------------------------
# Order within each tuple does not matter.  Category *priority* is handled
# by the extraction stage (symptom_extractor.py), not here.

SYMPTOM_CATEGORIES: dict[str, tuple[str, ...]] = {
    "respiratory": (
        "fever",
        "cough",
        "sore throat",
        "runny nose",
        "congestion",
        "mucus",
        "phlegm",
        "breathlessness",
        "cold",
        "flu",
    ),
    "cardiac": (
        "chest pain",
        "chest tightness",
        "jaw pain",
        "left arm pain",
        "palpitations",
        "heart pain",
        "pressure in chest",
    ),
    "neurological": (
        "headache",
        "dizziness",
        "blurred vision",
        "fainting",
        "weakness",
        "numbness",
        "migraine",
    ),
    "gastrointestinal": (
        "vomiting",
        "diarrhea",
        "nausea",
        "stomach pain",
        "abdominal pain",
        "food poisoning",
    ),
    "pregnancy": (
        "pregnant",
        "pregnancy",
        "bleeding during pregnancy",
    ),
    "injury": (
        "burn",
        "fracture",
        "cut",
        "bleeding",
        "wound",
        "broken bone",
    ),
    "general": (
        "tired",
        "weakness",
        "fatigue",
    ),
}

# ---------------------------------------------------------------------------
# Emergency candidate keywords
# ---------------------------------------------------------------------------
# These are checked by the extractor to flag messages as *potential*
# emergencies.  This does NOT replace the full EmergencyDetector.

EMERGENCY_CANDIDATE_KEYWORDS: tuple[str, ...] = (
    "chest pain",
    "cannot breathe",
    "can't breathe",
    "cant breathe",
    "severe bleeding",
    "seizure",
    "unconscious",
    "stroke",
    "heart attack",
    "not breathing",
)
