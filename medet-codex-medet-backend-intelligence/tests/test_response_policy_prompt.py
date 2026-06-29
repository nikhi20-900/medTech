"""
Integration tests for the policy-aware prompt builder.

Verifies that:
- Policy directives appear in the generated prompt
- Constraint values from ResponsePolicyContext are interpolated correctly
- Existing prompt functions remain backward-compatible
"""

from __future__ import annotations

from backend.app.services.conversation_state import (
    ConversationState,
    PatientFact,
)
from backend.app.services.response_policy import (
    ResponsePolicy,
    ResponsePolicyContext,
)
from backend.app.services.symptom_classifier import TriageContext
from backend.app.services.triage_prompt_builder import (
    build_policy_aware_prompt,
    build_stateful_triage_prompt,
    build_triage_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    *,
    severity: str = "low",
    emergency_candidate: bool = False,
    category: str = "respiratory",
    symptoms: list[str] | None = None,
    answered_questions: list[str] | None = None,
    collected_information: dict[str, PatientFact] | None = None,
    missing_information: list[str] | None = None,
    turn_count: int = 1,
) -> ConversationState:
    return ConversationState(
        conversation_id="test-prompt-001",
        triage=TriageContext(
            category=category,
            symptoms=symptoms or ["cough", "fever"],
            severity=severity,
            emergency_candidate=emergency_candidate,
            confidence=0.85,
            missing_info=missing_information or ["duration"],
        ),
        answered_questions=answered_questions or [],
        collected_information=collected_information or {},
        missing_information=missing_information or ["duration"],
        turn_count=turn_count,
    )


_ROUTINE_CTX = ResponsePolicyContext(
    policy=ResponsePolicy.ROUTINE,
    max_questions=3,
    allow_self_care=True,
    allow_home_remedies=True,
    show_emergency_warning=True,
    require_doctor_visit=False,
    max_response_words=300,
)

_EMERGENCY_CTX = ResponsePolicyContext(
    policy=ResponsePolicy.EMERGENCY,
    max_questions=2,
    allow_self_care=False,
    allow_home_remedies=False,
    show_emergency_warning=True,
    require_doctor_visit=True,
    max_response_words=150,
)

_URGENT_CTX = ResponsePolicyContext(
    policy=ResponsePolicy.URGENT,
    max_questions=2,
    allow_self_care=False,
    allow_home_remedies=False,
    show_emergency_warning=True,
    require_doctor_visit=True,
    max_response_words=200,
)

_FOLLOW_UP_CTX = ResponsePolicyContext(
    policy=ResponsePolicy.FOLLOW_UP,
    max_questions=2,
    allow_self_care=True,
    allow_home_remedies=True,
    show_emergency_warning=False,
    require_doctor_visit=False,
    max_response_words=250,
)


# ===================================================================
# Prompt content tests
# ===================================================================


class TestPromptContainsPolicy:
    """Verify that the policy name and constraints appear in the prompt."""

    def test_prompt_contains_policy_name_routine(self) -> None:
        state = _make_state()
        prompt = build_policy_aware_prompt(state, _ROUTINE_CTX)
        assert "Current Response Policy: ROUTINE" in prompt

    def test_prompt_contains_policy_name_emergency(self) -> None:
        state = _make_state(emergency_candidate=True)
        prompt = build_policy_aware_prompt(state, _EMERGENCY_CTX)
        assert "Current Response Policy: EMERGENCY" in prompt

    def test_prompt_contains_policy_name_urgent(self) -> None:
        state = _make_state(severity="high")
        prompt = build_policy_aware_prompt(state, _URGENT_CTX)
        assert "Current Response Policy: URGENT" in prompt

    def test_prompt_contains_policy_name_follow_up(self) -> None:
        state = _make_state(answered_questions=["duration"])
        prompt = build_policy_aware_prompt(state, _FOLLOW_UP_CTX)
        assert "Current Response Policy: FOLLOW_UP" in prompt


class TestPromptContainsConstraints:
    """Verify that constraint values from ResponsePolicyContext appear."""

    def test_prompt_contains_max_questions_from_context(self) -> None:
        state = _make_state()
        prompt = build_policy_aware_prompt(state, _ROUTINE_CTX)
        assert "Maximum questions: 3" in prompt

    def test_prompt_contains_max_response_words(self) -> None:
        state = _make_state()
        prompt = build_policy_aware_prompt(state, _ROUTINE_CTX)
        assert "300 words" in prompt

    def test_emergency_prompt_contains_no_reassurance(self) -> None:
        state = _make_state(emergency_candidate=True)
        prompt = build_policy_aware_prompt(state, _EMERGENCY_CTX)
        assert "Reassurance: NOT ALLOWED" in prompt

    def test_emergency_prompt_forbids_downplay(self) -> None:
        state = _make_state(emergency_candidate=True)
        prompt = build_policy_aware_prompt(state, _EMERGENCY_CTX)
        assert "don't worry" in prompt or "do NOT downplay" in prompt.lower()

    def test_routine_prompt_allows_self_care(self) -> None:
        state = _make_state()
        prompt = build_policy_aware_prompt(state, _ROUTINE_CTX)
        assert "Self-care advice: ALLOWED" in prompt

    def test_urgent_prompt_requires_doctor(self) -> None:
        state = _make_state(severity="high")
        prompt = build_policy_aware_prompt(state, _URGENT_CTX)
        assert "Doctor visit recommendation: REQUIRED" in prompt


class TestPromptContainsTriage:
    """Verify that triage context is present in the prompt."""

    def test_prompt_contains_category(self) -> None:
        state = _make_state(category="respiratory")
        prompt = build_policy_aware_prompt(state, _ROUTINE_CTX)
        assert "respiratory" in prompt

    def test_prompt_contains_symptoms(self) -> None:
        state = _make_state(symptoms=["cough", "fever"])
        prompt = build_policy_aware_prompt(state, _ROUTINE_CTX)
        assert "Cough" in prompt
        assert "Fever" in prompt

    def test_prompt_contains_severity(self) -> None:
        state = _make_state(severity="high")
        prompt = build_policy_aware_prompt(state, _URGENT_CTX)
        assert "high" in prompt

    def test_prompt_contains_enforcement_rules(self) -> None:
        state = _make_state()
        prompt = build_policy_aware_prompt(state, _ROUTINE_CTX)
        assert "ENFORCEMENT" in prompt
        assert "Follow the response structure above exactly" in prompt

    def test_prompt_contains_collected_info(self) -> None:
        state = _make_state(
            collected_information={
                "duration": PatientFact(value="3 days"),
            },
        )
        prompt = build_policy_aware_prompt(state, _ROUTINE_CTX)
        assert "3 days" in prompt
        assert "DO NOT ask again" in prompt


# ===================================================================
# Backward compatibility tests
# ===================================================================


class TestBackwardCompatibility:
    """Existing prompt functions must still work."""

    def test_build_stateful_triage_prompt_still_works(self) -> None:
        state = _make_state()
        prompt = build_stateful_triage_prompt(state)
        assert "Detected Category:" in prompt
        assert "respiratory" in prompt

    def test_build_triage_prompt_still_works(self) -> None:
        ctx = TriageContext(
            category="cardiac",
            symptoms=["chest pain"],
            severity="high",
        )
        prompt = build_triage_prompt(ctx)
        assert "cardiac" in prompt
        assert "Chest Pain" in prompt
