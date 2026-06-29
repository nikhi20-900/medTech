"""
Deterministic response policy rules for the Medet triage pipeline.

The single entry point :func:`determine_response_policy` inspects a
:class:`~backend.app.services.conversation_state.ConversationState`
and returns a :class:`~backend.app.services.response_policy.ResponsePolicyContext`
with the selected policy **and** its concrete constraints.

Rule chain (evaluated top-to-bottom, first match wins):

1. ``emergency_candidate == True`` OR ``stage == EMERGENCY``  →  EMERGENCY
2. ``severity == "high"``                                      →  URGENT
3. ``stage == FOLLOW_UP`` OR ``answered_questions > 0``        →  FOLLOW_UP
4. Otherwise                                                   →  ROUTINE

No LLM reasoning.  All rules are deterministic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.app.services.response_policy import (
    ResponsePolicy,
    ResponsePolicyContext,
)

if TYPE_CHECKING:
    from backend.app.services.conversation_state import ConversationState


# ---------------------------------------------------------------------------
# Fixed constraint sets — one per policy
# ---------------------------------------------------------------------------

_POLICY_CONSTRAINTS: dict[ResponsePolicy, ResponsePolicyContext] = {
    ResponsePolicy.ROUTINE: ResponsePolicyContext(
        policy=ResponsePolicy.ROUTINE,
        max_questions=3,
        allow_self_care=True,
        allow_home_remedies=True,
        show_emergency_warning=True,
        require_doctor_visit=False,
        max_response_words=300,
    ),
    ResponsePolicy.URGENT: ResponsePolicyContext(
        policy=ResponsePolicy.URGENT,
        max_questions=2,
        allow_self_care=False,
        allow_home_remedies=False,
        show_emergency_warning=True,
        require_doctor_visit=True,
        max_response_words=200,
    ),
    ResponsePolicy.EMERGENCY: ResponsePolicyContext(
        policy=ResponsePolicy.EMERGENCY,
        max_questions=2,
        allow_self_care=False,
        allow_home_remedies=False,
        show_emergency_warning=True,
        require_doctor_visit=True,
        max_response_words=150,
    ),
    ResponsePolicy.FOLLOW_UP: ResponsePolicyContext(
        policy=ResponsePolicy.FOLLOW_UP,
        max_questions=2,
        allow_self_care=True,
        allow_home_remedies=True,
        show_emergency_warning=False,
        require_doctor_visit=False,
        max_response_words=250,
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def determine_response_policy(
    state: ConversationState,
) -> ResponsePolicyContext:
    """Select a response policy for the current conversation state.

    The function is **pure** — it reads only from the supplied *state*
    and returns a frozen :class:`ResponsePolicyContext`.  No side
    effects, no randomness, no LLM calls.
    """
    from backend.app.services.conversation_state import ConversationStage

    # --- Priority 1: Emergency ---
    if state.triage.emergency_candidate:
        return _POLICY_CONSTRAINTS[ResponsePolicy.EMERGENCY]

    if state.stage == ConversationStage.EMERGENCY:
        return _POLICY_CONSTRAINTS[ResponsePolicy.EMERGENCY]

    # --- Priority 2: Urgent ---
    if state.triage.severity == "high":
        return _POLICY_CONSTRAINTS[ResponsePolicy.URGENT]

    # --- Priority 3: Follow-up ---
    if state.stage == ConversationStage.FOLLOW_UP:
        return _POLICY_CONSTRAINTS[ResponsePolicy.FOLLOW_UP]

    if len(state.answered_questions) > 0:
        return _POLICY_CONSTRAINTS[ResponsePolicy.FOLLOW_UP]

    # --- Priority 4: Routine ---
    return _POLICY_CONSTRAINTS[ResponsePolicy.ROUTINE]
