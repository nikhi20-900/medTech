"""
Triage prompt builder for the Medet triage pipeline.

Converts triage and conversation context into a structured prompt
string that is appended to the Ollama system instruction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.services.conversation_state import ConversationState
    from backend.app.services.response_policy import ResponsePolicyContext
    from backend.app.services.symptom_classifier import TriageContext



def build_triage_prompt(ctx: TriageContext) -> str:
    """Build the structured context block for the system instruction.

    The output is designed to give the LLM maximum structured context
    about the patient's situation so it can respond with relevant,
    compassionate healthcare guidance.

    .. note::
        Prefer :func:`build_stateful_triage_prompt` when conversation
        state is available.
    """
    parts: list[str] = ["\n"]

    # Category
    parts.append(f"Detected Category:\n{ctx.category}\n")

    # Symptoms
    if ctx.symptoms:
        symptom_lines = "\n".join(f"- {s.title()}" for s in ctx.symptoms)
        parts.append(f"Detected Symptoms:\n{symptom_lines}\n")
    else:
        parts.append("Detected Symptoms:\n- None identified\n")

    # Severity
    parts.append(f"Severity:\n{ctx.severity}\n")

    # Duration
    parts.append(f"Duration:\n{ctx.duration or 'Not specified'}\n")

    # Emergency candidate
    parts.append(f"Emergency Candidate:\n{ctx.emergency_candidate}\n")

    # Confidence
    parts.append(f"Confidence:\n{ctx.confidence}\n")

    # Missing information
    if ctx.missing_info:
        missing_lines = "\n".join(f"- {gap}" for gap in ctx.missing_info)
        parts.append(f"Missing Information:\n{missing_lines}\n")

    # Follow-up questions
    if ctx.followup_questions:
        question_lines = "\n".join(
            f"{i + 1}. {q}" for i, q in enumerate(ctx.followup_questions)
        )
        parts.append(f"Preferred Follow-up Questions:\n{question_lines}\n")

    parts.append("Use these questions whenever information is missing.")

    return "\n".join(parts)


def build_stateful_triage_prompt(state: ConversationState) -> str:
    """Build a context-aware prompt from conversation state.

    Includes:
    - Current triage context (category, symptoms, severity, etc.)
    - Information already collected from the patient
    - Remaining missing information
    - Follow-up questions (max 3, filtered)
    - Explicit instruction to NOT re-ask answered questions
    """
    ctx = state.triage
    parts: list[str] = ["\n"]

    # Category
    parts.append(f"Detected Category:\n{ctx.category}\n")

    # Symptoms
    if ctx.symptoms:
        symptom_lines = "\n".join(f"- {s.title()}" for s in ctx.symptoms)
        parts.append(f"Detected Symptoms:\n{symptom_lines}\n")
    else:
        parts.append("Detected Symptoms:\n- None identified\n")

    # Severity
    parts.append(f"Severity:\n{ctx.severity}\n")

    # Duration
    parts.append(f"Duration:\n{ctx.duration or 'Not specified'}\n")

    # Emergency candidate
    parts.append(f"Emergency Candidate:\n{ctx.emergency_candidate}\n")

    # Confidence
    parts.append(f"Confidence:\n{ctx.confidence}\n")

    # Conversation turn
    parts.append(f"Conversation Turn:\n{state.turn_count}\n")

    # Collected information (what the patient has already told us)
    if state.collected_information:
        info_lines = "\n".join(
            f"- {key}: {fact.value}"
            for key, fact in state.collected_information.items()
        )
        parts.append(
            f"Information Already Collected (DO NOT ask again):\n{info_lines}\n"
        )

    # Remaining missing information
    if state.missing_information:
        missing_lines = "\n".join(
            f"- {gap}" for gap in state.missing_information
        )
        parts.append(f"Still Missing:\n{missing_lines}\n")

    # Follow-up questions
    from backend.app.services.followup_questions import get_contextual_followups

    questions = get_contextual_followups(state)
    if questions:
        question_lines = "\n".join(
            f"{i + 1}. {q}" for i, q in enumerate(questions)
        )
        parts.append(f"Preferred Follow-up Questions:\n{question_lines}\n")
    else:
        parts.append("No follow-up questions needed.\n")

    parts.append(
        "IMPORTANT: Do NOT ask about information already collected above. "
        "Only ask the follow-up questions listed."
    )

    return "\n".join(parts)


def build_policy_aware_prompt(
    state: ConversationState,
    policy_ctx: ResponsePolicyContext,
) -> str:
    """Build a policy-driven prompt from conversation state.

    Unlike :func:`build_stateful_triage_prompt`, this function
    receives a pre-determined :class:`ResponsePolicyContext` and
    injects the policy's constraints and response template into the
    prompt.  The prompt builder only *formats* — it never *decides*
    the policy.

    Includes:
    - Current triage context (category, symptoms, severity, etc.)
    - Information already collected from the patient
    - Remaining missing information
    - Filtered follow-up questions
    - **Response policy directives** (template + enforcement rules)
    """
    from backend.app.services.followup_questions import get_contextual_followups
    from backend.app.services.response_templates import get_response_template

    ctx = state.triage
    parts: list[str] = ["\n"]

    # ---- Triage context block (same as build_stateful_triage_prompt) ----

    # Category
    parts.append(f"Detected Category:\n{ctx.category}\n")

    # Symptoms
    if ctx.symptoms:
        symptom_lines = "\n".join(f"- {s.title()}" for s in ctx.symptoms)
        parts.append(f"Detected Symptoms:\n{symptom_lines}\n")
    else:
        parts.append("Detected Symptoms:\n- None identified\n")

    # Severity
    parts.append(f"Severity:\n{ctx.severity}\n")

    # Duration
    parts.append(f"Duration:\n{ctx.duration or 'Not specified'}\n")

    # Emergency candidate
    parts.append(f"Emergency Candidate:\n{ctx.emergency_candidate}\n")

    # Confidence
    parts.append(f"Confidence:\n{ctx.confidence}\n")

    # Conversation turn
    parts.append(f"Conversation Turn:\n{state.turn_count}\n")

    # Collected information
    if state.collected_information:
        info_lines = "\n".join(
            f"- {key}: {fact.value}"
            for key, fact in state.collected_information.items()
        )
        parts.append(
            f"Information Already Collected (DO NOT ask again):\n{info_lines}\n"
        )

    # Remaining missing information
    if state.missing_information:
        missing_lines = "\n".join(
            f"- {gap}" for gap in state.missing_information
        )
        parts.append(f"Still Missing:\n{missing_lines}\n")

    # Follow-up questions
    questions = get_contextual_followups(state)
    if questions:
        question_lines = "\n".join(
            f"{i + 1}. {q}" for i, q in enumerate(questions)
        )
        parts.append(f"Preferred Follow-up Questions:\n{question_lines}\n")
    else:
        parts.append("No follow-up questions needed.\n")

    # ---- Policy directives block (NEW) ----

    parts.append("--- RESPONSE POLICY DIRECTIVES ---\n")
    parts.append(get_response_template(policy_ctx))
    parts.append(
        "\nENFORCEMENT:\n"
        "- Follow the response structure above exactly.\n"
        "- Never change the response template.\n"
        f"- Stay within {policy_ctx.max_response_words} words.\n"
        f"- Never ask more than {policy_ctx.max_questions} questions.\n"
        "- Follow the backend policy exactly.\n"
        "- Do NOT ask about information already collected above.\n"
        "- Only ask the follow-up questions listed.\n"
    )

    return "\n".join(parts)
