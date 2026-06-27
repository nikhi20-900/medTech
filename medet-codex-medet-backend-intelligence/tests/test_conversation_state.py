"""
Tests for the Medet conversation state engine.

Covers:
- ConversationStateManager CRUD operations
- State persistence across turns
- PatientFact merge logic (never overwrite with None)
- Multi-turn conversation scenario from spec
- Contextual follow-up filtering
- Stateful prompt builder output
"""

from __future__ import annotations

import pytest

from backend.app.services.conversation_state import (
    ConversationStage,
    ConversationState,
    ConversationStateManager,
    PatientFact,
    state_manager,
)
from backend.app.services.conversation_state_rules import (
    determine_stage,
    prioritize_missing_information,
    select_next_questions,
)
from backend.app.services.followup_questions import (
    get_contextual_followups,
    get_followup_questions,
)
from backend.app.services.symptom_classifier import TriageContext, classify_symptom
from backend.app.services.triage_prompt_builder import (
    build_stateful_triage_prompt,
    build_triage_prompt,
)


# ===================================================================
# ConversationStateManager CRUD
# ===================================================================


class TestStateManagerCRUD:

    def setup_method(self) -> None:
        self.mgr = ConversationStateManager()

    def test_create(self) -> None:
        state = self.mgr.create("conv-1")
        assert state.conversation_id == "conv-1"
        assert state.triage.category == "general"
        assert state.collected_information == {}
        assert state.turn_count == 0
        assert state.stage == ConversationStage.COLLECTING

    def test_get_existing(self) -> None:
        self.mgr.create("conv-2")
        state = self.mgr.get("conv-2")
        assert state is not None
        assert state.conversation_id == "conv-2"

    def test_get_nonexistent(self) -> None:
        assert self.mgr.get("nope") is None

    def test_clear(self) -> None:
        self.mgr.create("conv-3")
        self.mgr.clear("conv-3")
        assert self.mgr.get("conv-3") is None

    def test_clear_nonexistent_no_error(self) -> None:
        self.mgr.clear("nope")  # should not raise


# ===================================================================
# State Update & Persistence
# ===================================================================


class TestStateUpdate:

    def setup_method(self) -> None:
        self.mgr = ConversationStateManager()

    def test_first_turn_creates_state(self) -> None:
        triage = classify_symptom("I have fever and cough")
        state = self.mgr.update("conv-10", "I have fever and cough", triage)
        assert state.conversation_id == "conv-10"
        assert state.turn_count == 1
        assert "symptoms" in state.collected_information

    def test_turn_count_increments(self) -> None:
        triage1 = classify_symptom("I have fever")
        state1 = self.mgr.update("conv-11", "I have fever", triage1)
        assert state1.turn_count == 1

        triage2 = classify_symptom("for 3 days")
        state2 = self.mgr.update("conv-11", "for 3 days", triage2)
        assert state2.turn_count == 2

    def test_collected_info_persists_across_turns(self) -> None:
        triage1 = classify_symptom("I have fever and cough")
        state1 = self.mgr.update("conv-12", "I have fever and cough", triage1)
        assert "symptoms" in state1.collected_information

        # Second turn adds duration
        triage2 = classify_symptom("for 3 days")
        state2 = self.mgr.update("conv-12", "for 3 days", triage2)

        # Both symptoms AND duration should be present
        assert "symptoms" in state2.collected_information
        assert "duration" in state2.collected_information
        assert state2.collected_information["duration"].value == "3 days"

    def test_never_overwrite_with_none(self) -> None:
        # First turn provides severity
        triage1 = classify_symptom("I have severe headache")
        state1 = self.mgr.update("conv-13", "I have severe headache", triage1)
        assert "severity" in state1.collected_information

        # Second turn has no severity info (low = default = not stored)
        triage2 = classify_symptom("also some cough")
        state2 = self.mgr.update("conv-13", "also some cough", triage2)

        # Severity from turn 1 should still be there
        assert "severity" in state2.collected_information
        assert state2.collected_information["severity"].value == "high"

    def test_stage_initializes_to_collecting(self) -> None:
        triage = classify_symptom("I have fever")
        state = self.mgr.update("conv-14", "I have fever", triage)
        assert state.stage == ConversationStage.COLLECTING


# ===================================================================
# PatientFact
# ===================================================================


class TestPatientFact:

    def test_default_values(self) -> None:
        fact = PatientFact(value="101°F")
        assert fact.confidence == 1.0
        assert fact.source == "user"

    def test_custom_values(self) -> None:
        fact = PatientFact(value="3 days", confidence=0.95, source="triage_pipeline")
        assert fact.value == "3 days"
        assert fact.confidence == 0.95
        assert fact.source == "triage_pipeline"


