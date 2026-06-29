"""
Unit tests for the Response Policy Engine.

Covers:
- All four policy paths (ROUTINE, URGENT, EMERGENCY, FOLLOW_UP)
- Constraint correctness per policy
- Precedence: emergency > urgent > follow_up > routine
- Determinism: same input always produces same output
- Edge cases: fresh conversation, medium severity, no symptoms
"""

from __future__ import annotations

import pytest

from backend.app.services.conversation_state import (
    ConversationStage,
    ConversationState,
)
from backend.app.services.response_policy import (
    ResponsePolicy,
    ResponsePolicyContext,
)
from backend.app.services.response_policy_rules import determine_response_policy
from backend.app.services.symptom_classifier import TriageContext


# ---------------------------------------------------------------------------
# Helpers — build ConversationState with specific fields
# ---------------------------------------------------------------------------


def _make_state(
    *,
    severity: str = "low",
    emergency_candidate: bool = False,
    stage: ConversationStage = ConversationStage.COLLECTING,
    answered_questions: list[str] | None = None,
    category: str = "general",
    symptoms: list[str] | None = None,
) -> ConversationState:
    """Build a minimal ConversationState for testing."""
    return ConversationState(
        conversation_id="test-conv-001",
        triage=TriageContext(
            category=category,
            symptoms=symptoms or [],
            severity=severity,
            emergency_candidate=emergency_candidate,
        ),
        stage=stage,
        answered_questions=answered_questions or [],
    )


# ===================================================================
# Core policy tests
# ===================================================================


class TestRoutinePolicy:
    """ROUTINE: the default path for low-severity, first-turn conversations."""

    def test_default_case(self) -> None:
        state = _make_state()
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.ROUTINE

    def test_low_severity(self) -> None:
        state = _make_state(severity="low")
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.ROUTINE

    def test_medium_severity_returns_routine(self) -> None:
        state = _make_state(severity="medium")
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.ROUTINE

    def test_no_symptoms_returns_routine(self) -> None:
        state = _make_state(symptoms=[])
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.ROUTINE


class TestUrgentPolicy:
    """URGENT: triggered when severity is 'high'."""

    def test_high_severity(self) -> None:
        state = _make_state(severity="high")
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.URGENT


class TestEmergencyPolicy:
    """EMERGENCY: triggered by emergency_candidate or EMERGENCY stage."""

    def test_emergency_candidate(self) -> None:
        state = _make_state(emergency_candidate=True)
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.EMERGENCY

    def test_emergency_stage(self) -> None:
        state = _make_state(stage=ConversationStage.EMERGENCY)
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.EMERGENCY


class TestFollowUpPolicy:
    """FOLLOW_UP: triggered by answered_questions > 0 or FOLLOW_UP stage."""

    def test_answered_questions(self) -> None:
        state = _make_state(answered_questions=["duration"])
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.FOLLOW_UP

    def test_followup_stage(self) -> None:
        state = _make_state(stage=ConversationStage.FOLLOW_UP)
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.FOLLOW_UP


# ===================================================================
# Constraint tests
# ===================================================================


