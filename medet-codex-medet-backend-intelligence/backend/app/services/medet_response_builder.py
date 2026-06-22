from __future__ import annotations

from typing import Any

from backend.app.schemas.medet_response import (
    DEFAULT_INPUT_TYPE,
    DEFAULT_LANGUAGE,
    MedetResponse,
    normalize_sources,
)
from backend.app.services.emergency_detector import detect_emergency
from backend.app.services.healthcare_cards import build_healthcare_cards
from backend.app.services.language_support import get_doctor_suggestion_text
from backend.app.services.medical_safety_guard import guard_medical_response
from backend.app.services.voice_support import build_voice_metadata

MEDICAL_KEYWORDS = {
    # English symptoms
    "fever",
    "headache",
    "pain",
    "cough",
    "vomiting",
    "nausea",
    "bleeding",
    "injury",
    "breathing",
    "breathe",
    "breathless",
    "gasping",
    "suffocating",
    "doctor",
    "medicine",
    "hospital",
    "symptom",
    "sick",
    "ill",
    "weakness",
    "chest",
    "dizzy",
    "diarrhea",
    "infection",
    "allergy",
    "burn",
    "seizure",
    "convulsion",
    "fits",
    "stroke",
    "unconscious",
    "fainted",
    "collapsed",
    "pregnant",
    "heart attack",
    "dehydration",
    "blood",
    "urine",
    "stool",
    # Hindi / Romanized Hindi
    "bukhar",
    "dard",
    "khoon",
    "behosh",
    "daura",
    "saans",
    "seene",
    "chhati",
    "बुखार",
    "दर्द",
    "खून",
    "बेहोश",
    "दौरा",
    "सांस",
    "छाती",
    "लकवा",
    "ज्वरो",
    # Bengali
    "জ্বর",
    "ব্যথা",
    "রক্ত",
    "অজ্ঞান",
    "খিঁচুনি",
    "শ্বাস",
    "বুকে",
    # Tamil
    "காய்ச்சல்",
    "வலி",
    "ரத்தம்",
    "மயக்கம்",
    "வலிப்பு",
    "மூச்சு",
    # Kannada
    "ಜ್ವರ",
    "ನೋವು",
    "ರಕ್ತ",
    "ಬೇಹೋಷ್",
    "ಉಸಿರು",
    # Nepali
    "रगत",
    "सास",
}


def is_medical_query(message: str | None) -> bool:
    if not message:
        return False

    lowered = message.lower()
    return any(
        keyword in lowered
        for keyword in MEDICAL_KEYWORDS
    )


def build_medet_response(
    ai_text: str,
    user_message: str | None = None,
    sources: list[dict[str, Any] | str] | None = None,
    suggest_doctor: bool | None = None,
    conversation_id: str | None = None,
    input_type: str = DEFAULT_INPUT_TYPE,
    language: str = DEFAULT_LANGUAGE,
) -> MedetResponse:
    """
    Attach healthcare metadata to a Medet answer.
    """
    medical_query = is_medical_query(user_message)

    if medical_query:
        detection = detect_emergency(user_message)
    else:
        detection = {
            "emergency": False,
            "severity": "low",
            "reason": None,
        }

    emergency = bool(detection["emergency"])

    safety = guard_medical_response(
        ai_text,
        user_message=user_message,
        emergency=emergency,
        language=language,
    )
    final_text = safety.response

    should_suggest_doctor = (
        emergency or safety.suggest_doctor
        if suggest_doctor is None
        else bool(
            suggest_doctor
            or emergency
            or safety.suggest_doctor
        )
    )

    if not medical_query:
        emergency = False
        should_suggest_doctor = False

    if suggest_doctor and not emergency:
        final_text = _append_once(
            final_text,
            get_doctor_suggestion_text(language),
        )

    cards = []
    if medical_query:
        cards = build_healthcare_cards(
            response=final_text,
            user_message=user_message,
            emergency=emergency,
            severity=str(detection["severity"]),
            suggest_doctor=should_suggest_doctor,
            medical_warning=safety.medical_warning,
            trust_level=safety.trust_level,
            language=language,
        )

    return MedetResponse(
        response=final_text,
        input_type=input_type,
        language=language,
        emergency=emergency,
        severity=str(detection["severity"]),
        reason=(
            detection["reason"]
            if isinstance(detection["reason"], str)
            else None
        ),
        medical_warning=safety.medical_warning,
        trust_level=safety.trust_level,
        suggest_doctor=should_suggest_doctor,
        cards=cards,
        sources=normalize_sources(sources),
        voice=build_voice_metadata(
            input_type=input_type,
            language=language,
            transcript=user_message,
            response_text=final_text,
        ),
        **(
            {"conversation_id": conversation_id}
            if conversation_id
            else {}
        ),
    )


def _append_once(text: str, addition: str) -> str:
    if addition in text:
        return text

    if not text:
        return addition
    return f"{text}\n\n{addition}"