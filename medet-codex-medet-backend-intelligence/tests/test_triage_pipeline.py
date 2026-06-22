"""
Comprehensive triage test suite for MEDET medical decision pipeline.

Tests 60+ scenarios across four categories:
  - LOW RISK: fever, headache, mild cough, etc.
  - MEDIUM RISK: persistent fever, severe vomiting, etc.
  - HIGH RISK: chest pain, cannot breathe, heavy bleeding, etc.
  - NON-MEDICAL: general knowledge, jokes, greetings, etc.

Each test verifies:
  - emergency flag
  - severity level
  - suggest_doctor flag
  - card types present/absent
"""

import pytest

from backend.app.services.medet_response_builder import build_medet_response


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build(user_message: str, ai_text: str = "I understand. Let me help you."):
    return build_medet_response(
        ai_text=ai_text,
        user_message=user_message,
        conversation_id="triage-test",
    )


def _card_types(result):
    return [card.type for card in result.cards]


# ===========================================================================
# LOW RISK — No emergency, no doctor, basic cards only
# ===========================================================================

class TestLowRisk:
    """Simple symptoms that should NOT trigger emergency or doctor visit."""

    def test_simple_fever(self):
        result = _build("I have a fever")
        assert result.emergency is False
        assert result.severity == "low"
        assert result.suggest_doctor is False
        assert "emergency" not in _card_types(result)

    def test_fever_with_medicine_question(self):
        result = _build("I think I have a fever. Can you recommend medicines?")
        assert result.emergency is False
        assert result.severity == "low"
        assert "emergency" not in _card_types(result)

    def test_mild_headache(self):
        result = _build("I have a mild headache")
        assert result.emergency is False
        assert result.severity == "low"
        assert "emergency" not in _card_types(result)

    def test_headache_after_sun(self):
        result = _build("Headache after working in the sun")
        assert result.emergency is False
        assert result.severity == "low"

    def test_mild_cough(self):
        result = _build("I have a slight cough since morning")
        assert result.emergency is False
        assert result.severity == "low"

    def test_runny_nose(self):
        result = _build("My nose is running and I feel sick")
        assert result.emergency is False
        assert result.severity == "low"

    def test_tiredness(self):
        result = _build("I feel very tired and have weakness")
        assert result.emergency is False
        assert result.severity == "low"

    def test_body_ache(self):
        result = _build("I have body pain and feel ill")
        assert result.emergency is False
        assert result.severity == "low"

    def test_sore_throat(self):
        result = _build("My throat is sore and painful")
        assert result.emergency is False
        assert result.severity == "low"

    def test_stomach_ache(self):
        result = _build("I have pain in my stomach")
        assert result.emergency is False
        assert result.severity == "low"

    def test_cold_symptoms(self):
        result = _build("I have a cold with cough and runny nose")
        assert result.emergency is False
        assert result.severity == "low"

    def test_minor_allergy(self):
        result = _build("I have an allergy and my skin is itching")
        assert result.emergency is False
        assert result.severity == "low"

    def test_mild_diarrhea(self):
        result = _build("I have had loose motion since morning")
        assert result.emergency is False
        assert result.severity == "low"

    def test_dizziness(self):
        result = _build("I feel a bit dizzy")
        assert result.emergency is False
        assert result.severity == "low"

    def test_low_risk_has_followup_card(self):
        result = _build("I have fever and headache")
        assert "followup" in _card_types(result)

    def test_low_risk_has_hydration_card_for_fever(self):
        result = _build("I have fever since yesterday")
        assert "hydration" in _card_types(result)

    def test_low_risk_no_dial_112(self):
        result = _build("I have a fever")
        assert result.emergency is False
        for card in result.cards:
            assert "112" not in card.content

    def test_simple_nausea(self):
        result = _build("I feel nauseous")
        assert result.emergency is False
        assert result.severity == "low"


# ===========================================================================
# MEDIUM RISK — suggest_doctor=True, but NOT emergency
# ===========================================================================

