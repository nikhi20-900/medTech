from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.services.conversation_state import ConversationState

FOLLOWUP_QUESTIONS = {
    "respiratory": [
        "How many days have you had these symptoms?",
        "What is your temperature?",
        "Is your cough dry or producing mucus?",
        "Are you having trouble breathing?"
    ],

    "cardiac": [
        "When did the chest pain start?",
        "Does the pain spread to your arm or jaw?",
        "Are you sweating or feeling dizzy?"
    ],

    "neurological": [
        "How severe is the headache?",
        "Do you have blurred vision?",
        "Do you feel weak or numb?"
    ],

    "gastrointestinal": [
        "Are you vomiting?",
        "Do you have diarrhea?",
        "Can you drink fluids normally?"
    ],

    "pregnancy": [
        "How many weeks pregnant are you?",
        "What is your temperature?",
        "Do you have bleeding or abdominal pain?"
    ],

    "injury": [
        "When did the injury happen?",
        "Is there bleeding?",
        "Can you move the affected area?"
    ],

    "general": [
        "How long have you had these symptoms?",
        "Are they getting worse?"
    ]
}

# Maps gap keys to human-readable follow-up questions.
# Used to convert question IDs back to displayable text.
GAP_TO_QUESTION: dict[str, str] = {
    "duration": "How long have you had these symptoms?",
    "severity": "How severe are your symptoms?",
    "symptom_detail": "Do you have any other symptoms?",
    "temperature": "What is your temperature?",
    "bleeding_detail": "How much bleeding is there?",
}

# Emergency-related gap keys — prioritized first.
_EMERGENCY_GAPS: frozenset[str] = frozenset({
    "bleeding_detail",
    "severity",
})

_MAX_FOLLOWUP_QUESTIONS = 3


def get_followup_questions(category: str) -> list[str]:
    """Return category-specific follow-up questions.

    Kept for backward compatibility.
    """
    return FOLLOWUP_QUESTIONS.get(
        category,
        FOLLOWUP_QUESTIONS["general"]
    )


def get_contextual_followups(state: ConversationState) -> list[str]:
    """Return follow-up questions based on conversation state.

    Rules:
    - Never ask about information already collected.
    - Return at most 3 highest-priority missing questions.
    - Prioritize emergency-related information first.
    - If no important information is missing, return an empty list.
    """
    # Determine which gaps are still unanswered
    answered = set(state.answered_questions)
    remaining_gaps: list[str] = [
        gap for gap in state.missing_information
        if gap not in answered
    ]

    if not remaining_gaps:
        return []

    # Sort: emergency-related gaps first, then others
    emergency_gaps = [g for g in remaining_gaps if g in _EMERGENCY_GAPS]
    other_gaps = [g for g in remaining_gaps if g not in _EMERGENCY_GAPS]
    prioritized = emergency_gaps + other_gaps

    # Convert gap keys to human-readable questions (max 3)
    questions: list[str] = []
    for gap in prioritized[:_MAX_FOLLOWUP_QUESTIONS]:
        question = GAP_TO_QUESTION.get(gap)
        if question:
            questions.append(question)

    # If we have room, fill with category-specific questions
    # that aren't already covered
    if len(questions) < _MAX_FOLLOWUP_QUESTIONS:
        for q in get_followup_questions(state.triage.category):
            if q not in questions and len(questions) < _MAX_FOLLOWUP_QUESTIONS:
                questions.append(q)

    return questions