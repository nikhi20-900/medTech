"""
Tests for the Medet symptom classification triage pipeline.

Covers:
- Full pipeline integration (classify_symptom → TriageContext)
- Individual module unit tests
- Test cases from the classifier.md spec
"""

from __future__ import annotations

import pytest

from backend.app.services.symptom_classifier import TriageContext, classify_symptom
from backend.app.services.symptom_extractor import extract_symptoms
from backend.app.services.severity_detector import detect_severity
from backend.app.services.duration_detector import extract_duration
from backend.app.services.missing_info_detector import detect_missing_info
from backend.app.services.followup_questions import (
    get_followup_questions,
)
from backend.app.services.triage_prompt_builder import build_triage_prompt


# ===================================================================
# SPEC TEST CASES — full pipeline integration
# ===================================================================


class TestClassifySymptomPipeline:
    """Test cases from classifier.md spec."""

    def test_fever_and_cough(self) -> None:
        ctx = classify_symptom("I have fever and cough")
        assert ctx.category == "respiratory"
        assert "fever" in ctx.symptoms
        assert "cough" in ctx.symptoms
        assert ctx.severity == "low"
        assert ctx.duration is None
        assert ctx.emergency_candidate is False

    def test_fever_for_3_days(self) -> None:
        ctx = classify_symptom("I have fever for 3 days")
        assert ctx.category == "respiratory"
        assert "fever" in ctx.symptoms
        assert ctx.severity == "low"
        assert ctx.duration == "3 days"

    def test_severe_chest_pain(self) -> None:
        ctx = classify_symptom("I have severe chest pain")
        assert ctx.category == "cardiac"
        assert "chest pain" in ctx.symptoms
        assert ctx.severity == "high"
        assert ctx.emergency_candidate is True

    def test_pregnant_and_fever(self) -> None:
        ctx = classify_symptom("I am pregnant and have fever")
        assert ctx.category == "pregnancy"
        assert "pregnant" in ctx.symptoms
        assert "fever" in ctx.symptoms

    def test_stomach_pain_and_vomiting(self) -> None:
        ctx = classify_symptom("I have stomach pain and vomiting")
        assert ctx.category == "gastrointestinal"
        assert "stomach pain" in ctx.symptoms
        assert "vomiting" in ctx.symptoms

    def test_headache_and_blurred_vision(self) -> None:
        ctx = classify_symptom("I have headache and blurred vision")
        assert ctx.category == "neurological"
        assert "headache" in ctx.symptoms
        assert "blurred vision" in ctx.symptoms

    def test_general_non_medical(self) -> None:
        ctx = classify_symptom("What is the weather today?")
        assert ctx.category == "general"
        assert ctx.symptoms == []
        assert ctx.severity == "low"


# ===================================================================
# UNIT TESTS — Symptom Extraction
# ===================================================================


class TestSymptomExtraction:

    def test_multiple_symptoms(self) -> None:
        result = extract_symptoms("I have fever cough and headache")
        assert "fever" in result.symptoms
        assert "cough" in result.symptoms
        assert "headache" in result.symptoms

    def test_multi_word_symptom(self) -> None:
        result = extract_symptoms("I have chest pain")
        assert "chest pain" in result.symptoms
        assert result.category == "cardiac"

    def test_pregnancy_priority(self) -> None:
        result = extract_symptoms("I am pregnant and have headache and fever")
        assert result.category == "pregnancy"

    def test_no_symptoms(self) -> None:
        result = extract_symptoms("Hello how are you")
        assert result.symptoms == []
        assert result.category == "general"

    def test_emergency_candidate(self) -> None:
        result = extract_symptoms("I cannot breathe")
        assert result.emergency_candidate is True

    def test_not_emergency_candidate(self) -> None:
        result = extract_symptoms("I have a headache")
        assert result.emergency_candidate is False

    def test_negated_chest_pain_not_emergency_candidate(self) -> None:
        """Negated 'chest pain' must NOT set emergency_candidate."""
        result = extract_symptoms("I don't have chest pain")
        assert result.emergency_candidate is False

    def test_negated_trouble_breathing_not_emergency_candidate(self) -> None:
        """Negated 'trouble breathing' must NOT set emergency_candidate."""
        result = extract_symptoms("no trouble breathing at all")
        assert result.emergency_candidate is False

    def test_full_bug_report_not_emergency_candidate(self) -> None:
        """The exact bug-report input must NOT set emergency_candidate."""
        result = extract_symptoms(
            "I've had these symptoms for 3 days. My temperature is 101.4°F. "
            "The cough is dry. The body pain is moderate. I don't have chest "
            "pain or trouble breathing. I took paracetamol this morning, but "
            "the fever keeps coming back."
        )
        assert result.emergency_candidate is False

    def test_non_negated_chest_pain_still_emergency_candidate(self) -> None:
        """Sanity check: actual 'chest pain' must still flag candidate."""
        result = extract_symptoms("I have chest pain")
        assert result.emergency_candidate is True