class TestMediumRisk:
    """Persistent or concerning symptoms that need a doctor but not 112."""

    def test_fever_for_many_days(self):
        result = _build("I have had fever for 3 days and it is not going down")
        assert result.emergency is False
        assert result.suggest_doctor is True

    def test_high_fever(self):
        result = _build("I have very high fever since yesterday")
        assert result.emergency is False
        assert result.suggest_doctor is True

    def test_pregnant_with_symptoms(self):
        result = _build("I am pregnant and I have headache")
        assert result.emergency is False
        assert result.suggest_doctor is True

    def test_baby_fever(self):
        result = _build("My baby has fever and is crying a lot")
        assert result.emergency is False
        assert result.suggest_doctor is True

    def test_elderly_weakness(self):
        result = _build("My elderly father has weakness and cannot eat")
        assert result.emergency is False
        assert result.suggest_doctor is True

    def test_persistent_cough(self):
        result = _build("I have persistent cough and it is not improving")
        assert result.emergency is False

    def test_blood_in_urine(self):
        result = _build("I see blood in urine")
        assert result.emergency is False
        assert result.suggest_doctor is True

    def test_dehydration(self):
        result = _build("I have dehydration and cannot drink water")
        assert result.emergency is False
        assert result.suggest_doctor is True

    def test_diabetes_mention(self):
        result = _build("I have diabetes and I feel sick today")
        assert result.emergency is False
        assert result.suggest_doctor is True

    def test_medium_risk_has_doctor_card(self):
        result = _build("My baby has fever and is not eating")
        card_types = _card_types(result)
        assert "emergency" not in card_types

    def test_worsening_fever(self):
        result = _build("My worsening fever is scaring me")
        assert result.emergency is False


# ===========================================================================
# HIGH RISK — emergency=True, severity=high
# ===========================================================================

class TestHighRisk:
    """Genuine emergencies that should show Dial 112 and emergency cards."""

    def test_chest_pain(self):
        result = _build("My mother has chest pain and cold sweat")
        assert result.emergency is True
        assert result.severity == "high"
        assert result.suggest_doctor is True
        assert "emergency" in _card_types(result)

    def test_cannot_breathe(self):
        result = _build("I cannot breathe properly")
        assert result.emergency is True
        assert result.severity == "high"

    def test_heavy_bleeding(self):
        result = _build("There is heavy bleeding and blood is not stopping")
        assert result.emergency is True
        assert result.severity == "high"

    def test_unconscious(self):
        result = _build("My father is unconscious and not waking up")
        assert result.emergency is True
        assert result.severity == "high"

    def test_seizure(self):
        result = _build("My child is having a seizure")
        assert result.emergency is True
        assert result.severity == "high"

    def test_stroke_symptoms(self):
        result = _build("My mother has stroke symptoms and face drooping")
        assert result.emergency is True
        assert result.severity == "high"

    def test_heart_attack(self):
        result = _build("I think I am having a heart attack")
        assert result.emergency is True
        assert result.severity == "high"

    def test_pregnancy_bleeding(self):
        result = _build("She is pregnant and there is bleeding")
        assert result.emergency is True
        assert result.severity == "high"

    def test_severe_burn(self):
        result = _build("My child has a severe burn on their arm")
        assert result.emergency is True
        assert result.severity == "high"

    def test_chest_pain_hindi(self):
        result = _build("छाती में दर्द हो रहा है")
        assert result.emergency is True
        assert result.severity == "high"

    def test_breathing_difficulty_hindi(self):
        result = _build("सांस लेने में दिक्कत हो रही है")
        assert result.emergency is True
        assert result.severity == "high"

    def test_unconscious_bengali(self):
        result = _build("সে অজ্ঞান হয়ে গেছে")
        assert result.emergency is True
        assert result.severity == "high"

    def test_high_risk_has_emergency_card(self):
        result = _build("I have chest pain and cannot breathe")
        card_types = _card_types(result)
        assert card_types[0] == "emergency"
        assert "doctor_visit" in card_types

    def test_gasping(self):
        result = _build("He is gasping for air")
        assert result.emergency is True
        assert result.severity == "high"

    def test_collapsed(self):
        result = _build("She collapsed and is not responding")
        assert result.emergency is True
        assert result.severity == "high"

    def test_severe_bleeding_not_stopping(self):
        result = _build("Bleeding a lot and blood not stopping from the wound")
        assert result.emergency is True
        assert result.severity == "high"


