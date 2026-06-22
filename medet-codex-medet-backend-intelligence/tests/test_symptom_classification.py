from __future__ import annotations

import pytest
from backend.app.services.symptom_classifier import classify_symptom, SymptomCategory
from backend.app.services.followup_questions import get_followup_questions


def test_symptom_classification_respiratory() -> None:
    category = classify_symptom("I have fever and cough")
    assert category.name == "respiratory"
    assert category.severity == "low"

    questions = get_followup_questions(category.name)
    assert "What is your temperature?" in questions
    assert len(questions) > 0


def test_symptom_classification_cardiac() -> None:
    category = classify_symptom("I have chest pain and sweating")
    assert category.name == "cardiac"
    assert category.severity == "high"

    questions = get_followup_questions(category.name)
    assert "When did the chest pain start?" in questions


def test_symptom_classification_pregnancy() -> None:
    category = classify_symptom("I am pregnant and have fever")
    assert category.name == "pregnancy"
    assert category.severity == "medium"

    questions = get_followup_questions(category.name)
    assert "How many weeks pregnant are you?" in questions


def test_symptom_classification_neurological() -> None:
    category = classify_symptom("I have severe headache and blurry vision")
    assert category.name == "neurological"
    assert category.severity == "medium"

    questions = get_followup_questions(category.name)
    assert "How severe is the headache?" in questions


def test_symptom_classification_gastrointestinal() -> None:
    category = classify_symptom("I have stomach pain and vomiting")
    assert category.name == "gastrointestinal"
    assert category.severity == "medium"

    questions = get_followup_questions(category.name)
    assert "Are you vomiting?" in questions


def test_symptom_classification_injury() -> None:
    category = classify_symptom("I got a deep burn on my arm")
    assert category.name == "injury"
    assert category.severity == "medium"


def test_symptom_classification_general() -> None:
    category = classify_symptom("What is the weather today?")
    assert category.name == "general"
    assert category.severity == "low"
