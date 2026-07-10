"""
Structured follow-up question bank for the Medet triage pipeline.

This module is **pure data** — no business logic lives here.

Each :class:`FollowupQuestion` carries enough metadata for the
:mod:`question_prioritizer` to deterministically select the best
questions based on the conversation state.

Groups
------
Questions are tagged with a semantic ``group`` so the prioritizer can
enforce diversity (e.g. avoid asking three respiratory questions in a
row when vitals and timeline questions are also relevant).

Prerequisites
-------------
An optional ``prerequisites`` tuple lists symptom or fact keys that
must already be present for the question to be eligible.  For example
``cough_type`` requires ``"cough"`` to have been detected.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# FollowupQuestion — structured question descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FollowupQuestion:
    """A single follow-up question with clinical metadata.

    Attributes
    ----------
    id:
        Unique identifier (e.g. ``"temperature"``).
    text:
        Human-readable question text shown to the patient.
    clinical_priority:
        Lower number = higher clinical urgency.  ``1`` is most
        critical.
    required_fact:
        The key in ``ConversationState.collected_information`` that,
        when present, means this question has been answered.
    applicable_categories:
        Triage categories for which this question is relevant.
        Use ``("all",)`` for universal questions.
    group:
        Semantic group for diversity enforcement (e.g. ``"vitals"``,
        ``"timeline"``, ``"respiratory"``).
    emergency_only:
        If ``True`` the question is only eligible when the triage
        context flags ``emergency_candidate=True``.
    prerequisites:
        Symptom or fact keys that must **all** be present (in
        ``state.triage.symptoms`` or ``state.collected_information``)
        for this question to be eligible.  Empty tuple = always
        eligible (subject to other filters).
    """

    id: str
    text: str
    clinical_priority: int
    required_fact: str
    applicable_categories: tuple[str, ...]
    group: str
    emergency_only: bool = False
    prerequisites: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# QUESTION_BANK — flat list of all follow-up questions
# ---------------------------------------------------------------------------
# Ordering in the list does NOT matter — the prioritizer sorts at
# selection time based on clinical_priority, emergency status, and
# group diversity.

QUESTION_BANK: tuple[FollowupQuestion, ...] = (
    # ---- Timeline --------------------------------------------------------
    FollowupQuestion(
        id="duration",
        text="How long have you had these symptoms?",
        clinical_priority=1,
        required_fact="duration",
        applicable_categories=("all",),
        group="timeline",
    ),
    FollowupQuestion(
        id="symptom_progression",
        text="Are your symptoms getting better, worse, or staying the same?",
        clinical_priority=3,
        required_fact="symptom_progression",
        applicable_categories=("all",),
        group="timeline",
    ),
    # ---- Vitals ----------------------------------------------------------
    FollowupQuestion(
        id="temperature",
        text="Have you measured your temperature?",
        clinical_priority=2,
        required_fact="temperature",
        applicable_categories=("respiratory", "general"),
        group="vitals",
    ),
    # ---- Respiratory -----------------------------------------------------
    FollowupQuestion(
        id="cough_type",
        text="Is your cough dry or producing mucus?",
        clinical_priority=3,
        required_fact="cough_type",
        applicable_categories=("respiratory",),
        group="respiratory",
        prerequisites=("cough",),
    ),
    FollowupQuestion(
        id="breathing_difficulty",
        text="Are you having difficulty breathing?",
        clinical_priority=2,
        required_fact="breathing_difficulty",
        applicable_categories=("respiratory", "cardiac"),
        group="respiratory",
    ),
    FollowupQuestion(
        id="swallowing_difficulty",
        text="Is it painful or difficult to swallow?",
        clinical_priority=3,
        required_fact="swallowing_difficulty",
        applicable_categories=("respiratory",),
        group="respiratory",
        prerequisites=("sore throat",),
    ),
    # ---- Cardiac ---------------------------------------------------------
    FollowupQuestion(
        id="chest_pain_location",
        text="Where exactly is the chest pain?",
        clinical_priority=1,
        required_fact="chest_pain_location",
        applicable_categories=("cardiac",),
        group="cardiac",
        prerequisites=("chest pain",),
    ),
    FollowupQuestion(
        id="chest_pain_radiation",
        text="Does the pain spread to your arm, jaw, or back?",
        clinical_priority=2,
        required_fact="chest_pain_radiation",
        applicable_categories=("cardiac",),
        group="cardiac",
        prerequisites=("chest pain",),
    ),
    # ---- Neurological ----------------------------------------------------
    FollowupQuestion(
        id="headache_severity",
        text="How severe is the headache on a scale of 1-10?",
        clinical_priority=2,
        required_fact="headache_severity",
        applicable_categories=("neurological",),
        group="neurological",
        prerequisites=("headache",),
    ),
    FollowupQuestion(
        id="vision_changes",
        text="Have you noticed any changes in your vision?",
        clinical_priority=3,
        required_fact="vision_changes",
        applicable_categories=("neurological",),
        group="neurological",
    ),
    # ---- Gastrointestinal ------------------------------------------------
    FollowupQuestion(
        id="vomiting",
        text="Have you been vomiting?",
        clinical_priority=3,
        required_fact="vomiting",
        applicable_categories=("gastrointestinal", "general"),
        group="gastrointestinal",
    ),
    FollowupQuestion(
        id="fluid_intake",
        text="Are you able to keep fluids down?",
        clinical_priority=3,
        required_fact="fluid_intake",
        applicable_categories=("gastrointestinal",),
        group="gastrointestinal",
        prerequisites=("vomiting",),
    ),
    # ---- Injury ----------------------------------------------------------
    FollowupQuestion(
        id="injury_time",
        text="When did the injury happen?",
        clinical_priority=1,
        required_fact="injury_time",
        applicable_categories=("injury",),
        group="injury",
    ),
    FollowupQuestion(
        id="bleeding_amount",
        text="How much bleeding is there?",
        clinical_priority=1,
        required_fact="bleeding_amount",
        applicable_categories=("injury", "pregnancy"),
        group="injury",
        prerequisites=("bleeding",),
    ),
    # ---- Pregnancy -------------------------------------------------------
    FollowupQuestion(
        id="pregnancy_weeks",
        text="How many weeks pregnant are you?",
        clinical_priority=1,
        required_fact="pregnancy_weeks",
        applicable_categories=("pregnancy",),
        group="pregnancy",
        prerequisites=("pregnant",),
    ),
    # ---- Treatment -------------------------------------------------------
    FollowupQuestion(
        id="medication_taken",
        text="Have you taken any medication for this?",
        clinical_priority=4,
        required_fact="medication_taken",
        applicable_categories=("all",),
        group="treatment",
    ),
    # ---- Emergency (only when emergency_candidate=True) ------------------
    FollowupQuestion(
        id="consciousness_level",
        text="Are you feeling alert and oriented?",
        clinical_priority=1,
        required_fact="consciousness_level",
        applicable_categories=("all",),
        group="emergency",
        emergency_only=True,
    ),
    FollowupQuestion(
        id="severe_pain",
        text="Are you experiencing severe or unbearable pain?",
        clinical_priority=1,
        required_fact="severe_pain",
        applicable_categories=("all",),
        group="emergency",
        emergency_only=True,
    ),
)
