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
    return FOLLOWUP_QUESTIONS.get(
        category,
        FOLLOWUP_QUESTIONS["general"]
    )