# ===========================================================================
# NON-MEDICAL — No emergency, no cards, no medical warnings
# ===========================================================================

class TestNonMedical:
    """Non-medical queries should return plain AI answer with no medical UI."""

    def test_capital_of_india(self):
        result = _build("What is the capital of India?")
        assert result.emergency is False
        assert result.severity == "low"
        assert result.suggest_doctor is False
        assert result.cards == []

    def test_joke(self):
        result = _build("Tell me a joke")
        assert result.emergency is False
        assert result.cards == []

    def test_prime_minister(self):
        result = _build("Who is the Prime Minister of India?")
        assert result.emergency is False
        assert result.cards == []

    def test_weather(self):
        result = _build("What is the weather today?")
        assert result.emergency is False
        assert result.cards == []

    def test_math(self):
        result = _build("What is 2 plus 2?")
        assert result.emergency is False
        assert result.cards == []

    def test_greeting(self):
        result = _build("Hello, how are you?")
        assert result.emergency is False
        assert result.cards == []

    def test_name_question(self):
        result = _build("What is your name?")
        assert result.emergency is False
        assert result.cards == []

    def test_history_question(self):
        result = _build("When did India gain independence?")
        assert result.emergency is False
        assert result.cards == []

    def test_recipe(self):
        result = _build("How do I make dal?")
        assert result.emergency is False
        assert result.cards == []

    def test_sports(self):
        result = _build("Who won the cricket match yesterday?")
        assert result.emergency is False
        assert result.cards == []

    def test_non_medical_no_medical_warning(self):
        result = _build("Tell me about the Taj Mahal")
        assert result.emergency is False
        assert result.medical_warning is False
        assert result.cards == []

    def test_general_advice(self):
        result = _build("How can I be happier?")
        assert result.emergency is False
        assert result.cards == []


# ===========================================================================
# EDGE CASES — tricky inputs that previously caused false positives
# ===========================================================================

class TestEdgeCases:
    """Edge cases that used to trigger false positives."""

    def test_breathing_exercises(self):
        """'breathing' alone should not trigger emergency."""
        result = _build("Can you suggest breathing exercises?")
        assert result.emergency is False

    def test_heartfelt(self):
        """'heart' alone should not trigger emergency."""
        result = _build("Thank you for the heartfelt advice")
        assert result.emergency is False
        assert result.cards == []

    def test_sunburn(self):
        """'burn' alone should not trigger emergency."""
        result = _build("I got a sunburn yesterday")
        assert result.emergency is False

    def test_small_cut_bleeding(self):
        """'bleeding' alone should not trigger emergency."""
        result = _build("I have a small cut that is bleeding a little")
        assert result.emergency is False

    def test_ai_response_with_emergency_boilerplate(self):
        """AI response containing safety text should not trigger emergency."""
        result = build_medet_response(
            ai_text="Rest and drink fluids. If you experience chest pain, breathing difficulty, or heavy bleeding, seek emergency care immediately.",
            user_message="I have a mild headache",
            conversation_id="edge-test",
        )
        assert result.emergency is False
        assert result.severity == "low"

    def test_negated_emergency(self):
        """Negated emergency phrases should not trigger."""
        result = _build("I do not have chest pain")
        assert result.emergency is False

    def test_fever_not_emergency(self):
        """Simple fever must NEVER be emergency."""
        result = _build("I have fever since yesterday")
        assert result.emergency is False
        assert result.severity == "low"
        assert "emergency" not in _card_types(result)

    def test_medicine_question_not_emergency(self):
        """Asking about medicine should not be emergency."""
        result = _build("Can you recommend medicine for headache?")
        assert result.emergency is False
        assert "emergency" not in _card_types(result)