# ===================================================================
# UNIT TESTS — Severity Detection
# ===================================================================


class TestSeverityDetection:

    def test_high_severity(self) -> None:
        assert detect_severity("severe headache") == "high"
        assert detect_severity("unbearable pain") == "high"
        assert detect_severity("extreme discomfort") == "high"

    def test_medium_severity(self) -> None:
        assert detect_severity("high fever for days") == "medium"
        assert detect_severity("persistent cough") == "medium"
        assert detect_severity("symptoms worsening") == "medium"

    def test_low_severity(self) -> None:
        assert detect_severity("I have a headache") == "low"
        assert detect_severity("mild cough") == "low"


# ===================================================================
# UNIT TESTS — Duration Detection
# ===================================================================


class TestDurationDetection:

    def test_digit_days(self) -> None:
        assert extract_duration("I have fever for 3 days") == "3 days"

    def test_word_days(self) -> None:
        assert extract_duration("pain for two days") == "2 days"

    def test_weeks(self) -> None:
        assert extract_duration("cough for 2 weeks") == "2 weeks"

    def test_one_week(self) -> None:
        assert extract_duration("sick for one week") == "1 week"

    def test_yesterday(self) -> None:
        assert extract_duration("started yesterday") == "yesterday"

    def test_since_yesterday(self) -> None:
        assert extract_duration("I have been sick since yesterday") == "since yesterday"

    def test_today(self) -> None:
        assert extract_duration("started today") == "today"

    def test_no_duration(self) -> None:
        assert extract_duration("I have a headache") is None


# ===================================================================
# UNIT TESTS — Missing Info Detection
# ===================================================================


class TestMissingInfoDetection:

    def test_missing_duration(self) -> None:
        extraction = extract_symptoms("I have fever and cough")
        missing = detect_missing_info(extraction, "low", None)
        assert "duration" in missing.gaps

    def test_missing_severity(self) -> None:
        extraction = extract_symptoms("I have chest pain")
        missing = detect_missing_info(extraction, "low", "3 days")
        assert "severity" in missing.gaps

    def test_no_gaps_for_general(self) -> None:
        extraction = extract_symptoms("hello")
        missing = detect_missing_info(extraction, "low", None)
        # General category should not flag severity as missing
        assert "severity" not in missing.gaps

    def test_temperature_gap(self) -> None:
        extraction = extract_symptoms("I have fever")
        missing = detect_missing_info(extraction, "low", None)
        assert "temperature" in missing.gaps

    def test_bleeding_detail_gap(self) -> None:
        extraction = extract_symptoms("I have bleeding")
        missing = detect_missing_info(extraction, "low", None)
        assert "bleeding_detail" in missing.gaps


# ===================================================================
# UNIT TESTS — Contextual Follow-ups
# ===================================================================


class TestContextualFollowups:

    def test_backward_compat(self) -> None:
        questions = get_followup_questions("respiratory")
        assert len(questions) > 0
        assert "What is your temperature?" in questions

    def test_backward_compat_cardiac(self) -> None:
        questions = get_followup_questions("cardiac")
        assert "When did the chest pain start?" in questions


# ===================================================================
# UNIT TESTS — Confidence Score
# ===================================================================


class TestConfidenceScore:

    def test_high_confidence(self) -> None:
        ctx = classify_symptom("I have fever cough and headache")
        assert ctx.confidence >= 0.9

    def test_medium_confidence(self) -> None:
        ctx = classify_symptom("I have a headache")
        assert 0.5 <= ctx.confidence <= 0.8

    def test_low_confidence(self) -> None:
        ctx = classify_symptom("I don't feel good")
        assert ctx.confidence <= 0.4


# ===================================================================
# UNIT TESTS — Triage Prompt Builder
# ===================================================================


class TestTriagePromptBuilder:

    def test_contains_all_sections(self) -> None:
        ctx = classify_symptom("I have fever and cough for 3 days")
        prompt = build_triage_prompt(ctx)
        assert "Detected Category:" in prompt
        assert "Detected Symptoms:" in prompt
        assert "Severity:" in prompt
        assert "Duration:" in prompt
        assert "Emergency Candidate:" in prompt
        assert "Confidence:" in prompt

    def test_missing_info_in_prompt(self) -> None:
        ctx = classify_symptom("I have severe chest pain")
        prompt = build_triage_prompt(ctx)
        assert "Missing Information:" in prompt

    def test_no_symptoms_message(self) -> None:
        ctx = classify_symptom("hello")
        prompt = build_triage_prompt(ctx)
        assert "None identified" in prompt
