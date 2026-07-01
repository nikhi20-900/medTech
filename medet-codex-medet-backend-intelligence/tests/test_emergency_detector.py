from backend.app.services.emergency_detector import detect_emergency


def test_detects_breathing_difficulty() -> None:
    result = detect_emergency("My father cannot breathe and is gasping")

    assert result == {
        "emergency": True,
        "severity": "high",
        "reason": "Possible breathing difficulty detected",
    }


def test_detects_pregnancy_bleeding() -> None:
    result = detect_emergency("She is pregnant and bleeding since morning")

    assert result["emergency"] is True
    assert result["severity"] == "high"
    assert result["reason"] == "Possible pregnancy bleeding detected"


def test_detects_stroke_symptoms() -> None:
    result = detect_emergency("Sudden weakness on one side and slurred speech")

    assert result["emergency"] is True
    assert result["reason"] == "Possible stroke symptoms detected"


def test_non_emergency_returns_low_metadata() -> None:
    result = detect_emergency("Mild cough for two days")

    assert result == {
        "emergency": False,
        "severity": "low",
        "reason": None,
    }


def test_simple_negation_does_not_trigger() -> None:
    result = detect_emergency("There is no chest pain, only mild acidity")

    assert result["emergency"] is False


def test_detects_hindi_breathing_difficulty() -> None:
    result = detect_emergency("मुझे सांस लेने में दिक्कत हो रही है")

    assert result["emergency"] is True
    assert result["reason"] == "Possible breathing difficulty detected"


def test_detects_bengali_severe_bleeding() -> None:
    result = detect_emergency("রক্ত বন্ধ হচ্ছে না")

    assert result["emergency"] is True
    assert result["reason"] == "Possible severe bleeding detected"


def test_detects_nepali_chest_pain() -> None:
    result = detect_emergency("छाती दुखेको छ")

    assert result["emergency"] is True
    assert result["reason"] == "Possible chest pain or heart attack symptoms detected"


def test_detects_tamil_stroke_symptoms() -> None:
    result = detect_emergency("ஒரு பக்கம் பலவீனம் உள்ளது")

    assert result["emergency"] is True
    assert result["reason"] == "Possible stroke symptoms detected"


def test_detects_kannada_severe_burn() -> None:
    result = detect_emergency("ತೀವ್ರ ಸುಟ್ಟ ಗಾಯವಾಗಿದೆ")

    assert result["emergency"] is True
    assert result["reason"] == "Possible severe burn detected"


# ===================================================================
# Negated emergency symptoms — regression tests for false positives
# ===================================================================


def test_negated_dont_have_chest_pain() -> None:
    """'don't have chest pain' must NOT trigger emergency."""
    result = detect_emergency("I don't have chest pain or trouble breathing")
    assert result["emergency"] is False


def test_negated_no_chest_pain() -> None:
    """'no chest pain' must NOT trigger emergency."""
    result = detect_emergency("no chest pain, no breathing difficulty")
    assert result["emergency"] is False


def test_negated_chest_pain_gone() -> None:
    """Post-term negation ('gone', 'better') must NOT trigger emergency."""
    result = detect_emergency("chest pain has gone, breathing is fine")
    assert result["emergency"] is False


def test_negated_mixed_with_non_emergency() -> None:
    """Negated emergency + non-emergency symptom must NOT trigger."""
    result = detect_emergency(
        "I don't have chest pain but I have severe headache"
    )
    assert result["emergency"] is False


def test_negated_without_breathing_difficulty() -> None:
    """'without breathing difficulty' must NOT trigger emergency."""
    result = detect_emergency("fever for 3 days without breathing difficulty")
    assert result["emergency"] is False


def test_negated_never_had_chest_pain() -> None:
    """'never had chest pain' must NOT trigger emergency."""
    result = detect_emergency("I never had chest pain in my life")
    assert result["emergency"] is False


def test_non_negated_still_triggers() -> None:
    """Sanity check: actual chest pain must still trigger emergency."""
    result = detect_emergency("I have severe chest pain")
    assert result["emergency"] is True
    assert result["reason"] == "Possible chest pain or heart attack symptoms detected"


def test_full_bug_report_input() -> None:
    """The exact input from the bug report must NOT trigger emergency."""
    result = detect_emergency(
        "I've had these symptoms for 3 days. My temperature is 101.4°F. "
        "The cough is dry. The body pain is moderate. I don't have chest "
        "pain or trouble breathing. I took paracetamol this morning, but "
        "the fever keeps coming back."
    )
    assert result["emergency"] is False

