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

def get_followup_questions(category: str) -> list[str]:
    """Return category-specific follow-up questions.

    Kept for backward compatibility.
    """
    return FOLLOWUP_QUESTIONS.get(
        category,
        FOLLOWUP_QUESTIONS["general"]
    )


def get_contextual_followups(
    state: ConversationState,
    max_questions: int = 3,
) -> list[str]:
    """Return follow-up questions based on conversation state.

    Delegates entirely to the deterministic
    :class:`~backend.app.services.question_prioritizer.QuestionPrioritizer`.

    Rules (enforced by the prioritizer):
    - Never ask about information already collected.
    - Return at most *max_questions* highest-priority questions.
    - Emergency questions always override routine questions.
    - Prerequisite-gated questions only appear when relevant.
    - Questions are diversified across semantic groups.
    - Same input always produces the same output.
    """
    from backend.app.services.question_prioritizer import QuestionPrioritizer

    prioritizer = QuestionPrioritizer()
    selected = prioritizer.select(state, max_questions=max_questions)
    return [q.text for q in selected]