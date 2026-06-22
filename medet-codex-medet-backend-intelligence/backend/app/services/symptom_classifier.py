from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymptomCategory:
    name: str
    severity: str


def classify_symptom(message: str) -> SymptomCategory:
    """
    Simple rule-based symptom classifier.

    Categories:
    - pregnancy
    - cardiac
    - neurological
    - gastrointestinal
    - injury
    - respiratory
    - general

    IMPORTANT:
    Order matters.
    More specific conditions should be checked first.
    """

    text = message.lower().strip()

    # Pregnancy (highest priority)
    if any(word in text for word in [
        "pregnant",
        "pregnancy",
        "expecting",
        "गर्भवती",
        "गर्भावस्था",
    ]):
        return SymptomCategory(
            name="pregnancy",
            severity="medium",
        )

    # Cardiac
    if any(word in text for word in [
        "chest pain",
        "heart pain",
        "heart attack",
        "pressure in chest",
        "tightness in chest",
        "left arm pain",
    ]):
        return SymptomCategory(
            name="cardiac",
            severity="high",
        )

    # Neurological
    if any(word in text for word in [
        "headache",
        "migraine",
        "dizzy",
        "dizziness",
        "blurred vision",
        "vision problem",
        "numbness",
        "weakness",
    ]):
        return SymptomCategory(
            name="neurological",
            severity="medium",
        )

    # Gastrointestinal
    if any(word in text for word in [
        "vomiting",
        "vomit",
        "nausea",
        "diarrhea",
        "stomach pain",
        "abdominal pain",
        "food poisoning",
    ]):
        return SymptomCategory(
            name="gastrointestinal",
            severity="medium",
        )

    # Injury
    if any(word in text for word in [
        "cut",
        "injury",
        "wound",
        "burn",
        "fracture",
        "broken bone",
        "bleeding",
    ]):
        return SymptomCategory(
            name="injury",
            severity="medium",
        )

    # Respiratory
    if any(word in text for word in [
        "fever",
        "cough",
        "cold",
        "flu",
        "sore throat",
        "runny nose",
        "breathing",
    ]):
        return SymptomCategory(
            name="respiratory",
            severity="low",
        )

    return SymptomCategory(
        name="general",
        severity="low",
    )
