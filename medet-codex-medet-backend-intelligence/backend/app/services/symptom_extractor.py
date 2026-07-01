"""
Symptom extraction for the Medet triage pipeline.

Scans a user message against the keyword dictionaries in
:mod:`symptom_patterns` and returns an :class:`ExtractionResult`
containing matched symptoms, the best-fit category, an emergency
candidate flag, and a confidence score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.services.emergency_detector import _is_negated, _normalize
from backend.app.services.symptom_patterns import (
    EMERGENCY_CANDIDATE_KEYWORDS,
    SYMPTOM_CATEGORIES,
)

# Pregnancy is always the highest-priority category when present.
_PRIORITY_CATEGORY = "pregnancy"


@dataclass(frozen=True)
class ExtractionResult:
    """Output of the symptom extraction stage."""

    symptoms: list[str] = field(default_factory=list)
    category: str = "general"
    emergency_candidate: bool = False
    confidence: float = 0.0


def extract_symptoms(message: str) -> ExtractionResult:
    """Extract symptoms, determine category, and compute confidence."""
    text = message.lower().strip()

    # ------------------------------------------------------------------
    # 1. Find all matching symptom keywords across every category
    # ------------------------------------------------------------------
    matched_symptoms: list[str] = []
    category_scores: dict[str, int] = {}

    for category, keywords in SYMPTOM_CATEGORIES.items():
        count = 0
        for keyword in keywords:
            if keyword in text:
                if keyword not in matched_symptoms:
                    matched_symptoms.append(keyword)
                count += 1
        if count > 0:
            category_scores[category] = count

    # ------------------------------------------------------------------
    # 2. Determine the best category
    # ------------------------------------------------------------------
    category = _resolve_category(category_scores)

    # ------------------------------------------------------------------
    # 3. Emergency candidate check (negation-aware)
    # ------------------------------------------------------------------
    normalized = _normalize(text)
    emergency_candidate = any(
        kw in normalized and not _is_negated(normalized, kw)
        for kw in EMERGENCY_CANDIDATE_KEYWORDS
    )

    # ------------------------------------------------------------------
    # 4. Confidence heuristic
    # ------------------------------------------------------------------
    confidence = _compute_confidence(matched_symptoms, text)

    return ExtractionResult(
        symptoms=matched_symptoms,
        category=category,
        emergency_candidate=emergency_candidate,
        confidence=confidence,
    )


def _resolve_category(scores: dict[str, int]) -> str:
    """Pick the winning category.

    Rules:
    - If *pregnancy* matched at all, it always wins (highest clinical priority).
    - Otherwise the category with the most keyword matches wins.
    - Ties are broken alphabetically (deterministic).
    - If nothing matched, return ``"general"``.
    """
    if not scores:
        return "general"

    if _PRIORITY_CATEGORY in scores:
        return _PRIORITY_CATEGORY

    # Sort by score descending, then name ascending for determinism.
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[0][0]


def _compute_confidence(symptoms: list[str], text: str) -> float:
    """Simple heuristic: more matched symptoms → higher confidence.

    Scoring:
    - 0 symptoms → 0.3  (vague / non-medical)
    - 1 symptom  → 0.7
    - 2 symptoms → 0.85
    - 3+ symptoms → 0.95

    A very short message (< 4 words) with no symptoms gets 0.2.
    """
    n = len(symptoms)
    word_count = len(text.split())

    if n == 0:
        return 0.2 if word_count < 4 else 0.3
    if n == 1:
        return 0.7
    if n == 2:
        return 0.85
    return 0.95