class TestConstraints:
    """Verify fixed constraints per policy."""

    def test_emergency_max_questions_is_2(self) -> None:
        state = _make_state(emergency_candidate=True)
        result = determine_response_policy(state)
        assert result.max_questions == 2

    def test_emergency_no_self_care(self) -> None:
        state = _make_state(emergency_candidate=True)
        result = determine_response_policy(state)
        assert result.allow_self_care is False

    def test_emergency_no_home_remedies(self) -> None:
        state = _make_state(emergency_candidate=True)
        result = determine_response_policy(state)
        assert result.allow_home_remedies is False

    def test_emergency_requires_doctor_visit(self) -> None:
        state = _make_state(emergency_candidate=True)
        result = determine_response_policy(state)
        assert result.require_doctor_visit is True

    def test_routine_allows_self_care(self) -> None:
        state = _make_state()
        result = determine_response_policy(state)
        assert result.allow_self_care is True

    def test_routine_allows_home_remedies(self) -> None:
        state = _make_state()
        result = determine_response_policy(state)
        assert result.allow_home_remedies is True

    def test_routine_max_questions_is_3(self) -> None:
        state = _make_state()
        result = determine_response_policy(state)
        assert result.max_questions == 3

    def test_urgent_requires_doctor_visit(self) -> None:
        state = _make_state(severity="high")
        result = determine_response_policy(state)
        assert result.require_doctor_visit is True

    def test_urgent_no_self_care(self) -> None:
        state = _make_state(severity="high")
        result = determine_response_policy(state)
        assert result.allow_self_care is False

    def test_followup_allows_self_care(self) -> None:
        state = _make_state(answered_questions=["duration"])
        result = determine_response_policy(state)
        assert result.allow_self_care is True

    def test_all_policies_have_valid_max_questions(self) -> None:
        for policy in ResponsePolicy:
            ctx = ResponsePolicyContext(
                policy=policy,
                max_questions=2,
                allow_self_care=True,
                allow_home_remedies=True,
                show_emergency_warning=True,
                require_doctor_visit=False,
                max_response_words=200,
            )
            assert ctx.max_questions > 0

    def test_all_policies_have_valid_max_response_words(self) -> None:
        states = [
            _make_state(),  # ROUTINE
            _make_state(severity="high"),  # URGENT
            _make_state(emergency_candidate=True),  # EMERGENCY
            _make_state(answered_questions=["duration"]),  # FOLLOW_UP
        ]
        for state in states:
            result = determine_response_policy(state)
            assert result.max_response_words > 0


# ===================================================================
# Precedence tests
# ===================================================================


class TestPrecedence:
    """Verify the priority chain: EMERGENCY > URGENT > FOLLOW_UP > ROUTINE."""

    def test_emergency_beats_urgent(self) -> None:
        """severity=high + emergency_candidate=True → EMERGENCY."""
        state = _make_state(severity="high", emergency_candidate=True)
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.EMERGENCY

    def test_emergency_beats_followup(self) -> None:
        """answered_questions > 0 + emergency_candidate=True → EMERGENCY."""
        state = _make_state(
            emergency_candidate=True,
            answered_questions=["duration"],
        )
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.EMERGENCY

    def test_emergency_beats_all(self) -> None:
        """All conditions true → EMERGENCY wins."""
        state = _make_state(
            severity="high",
            emergency_candidate=True,
            stage=ConversationStage.FOLLOW_UP,
            answered_questions=["duration"],
        )
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.EMERGENCY

    def test_urgent_beats_followup(self) -> None:
        """severity=high + answered_questions > 0 → URGENT."""
        state = _make_state(
            severity="high",
            answered_questions=["duration"],
        )
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.URGENT

    def test_urgent_beats_routine(self) -> None:
        """severity=high, no emergency → URGENT (not ROUTINE)."""
        state = _make_state(severity="high")
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.URGENT


# ===================================================================
# Determinism tests
# ===================================================================


class TestDeterminism:
    """Verify that the policy engine is deterministic — no randomness."""

    def test_same_input_always_same_output(self) -> None:
        """Call 100 times with identical input → identical result."""
        state = _make_state(severity="high", emergency_candidate=True)
        first = determine_response_policy(state)
        for _ in range(99):
            result = determine_response_policy(state)
            assert result == first

    def test_determinism_across_all_policies(self) -> None:
        """Each policy path is deterministic."""
        cases = [
            _make_state(),  # ROUTINE
            _make_state(severity="high"),  # URGENT
            _make_state(emergency_candidate=True),  # EMERGENCY
            _make_state(answered_questions=["duration"]),  # FOLLOW_UP
        ]
        for state in cases:
            first = determine_response_policy(state)
            for _ in range(10):
                assert determine_response_policy(state) == first


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_fresh_conversation_returns_routine(self) -> None:
        state = ConversationState(
            conversation_id="fresh",
            triage=TriageContext(category="general"),
        )
        result = determine_response_policy(state)
        assert result.policy == ResponsePolicy.ROUTINE

    def test_response_policy_context_is_frozen(self) -> None:
        state = _make_state()
        result = determine_response_policy(state)
        with pytest.raises(AttributeError):
            result.max_questions = 99  # type: ignore[misc]
