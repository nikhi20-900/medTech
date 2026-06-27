"""
Conversation state engine for the Medet triage pipeline.

Maintains structured patient context across chat turns so the AI
never re-asks information already provided.

The :class:`ConversationStateManager` uses an in-memory ``dict`` store
that can be replaced by Redis or a database without changing business
logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.app.services.symptom_classifier import TriageContext


# ---------------------------------------------------------------------------
# PatientFact — typed wrapper for collected information
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientFact:
    """A single piece of information collected from the patient."""

    value: Any
    confidence: float = 1.0
    source: str = "user"


# ---------------------------------------------------------------------------
# ConversationStage — conversation lifecycle stages
# ---------------------------------------------------------------------------


class ConversationStage(Enum):
    """Stages of a healthcare conversation."""

    COLLECTING = "collecting"
    TRIAGE = "triage"
    ADVICE = "advice"
    EMERGENCY = "emergency"
    FOLLOW_UP = "follow_up"
    COMPLETE = "complete"


# ---------------------------------------------------------------------------
# ConversationState — frozen snapshot of patient context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConversationState:
    """Immutable snapshot of the conversation at a given turn."""

    conversation_id: str
    triage: TriageContext
    collected_information: dict[str, PatientFact] = field(default_factory=dict)
    missing_information: list[str] = field(default_factory=list)
    asked_questions: list[str] = field(default_factory=list)
    answered_questions: list[str] = field(default_factory=list)
    stage: ConversationStage = ConversationStage.COLLECTING
    turn_count: int = 0
    last_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Information extraction (stub — real logic deferred)
# ---------------------------------------------------------------------------

# Question ID → gap key mapping.  Used to determine which questions
# are answered when a collected_information key is present.

QUESTION_ID_TO_GAP: dict[str, str] = {
    "duration": "duration",
    "temperature": "temperature",
    "cough_type": "symptom_detail",
    "severity": "severity",
    "bleeding_detail": "bleeding_detail",
    "breathing_difficulty": "symptom_detail",
}


def _extract_information(
    message: str,
    triage: TriageContext,
) -> dict[str, PatientFact]:
    """Extract structured patient facts from a message.

    .. note::
        This is a **stub**.  Real extraction logic (temperature regex,
        cough type detection, etc.) will be added later.  For now it
        pulls only what the triage pipeline already provides.
    """
    facts: dict[str, PatientFact] = {}

    # Pull duration from triage (already extracted by duration_detector)
    if triage.duration is not None:
        facts["duration"] = PatientFact(
            value=triage.duration,
            confidence=0.95,
            source="triage_pipeline",
        )

    # Pull severity if not low (low is the default / ambiguous)
    if triage.severity != "low":
        facts["severity"] = PatientFact(
            value=triage.severity,
            confidence=0.90,
            source="triage_pipeline",
        )

    # Pull detected symptoms
    if triage.symptoms:
        facts["symptoms"] = PatientFact(
            value=triage.symptoms,
            confidence=triage.confidence,
            source="triage_pipeline",
        )

    # Pull category
    if triage.category != "general":
        facts["category"] = PatientFact(
            value=triage.category,
            confidence=triage.confidence,
            source="triage_pipeline",
        )

    return facts


# ---------------------------------------------------------------------------
# ConversationStateManager
# ---------------------------------------------------------------------------


class ConversationStateManager:
    """In-memory conversation state store.

    The public API (``create``, ``get``, ``update``, ``clear``) is
    intentionally minimal so the store backend can be swapped to Redis
    or a database without touching business logic.
    """

    def __init__(self) -> None:
        self._store: dict[str, ConversationState] = {}

    # -- public API ---------------------------------------------------------

    def create(self, conversation_id: str) -> ConversationState:
        """Create a fresh conversation state."""
        state = ConversationState(
            conversation_id=conversation_id,
            triage=TriageContext(category="general"),
        )
        self._store[conversation_id] = state
        return state

    def get(self, conversation_id: str) -> ConversationState | None:
        """Retrieve existing state, or ``None`` if not found."""
        return self._store.get(conversation_id)

    def update(
        self,
        conversation_id: str,
        message: str,
        triage: TriageContext,
    ) -> ConversationState:
        """Update (or create) conversation state with a new turn.

        1. Extract new facts from the message.
        2. Merge into existing collected_information (never overwrite
           with ``None``).
        3. Recompute missing_information.
        4. Track asked / answered question IDs.
        5. Return a new frozen :class:`ConversationState`.
        """
        previous = self._store.get(conversation_id)

        # --- Extract new facts from this turn ---
        new_facts = _extract_information(message, triage)

        # --- Merge with previous collected information ---
        if previous is not None:
            merged = dict(previous.collected_information)
        else:
            merged = {}

        for key, fact in new_facts.items():
            # Never overwrite existing values with None
            if fact.value is not None:
                merged[key] = fact

        # --- Determine answered question IDs ---
        previously_answered: list[str] = (
            list(previous.answered_questions) if previous else []
        )
        newly_answered: list[str] = []
        for qid, gap_key in QUESTION_ID_TO_GAP.items():
            if qid in merged and qid not in previously_answered:
                newly_answered.append(qid)

        all_answered = previously_answered + newly_answered

        # --- Compute remaining missing information ---
        all_gaps = list(triage.missing_info)
        remaining_missing: list[str] = []
        for gap in all_gaps:
            # If any question ID that maps to this gap has been answered,
            # consider it resolved.
            answered_for_gap = any(
                qid in all_answered
                for qid, gk in QUESTION_ID_TO_GAP.items()
                if gk == gap
            )
            if not answered_for_gap:
                remaining_missing.append(gap)

        # --- Track asked questions (from triage follow-ups) ---
        previously_asked: list[str] = (
            list(previous.asked_questions) if previous else []
        )
        # Map follow-up questions to IDs based on gap keys
        newly_asked: list[str] = [
            gap for gap in remaining_missing if gap not in previously_asked
        ]
        all_asked = list(dict.fromkeys(previously_asked + newly_asked))

        # --- Build new state ---
        turn = (previous.turn_count + 1) if previous else 1

        state = ConversationState(
            conversation_id=conversation_id,
            triage=triage,
            collected_information=merged,
            missing_information=remaining_missing,
            asked_questions=all_asked,
            answered_questions=all_answered,
            stage=ConversationStage.COLLECTING,
            turn_count=turn,
            last_updated=datetime.now(timezone.utc),
        )

        self._store[conversation_id] = state
        return state

    def clear(self, conversation_id: str) -> None:
        """Remove conversation state."""
        self._store.pop(conversation_id, None)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

state_manager = ConversationStateManager()
