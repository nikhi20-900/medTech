"""
Tests for the deterministic follow-up question prioritizer.

Covers:
- Already-answered filtering (temperature, duration, cough_type, multi-fact)
- Prerequisite filtering (cough_type, chest_pain_radiation, pregnancy_weeks)
- Clinical priority ordering
- Emergency override
- Group diversity
- Deterministic output
- No duplicate questions
- Empty state / fully populated state
"""

from __future__ import annotations

# pyrefly: ignore [missing-import]
import pytest

from backend.app.services.conversation_state import (
    ConversationState,
    PatientFact,
)
from backend.app.services.followup_question_bank import (
    QUESTION_BANK,
    FollowupQuestion,
)
from backend.app.services.followup_questions import get_contextual_followups
from backend.app.services.question_prioritizer import QuestionPrioritizer
from backend.app.services.symptom_classifier import TriageContext


# ===================================================================
# Helpers
# ===================================================================


def _make_state(
    category: str = "general",
    symptoms: list[str] | None = None,
    collected: dict[str, str] | None = None,
    emergency: bool = False,
    missing_info: list[str] | None = None,
) -> ConversationState:
    """Build a minimal ConversationState for testing."""
    collected_info = {}
    if collected:
        for key, value in collected.items():
            collected_info[key] = PatientFact(value=value)

    if missing_info is None:
        missing_info = ["duration", "severity", "symptom_detail", "temperature", "bleeding_detail"]

    return ConversationState(
        conversation_id="test-conv",
        triage=TriageContext(
            category=category,
            symptoms=symptoms or [],
            emergency_candidate=emergency,
        ),
        collected_information=collected_info,
        missing_information=missing_info,
    )


def _ids(questions: list[FollowupQuestion]) -> list[str]:
    """Extract question IDs from a list of FollowupQuestion."""
    return [q.id for q in questions]


def _texts(questions: list[str]) -> list[str]:
    """Identity — for readability in assertions."""
    return questions


# ===================================================================
# Already-Answered Filtering
# ===================================================================


class TestAlreadyAnsweredFiltering:

    def setup_method(self) -> None:
        self.prioritizer = QuestionPrioritizer()

    def test_temperature_already_known(self) -> None:
        """Temperature in collected_information → temperature question excluded."""
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough"],
            collected={"temperature": "101°F"},
        )
        selected = self.prioritizer.select(state)
        ids = _ids(selected)
        assert "temperature" not in ids

    def test_duration_already_known(self) -> None:
        """Duration in collected_information → duration question excluded."""
        state = _make_state(
            category="respiratory",
            symptoms=["fever"],
            collected={"duration": "3 days"},
        )
        selected = self.prioritizer.select(state)
        ids = _ids(selected)
        assert "duration" not in ids

    def test_cough_type_already_known(self) -> None:
        """Cough type in collected_information → cough_type question excluded."""
        state = _make_state(
            category="respiratory",
            symptoms=["cough"],
            collected={"cough_type": "dry"},
        )
        selected = self.prioritizer.select(state)
        ids = _ids(selected)
        assert "cough_type" not in ids

    def test_only_unanswered_questions_returned(self) -> None:
        """Multiple known facts → none of their questions appear."""
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough", "sore throat"],
            collected={
                "duration": "3 days",
                "temperature": "101°F",
                "cough_type": "dry",
            },
        )
        selected = self.prioritizer.select(state)
        ids = _ids(selected)
        assert "duration" not in ids
        assert "temperature" not in ids
        assert "cough_type" not in ids
        # Should still return other unanswered questions
        assert len(selected) > 0


# ===================================================================
# Prerequisite Filtering
# ===================================================================