# ===================================================================
# Multi-turn Conversation (Spec Test Case)
# ===================================================================


class TestMultiTurnConversation:
    """Test case from state engine.md spec."""

    def setup_method(self) -> None:
        self.mgr = ConversationStateManager()

    def test_spec_scenario(self) -> None:
        # Turn 1: "I have fever and cough."
        triage1 = classify_symptom("I have fever and cough.")
        state1 = self.mgr.update("spec-conv", "I have fever and cough.", triage1)

        assert state1.triage.category == "respiratory"
        assert "fever" in state1.triage.symptoms
        assert "cough" in state1.triage.symptoms

        # Duration should be missing
        assert "duration" in state1.missing_information

        # Turn 2: "3 days. 101°F. Dry cough."
        # Note: temperature and cough_type extraction is stubbed,
        # but duration will be picked up by the triage pipeline.
        triage2 = classify_symptom("3 days. 101°F. Dry cough.")
        state2 = self.mgr.update("spec-conv", "3 days. 101°F. Dry cough.", triage2)

        # Duration should now be collected
        assert "duration" in state2.collected_information
        assert state2.collected_information["duration"].value == "3 days"

        # Duration should be answered
        assert "duration" in state2.answered_questions

        # Duration should NOT be in missing_information anymore
        assert "duration" not in state2.missing_information

        # Turn count
        assert state2.turn_count == 2


# ===================================================================
# Contextual Follow-ups with State
# ===================================================================


class TestContextualFollowupsWithState:

    def setup_method(self) -> None:
        self.mgr = ConversationStateManager()

    def test_max_3_questions(self) -> None:
        triage = classify_symptom("I have fever")
        state = self.mgr.update("fup-1", "I have fever", triage)
        questions = get_contextual_followups(state)
        assert len(questions) <= 3

    def test_no_questions_when_nothing_missing(self) -> None:
        state = ConversationState(
            conversation_id="fup-2",
            triage=TriageContext(category="general"),
            missing_information=[],
            answered_questions=[],
        )
        questions = get_contextual_followups(state)
        assert questions == []

    def test_backward_compat_get_followup_questions(self) -> None:
        questions = get_followup_questions("respiratory")
        assert len(questions) > 0
        assert "What is your temperature?" in questions


# ===================================================================
# Stateful Prompt Builder
# ===================================================================


class TestStatefulPromptBuilder:

    def setup_method(self) -> None:
        self.mgr = ConversationStateManager()

    def test_contains_collected_info(self) -> None:
        triage = classify_symptom("I have fever for 3 days")
        state = self.mgr.update("prompt-1", "I have fever for 3 days", triage)
        prompt = build_stateful_triage_prompt(state)
        assert "Information Already Collected" in prompt
        assert "DO NOT ask again" in prompt

    def test_contains_missing_info(self) -> None:
        triage = classify_symptom("I have fever")
        state = self.mgr.update("prompt-2", "I have fever", triage)
        prompt = build_stateful_triage_prompt(state)
        assert "Still Missing:" in prompt

    def test_contains_turn_count(self) -> None:
        triage = classify_symptom("I have fever")
        state = self.mgr.update("prompt-3", "I have fever", triage)
        prompt = build_stateful_triage_prompt(state)
        assert "Conversation Turn:" in prompt
        assert "1" in prompt

    def test_old_builder_still_works(self) -> None:
        ctx = classify_symptom("I have fever and cough")
        prompt = build_triage_prompt(ctx)
        assert "Detected Category:" in prompt
        assert "Detected Symptoms:" in prompt


# ===================================================================
# Conversation State Rules (Stubs)
# ===================================================================


class TestConversationStateRules:
    """Verify stubs don't crash and return reasonable defaults."""

    def test_determine_stage(self) -> None:
        state = ConversationState(
            conversation_id="rule-1",
            triage=TriageContext(category="respiratory"),
        )
        stage = determine_stage(state)
        assert stage == ConversationStage.COLLECTING

    def test_prioritize_missing_information(self) -> None:
        state = ConversationState(
            conversation_id="rule-2",
            triage=TriageContext(category="respiratory"),
            missing_information=["duration", "severity"],
        )
        result = prioritize_missing_information(state)
        assert result == ["duration", "severity"]

    def test_select_next_questions(self) -> None:
        state = ConversationState(
            conversation_id="rule-3",
            triage=TriageContext(category="respiratory"),
            missing_information=["duration", "severity", "temperature", "extra"],
        )
        result = select_next_questions(state)
        assert len(result) <= 3
