"""
Conversation state rules for the Medet triage pipeline.

This module contains decision-making functions that operate on
:class:`~backend.app.services.conversation_state.ConversationState`.

All functions are **stubs** — real logic will be added in a future
sprint.  The ``ConversationStateManager`` should only store/update
state; all decision logic belongs here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.services.conversation_state import (
        ConversationStage,
        ConversationState,
    )


def determine_stage(state: ConversationState) -> ConversationStage:
    """Determine the current conversation stage based on state.

    .. note:: Stub — always returns the current stage unchanged.
    """
    return state.stage


def prioritize_missing_information(state: ConversationState) -> list[str]:
    """Rank missing information by clinical priority.

    .. note:: Stub — returns missing_information as-is.
    """
    return list(state.missing_information)


def select_next_questions(state: ConversationState) -> list[str]:
    """Select the next question IDs to ask the patient.

    .. note:: Stub — returns up to 3 from missing_information.
    """
    return list(state.missing_information[:3])
