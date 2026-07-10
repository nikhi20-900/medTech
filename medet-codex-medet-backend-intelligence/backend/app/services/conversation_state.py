"""
Conversation state engine for the Medet triage pipeline.

Maintains structured patient context across chat turns so the AI
never re-asks information already provided.

The :class:`ConversationStateManager` uses an in-memory ``dict`` store
that can be replaced by Redis or a database without changing business
logic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.app.services.symptom_classifier import TriageContext

logger = logging.getLogger("medet.conversation_state")


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
    "symptom_progression": "duration",
    "temperature": "temperature",
    "cough_type": "symptom_detail",
    "breathing_difficulty": "symptom_detail",
    "swallowing_difficulty": "symptom_detail",
    "chest_pain_location": "severity",
    "chest_pain_radiation": "severity",
    "headache_severity": "severity",
    "vision_changes": "symptom_detail",
    "vomiting": "symptom_detail",
    "fluid_intake": "symptom_detail",
    "injury_time": "duration",
    "bleeding_amount": "bleeding_detail",
    "pregnancy_weeks": "symptom_detail",
    "medication_taken": "symptom_detail",
    "consciousness_level": "severity",
    "severe_pain": "severity",
}


def _extract_information(
    message: str,
    triage: TriageContext,
) -> dict[str, PatientFact]:
    """Extract structured patient facts from a message.

    Pulls information from the triage pipeline as well as rule-based
    heuristic matching on the message text (e.g., temperature, cough type).
    """
    facts: dict[str, PatientFact] = {}
    text = message.lower().strip()

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

    # 1. Temperature Values
    temp_match = re.search(
        r"\b(9[5-9](?:\.\d+)?|10[0-6](?:\.\d+)?|3[5-9](?:\.\d+)?|4[0-2](?:\.\d+)?)\s*(?:f|c|degree|°)?\b",
        text,
    )
    if temp_match:
        facts["temperature"] = PatientFact(
            value=temp_match.group(1),
            confidence=0.95,
            source="rule_extraction",
        )
    elif re.search(r"\b(no\s+fever|normal\s+temp|no\s+temp|normal\s+temperature|without\s+fever)\b", text):
        facts["temperature"] = PatientFact(
            value="normal",
            confidence=0.95,
            source="rule_extraction",
        )
    elif re.search(r"\b(fever|feverish|high\s+temp|high\s+temperature)\b", text):
        facts["temperature"] = PatientFact(
            value="high",
            confidence=0.90,
            source="rule_extraction",
        )

    # 2. Cough Type
    if re.search(r"\b(dry\s+cough|cough\s+is\s+dry)\b", text) or (re.search(r"\b(dry)\b", text) and "cough" in text):
        facts["cough_type"] = PatientFact(value="dry", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(wet\s+cough|cough\s+producing\s+mucus|cough\s+with\s+mucus|phlegm|mucus)\b", text):
        facts["cough_type"] = PatientFact(value="mucus", confidence=0.95, source="rule_extraction")

    # 3. Breathing Difficulty
    if re.search(r"\b(difficulty\s+breathing|short\s+of\s+breath|can't\s+breathe|cant\s+breathe|trouble\s+breathing|breathless)\b", text):
        facts["breathing_difficulty"] = PatientFact(value="yes", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(no\s+difficulty\s+breathing|breathing\s+is\s+fine|no\s+trouble\s+breathing)\b", text):
        facts["breathing_difficulty"] = PatientFact(value="no", confidence=0.95, source="rule_extraction")

    # 4. Swallowing Difficulty
    if re.search(r"\b(hard\s+to\s+swallow|painful\s+to\s+swallow|cannot\s+swallow|can't\s+swallow|hurts\s+to\s+swallow)\b", text):
        facts["swallowing_difficulty"] = PatientFact(value="yes", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(no\s+difficulty\s+swallowing|can\s+swallow|swallowing\s+is\s+fine)\b", text):
        facts["swallowing_difficulty"] = PatientFact(value="no", confidence=0.95, source="rule_extraction")

    # 5. Chest Pain Location & Radiation
    if "chest pain" in text:
        loc_match = re.search(r"\b(center|left|right|middle|side)\b", text)
        if loc_match:
            facts["chest_pain_location"] = PatientFact(value=loc_match.group(1), confidence=0.95, source="rule_extraction")
        
        rad_match = re.search(r"\b(spreads?\s+to|radiates?\s+to|goes\s+to|pain\s+in)\s*(?:my\s*)?(arm|jaw|back|shoulder)\b", text)
        if rad_match:
            facts["chest_pain_radiation"] = PatientFact(value=rad_match.group(2), confidence=0.95, source="rule_extraction")
        elif re.search(r"\b(doesn't\s+spread|no\s+radiation|does\s+not\s+spread|stay\s+in\s+chest)\b", text):
            facts["chest_pain_radiation"] = PatientFact(value="no", confidence=0.95, source="rule_extraction")

    # 6. Headache Severity
    if "headache" in text:
        sev_match = re.search(r"\b(10|[1-9])\s*(?:out\s+of\s+10)?\b", text)
        if sev_match:
            facts["headache_severity"] = PatientFact(value=sev_match.group(1), confidence=0.95, source="rule_extraction")

    # 7. Vision Changes
    if re.search(r"\b(blurred\s+vision|blurry|double\s+vision|cannot\s+see|can't\s+see|vision\s+changes)\b", text):
        facts["vision_changes"] = PatientFact(value="yes", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(no\s+vision\s+changes|vision\s+is\s+fine|normal\s+vision)\b", text):
        facts["vision_changes"] = PatientFact(value="no", confidence=0.95, source="rule_extraction")

    # 8. Vomiting & Fluid Intake
    if re.search(r"\b(vomit|vomited|vomiting|throwing\s+up|threw\s+up)\b", text):
        facts["vomiting"] = PatientFact(value="yes", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(no\s+vomiting|not\s+vomiting|haven't\s+vomited)\b", text):
        facts["vomiting"] = PatientFact(value="no", confidence=0.95, source="rule_extraction")

    if re.search(r"\b(can\s+keep\s+fluids\s+down|can\s+drink|keeping\s+fluids\s+down|drinking\s+fine)\b", text):
        facts["fluid_intake"] = PatientFact(value="yes", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(cannot\s+keep\s+fluids\s+down|can't\s+keep\s+fluids\s+down|can't\s+drink|vomiting\s+fluids)\b", text):
        facts["fluid_intake"] = PatientFact(value="no", confidence=0.95, source="rule_extraction")

    # 9. Injury Time & Bleeding Amount
    if re.search(r"\b(just\s+now|today|yesterday|hours\s+ago|mins\s+ago)\b", text):
        facts["injury_time"] = PatientFact(value=re.search(r"\b(just\s+now|today|yesterday|hours\s+ago|mins\s+ago)\b", text).group(1), confidence=0.95, source="rule_extraction")

    if re.search(r"\b(heavy|a\s+lot\s+of\s+bleeding|severe\s+bleeding|spotting|mild\s+bleeding)\b", text):
        facts["bleeding_amount"] = PatientFact(value=re.search(r"\b(heavy|a\s+lot|severe|spotting|mild)\b", text).group(1), confidence=0.95, source="rule_extraction")

    # 10. Pregnancy Weeks
    preg_match = re.search(r"\b(\d+)\s*(?:weeks|months)\b", text)
    if preg_match:
        facts["pregnancy_weeks"] = PatientFact(value=preg_match.group(1), confidence=0.95, source="rule_extraction")

    # 11. Medication Taken
    if re.search(r"\b(took\s+medication|took\s+medicine|paracetamol|ibuprofen|advil|aspirin|tylenol|pill|took\s+pills|took\s+something)\b", text):
        facts["medication_taken"] = PatientFact(value="yes", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(no\s+medication|no\s+medicine|haven't\s+taken\s+anything|took\s+nothing|no\s+pills)\b", text):
        facts["medication_taken"] = PatientFact(value="no", confidence=0.95, source="rule_extraction")

    # 12. Symptom Progression
    if re.search(r"\b(worse|getting\s+worse|worsened)\b", text):
        facts["symptom_progression"] = PatientFact(value="worse", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(better|getting\s+better|improved)\b", text):
        facts["symptom_progression"] = PatientFact(value="better", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(same|no\s+change|stayed\s+the\s+same)\b", text):
        facts["symptom_progression"] = PatientFact(value="same", confidence=0.95, source="rule_extraction")

    # 13. Consciousness Level & Severe Pain (Emergency)
    if re.search(r"\b(alert|oriented|awake|conscious)\b", text):
        facts["consciousness_level"] = PatientFact(value="alert", confidence=0.95, source="rule_extraction")
    elif re.search(r"\b(confused|dizzy|sleepy|fainting|unresponsive|passing\s+out)\b", text):
        facts["consciousness_level"] = PatientFact(value="impaired", confidence=0.95, source="rule_extraction")

    if re.search(r"\b(severe\s+pain|unbearable\s+pain|worst\s+pain|very\s+painful|10/10\s+pain)\b", text):
        facts["severe_pain"] = PatientFact(value="yes", confidence=0.95, source="rule_extraction")

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

        # Add debug logging showing collected_information
        info_dict = {k: v.value for k, v in state.collected_information.items()}
        logger.info(f"[DEBUG] Conversation {conversation_id} Turn {turn} collected_information: {info_dict}")

        return state

    def clear(self, conversation_id: str) -> None:
        """Remove conversation state."""
        self._store.pop(conversation_id, None)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

state_manager = ConversationStateManager()
