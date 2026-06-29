"""
Response templates for the Medet triage pipeline.

Provides structured prompt instruction text for each
:class:`~backend.app.services.response_policy.ResponsePolicy`.

All constraint values (max_questions, allow_self_care, etc.) are read
from the :class:`~backend.app.services.response_policy.ResponsePolicyContext`
dataclass — **not** hardcoded in the template strings.  This ensures
:class:`ResponsePolicyContext` remains the single source of truth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.services.response_policy import ResponsePolicyContext

from backend.app.services.response_policy import ResponsePolicy


# ---------------------------------------------------------------------------
# Template builders — one per policy
# ---------------------------------------------------------------------------


def _routine_template(ctx: ResponsePolicyContext) -> str:
    return (
        f"Current Response Policy: ROUTINE\n"
        f"\n"
        f"Response Structure:\n"
        f"1. Acknowledge the patient's concern with empathy.\n"
        f"2. Provide a brief medical explanation.\n"
        f"3. Ask up to {ctx.max_questions} follow-up questions to gather more information.\n"
        f"4. Offer practical self-care advice.\n"
        f"5. Include a general emergency warning at the end.\n"
        f"\n"
        f"Response Rules:\n"
        f"- Maximum questions: {ctx.max_questions}\n"
        f"- Self-care advice: ALLOWED\n"
        f"- Home remedies: ALLOWED\n"
        f"- Doctor visit recommendation: NOT REQUIRED\n"
        f"- Maximum response length: {ctx.max_response_words} words\n"
    )


def _urgent_template(ctx: ResponsePolicyContext) -> str:
    return (
        f"Current Response Policy: URGENT\n"
        f"\n"
        f"Response Structure:\n"
        f"1. Acknowledge the patient's concern with empathy.\n"
        f"2. Clearly explain why their symptoms are concerning.\n"
        f"3. Ask up to {ctx.max_questions} focused follow-up questions.\n"
        f"4. Recommend scheduling a medical evaluation soon.\n"
        f"\n"
        f"Response Rules:\n"
        f"- Maximum questions: {ctx.max_questions}\n"
        f"- Self-care advice: NOT ALLOWED\n"
        f"- Home remedies: NOT ALLOWED\n"
        f"- Doctor visit recommendation: REQUIRED\n"
        f"- Maximum response length: {ctx.max_response_words} words\n"
    )


def _emergency_template(ctx: ResponsePolicyContext) -> str:
    return (
        f"Current Response Policy: EMERGENCY\n"
        f"\n"
        f"Response Structure:\n"
        f"1. Issue an IMMEDIATE medical warning.\n"
        f"2. Ask at most {ctx.max_questions} critical clarifying questions.\n"
        f"3. Provide clear, immediate action steps.\n"
        f"\n"
        f"Response Rules:\n"
        f"- Maximum questions: {ctx.max_questions}\n"
        f"- Self-care advice: NOT ALLOWED\n"
        f"- Home remedies: NOT ALLOWED\n"
        f"- Reassurance: NOT ALLOWED — do NOT downplay symptoms\n"
        f"- Doctor visit recommendation: REQUIRED — recommend emergency services\n"
        f"- Maximum response length: {ctx.max_response_words} words\n"
        f"- Do NOT use phrases like 'don't worry', 'it's probably nothing', "
        f"or 'this is likely harmless'.\n"
    )


def _follow_up_template(ctx: ResponsePolicyContext) -> str:
    return (
        f"Current Response Policy: FOLLOW_UP\n"
        f"\n"
        f"Response Structure:\n"
        f"1. Briefly summarize the information collected so far.\n"
        f"2. Ask up to {ctx.max_questions} remaining follow-up questions.\n"
        f"3. Provide updated advice based on all collected information.\n"
        f"\n"
        f"Response Rules:\n"
        f"- Maximum questions: {ctx.max_questions}\n"
        f"- Self-care advice: ALLOWED\n"
        f"- Home remedies: ALLOWED\n"
        f"- Do NOT repeat questions the patient has already answered.\n"
        f"- Maximum response length: {ctx.max_response_words} words\n"
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_TEMPLATE_BUILDERS: dict[ResponsePolicy, object] = {
    ResponsePolicy.ROUTINE: _routine_template,
    ResponsePolicy.URGENT: _urgent_template,
    ResponsePolicy.EMERGENCY: _emergency_template,
    ResponsePolicy.FOLLOW_UP: _follow_up_template,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_response_template(policy_ctx: ResponsePolicyContext) -> str:
    """Return the structured prompt instruction text for *policy_ctx*.

    Constraint values (max_questions, allow_self_care, etc.) are
    interpolated from the dataclass — not hardcoded.
    """
    builder = _TEMPLATE_BUILDERS.get(policy_ctx.policy)
    if builder is None:
        raise ValueError(f"No template for policy: {policy_ctx.policy!r}")
    return builder(policy_ctx)  # type: ignore[operator]