class TestPrerequisiteFiltering:

    def setup_method(self) -> None:
        self.prioritizer = QuestionPrioritizer()

    def test_cough_type_requires_cough_symptom(self) -> None:
        """cough_type question absent when 'cough' not in symptoms."""
        state = _make_state(
            category="respiratory",
            symptoms=["sore throat"],  # no cough
        )
        selected = self.prioritizer.select(state, max_questions=10)
        ids = _ids(selected)
        assert "cough_type" not in ids

    def test_cough_type_present_when_cough_detected(self) -> None:
        """cough_type question present when 'cough' is in symptoms."""
        state = _make_state(
            category="respiratory",
            symptoms=["cough"],
        )
        selected = self.prioritizer.select(state, max_questions=10)
        ids = _ids(selected)
        assert "cough_type" in ids

    def test_chest_pain_radiation_requires_chest_pain(self) -> None:
        """chest_pain_radiation absent without 'chest pain' symptom."""
        state = _make_state(
            category="cardiac",
            symptoms=["palpitations"],  # no chest pain
        )
        selected = self.prioritizer.select(state, max_questions=10)
        ids = _ids(selected)
        assert "chest_pain_radiation" not in ids
        assert "chest_pain_location" not in ids

    def test_pregnancy_weeks_requires_pregnant(self) -> None:
        """pregnancy_weeks absent without 'pregnant' symptom."""
        state = _make_state(
            category="pregnancy",
            symptoms=["bleeding during pregnancy"],  # no "pregnant" keyword
        )
        selected = self.prioritizer.select(state, max_questions=10)
        ids = _ids(selected)
        assert "pregnancy_weeks" not in ids


# ===================================================================
# Ordering & Priority
# ===================================================================


class TestOrderingAndPriority:

    def setup_method(self) -> None:
        self.prioritizer = QuestionPrioritizer()

    def test_questions_ordered_by_clinical_priority(self) -> None:
        """Output respects clinical_priority order (lower = first)."""
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough", "sore throat"],
        )
        selected = self.prioritizer.select(state, max_questions=10)
        priorities = [q.clinical_priority for q in selected]
        # Within each diversity pass, priorities should be non-decreasing.
        # But across passes, a lower-priority question from a new group
        # may precede a higher-priority question from a seen group.
        # Verify that at minimum the first question has the lowest
        # priority number among all selected.
        assert selected[0].clinical_priority == min(priorities)

    def test_emergency_questions_override_routine(self) -> None:
        """Emergency candidate → emergency questions appear first."""
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough"],
            emergency=True,
        )
        selected = self.prioritizer.select(state, max_questions=5)
        ids = _ids(selected)
        # Emergency questions should be present and at the front
        emergency_ids = {"consciousness_level", "severe_pain"}
        found_emergency = [q for q in selected if q.id in emergency_ids]
        assert len(found_emergency) > 0
        # All emergency questions should precede all routine questions
        emergency_indices = [ids.index(q.id) for q in found_emergency]
        routine_questions = [q for q in selected if q.id not in emergency_ids]
        if routine_questions:
            first_routine_idx = ids.index(routine_questions[0].id)
            assert all(ei < first_routine_idx for ei in emergency_indices)

    def test_deterministic_output(self) -> None:
        """Running 100× with identical input → identical output."""
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough", "sore throat"],
        )
        first_run = self.prioritizer.select(state)
        first_ids = _ids(first_run)

        for _ in range(99):
            run = self.prioritizer.select(state)
            assert _ids(run) == first_ids


# ===================================================================
# Group Diversity
# ===================================================================


class TestGroupDiversity:

    def setup_method(self) -> None:
        self.prioritizer = QuestionPrioritizer()

    def test_group_diversity_no_same_group_cluster(self) -> None:
        """When 3+ groups eligible, result spans ≥2 distinct groups."""
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough", "sore throat"],
        )
        selected = self.prioritizer.select(state, max_questions=3)
        groups = {q.group for q in selected}
        assert len(groups) >= 2, (
            f"Expected ≥2 distinct groups, got {groups}"
        )

    def test_single_group_fallback(self) -> None:
        """When only 1 group eligible, still returns valid questions."""
        # Cardiac with chest pain → mostly cardiac group
        state = _make_state(
            category="cardiac",
            symptoms=["chest pain"],
        )
        selected = self.prioritizer.select(state, max_questions=3)
        assert len(selected) > 0
        # Should still work without crashing
        ids = _ids(selected)
        assert len(ids) == len(set(ids))  # no duplicates


# ===================================================================
# Edge Cases
# ===================================================================


class TestEdgeCases:

    def setup_method(self) -> None:
        self.prioritizer = QuestionPrioritizer()

    def test_no_duplicate_questions(self) -> None:
        """Every returned question text and ID is unique."""
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough", "sore throat"],
        )
        selected = self.prioritizer.select(state, max_questions=10)
        ids = _ids(selected)
        texts = [q.text for q in selected]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"
        assert len(texts) == len(set(texts)), f"Duplicate texts: {texts}"

    def test_empty_state(self) -> None:
        """Fresh state with no facts → returns highest-priority universal questions."""
        state = _make_state(category="general", symptoms=[])
        selected = self.prioritizer.select(state)
        assert len(selected) > 0
        # Duration (priority 1, universal) should be among them
        ids = _ids(selected)
        assert "duration" in ids

    def test_fully_populated_state(self) -> None:
        """All facts known → returns empty list."""
        # Collect every possible required_fact from the bank
        all_facts = {q.required_fact: "known" for q in QUESTION_BANK}
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough", "sore throat"],
            collected=all_facts,
        )
        selected = self.prioritizer.select(state)
        assert selected == []


# ===================================================================
# Integration: get_contextual_followups (string API)
# ===================================================================


class TestContextualFollowupsIntegration:
    """Verify the public string API delegates correctly."""

    def test_returns_strings(self) -> None:
        state = _make_state(
            category="respiratory",
            symptoms=["sore throat"],
        )
        result = get_contextual_followups(state)
        assert isinstance(result, list)
        assert all(isinstance(q, str) for q in result)
        assert len(result) <= 3

    def test_max_questions_respected(self) -> None:
        state = _make_state(
            category="respiratory",
            symptoms=["fever", "cough", "sore throat"],
        )
        result = get_contextual_followups(state, max_questions=2)
        assert len(result) <= 2

    def test_sore_throat_scenario(self) -> None:
        """'I have a sore throat' → symptom-specific questions, not generic."""
        state = _make_state(
            category="respiratory",
            symptoms=["sore throat"],
        )
        # With default max_questions=3, group diversity picks one per group:
        # timeline (duration), respiratory (breathing_difficulty), vitals (temperature)
        result_3 = get_contextual_followups(state, max_questions=3)
        # Should NOT include generic questions
        assert not any("how severe are your symptoms" in q.lower() for q in result_3)
        assert not any("any other symptoms" in q.lower() for q in result_3)
        # Duration should be first (priority 1, timeline group)
        assert "How long have you had these symptoms?" in result_3

        # With more slots, swallowing difficulty (prerequisite: sore throat)
        # should appear once its group gets a second slot
        result_5 = get_contextual_followups(state, max_questions=5)
        assert any("swallow" in q.lower() for q in result_5)


class TestPersistenceRegression:
    """Verify follow-up answers are extracted and never asked again."""

    def test_three_turn_persistence(self) -> None:
        from backend.app.services.conversation_state import ConversationStateManager
        from backend.app.services.symptom_classifier import classify_symptom

        mgr = ConversationStateManager()
        conv_id = "test-persistence-3-turn"

        # Turn 1: User introduces symptoms (no fever, so temperature is missing)
        triage1 = classify_symptom("I have a sore throat.")
        state1 = mgr.update(conv_id, "I have a sore throat.", triage1)

        # Get follow-up questions
        questions1 = get_contextual_followups(state1)
        # Should ask about duration and temperature
        assert any("how long" in q.lower() for q in questions1)
        assert any("temperature" in q.lower() for q in questions1)

        # Turn 2: User answers both duration and temperature
        triage2 = classify_symptom("It started 2 days ago. No fever.")
        state2 = mgr.update(conv_id, "It started 2 days ago. No fever.", triage2)

        # Verify facts are extracted and merged
        assert "duration" in state2.collected_information
        assert "temperature" in state2.collected_information
        assert state2.collected_information["temperature"].value == "normal"

        # Verify they are not asked again
        questions2 = get_contextual_followups(state2)
        assert not any("how long" in q.lower() for q in questions2)
        assert not any("temperature" in q.lower() for q in questions2)

        # Turn 3: Further user response, check they still persist and aren't re-asked
        triage3 = classify_symptom("No other symptoms.")
        state3 = mgr.update(conv_id, "No other symptoms.", triage3)

        assert "duration" in state3.collected_information
        assert "temperature" in state3.collected_information

        questions3 = get_contextual_followups(state3)
        assert not any("how long" in q.lower() for q in questions3)
        assert not any("temperature" in q.lower() for q in questions3)
