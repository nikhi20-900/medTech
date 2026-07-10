"""
Deterministic follow-up question prioritizer for the Medet triage pipeline.

Selects the best follow-up questions to ask a patient based entirely on
structured rules — **no LLM, no randomness**.

Pipeline (7 stages)
-------------------
1. **Category Filter** — keep questions matching the triage category
   or ``"all"``.
2. **Prerequisite Filter** — keep questions whose prerequisites are
   satisfied by detected symptoms or collected facts.
3. **Already Answered Filter** — remove questions whose
   ``required_fact`` is already in ``collected_information``.
4. **Emergency Filter** — remove ``emergency_only=True`` questions
   unless ``emergency_candidate`` is set.
5. **Sort** — emergency-only first, then ``clinical_priority`` ASC,
   then ``id`` ASC (deterministic tiebreak).
6. **Group Diversity** — round-robin across semantic groups so the
   output is diverse.
7. **Top N** — return up to ``max_questions`` entries.

Guarantees
----------
- Same input → identical output (deterministic).
- No duplicate questions.
- Emergency questions always override routine questions.
- Higher ``clinical_priority`` (lower number) is always preferred
  within the same diversity pass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.app.services.followup_question_bank import (
    QUESTION_BANK,
    FollowupQuestion,
)

if TYPE_CHECKING:
    from backend.app.services.conversation_state import ConversationState


class QuestionPrioritizer:
    """Stateless, deterministic follow-up question selector.

    Instantiation is cheap — no side-effects, no I/O.  Each call to
    :meth:`select` runs the full pipeline from scratch against the
    provided :class:`ConversationState`.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select(
        self,
        state: ConversationState,
        max_questions: int = 3,
    ) -> list[FollowupQuestion]:
        """Return the highest-priority, diverse, unanswered questions.

        Parameters
        ----------
        state:
            Current conversation state snapshot.
        max_questions:
            Maximum number of questions to return.

        Returns
        -------
        list[FollowupQuestion]
            Ordered list (best first) of up to *max_questions* entries.
        """
        # If no important information is missing, return an empty list.
        answered = set(state.answered_questions)
        remaining_gaps = [
            gap for gap in state.missing_information
            if gap not in answered
        ]
        if not remaining_gaps:
            return []

        category = state.triage.category
        symptoms = set(state.triage.symptoms)
        known_facts = set(state.collected_information.keys())
        is_emergency = state.triage.emergency_candidate

        # Build a combined set for prerequisite checks — symptoms plus
        # any fact keys the patient has already provided.
        available_context = symptoms | known_facts

        # Stage 1: Category filter
        candidates = _filter_by_category(QUESTION_BANK, category)

        # Stage 2: Prerequisite filter
        candidates = _filter_by_prerequisites(candidates, available_context)

        # Stage 3: Already-answered filter
        candidates = _filter_answered(candidates, known_facts)

        # Stage 4: Emergency filter
        candidates = _filter_emergency(candidates, is_emergency)

        # Stage 5: Deterministic sort
        candidates = _sort(candidates)

        # Stage 6: Group diversity
        candidates = _apply_group_diversity(candidates, max_questions)

        # Stage 7: Top N
        return candidates[:max_questions]


# ----------------------------------------------------------------------
# Pipeline stages (module-private)
# ----------------------------------------------------------------------


def _filter_by_category(
    questions: tuple[FollowupQuestion, ...],
    category: str,
) -> list[FollowupQuestion]:
    """Keep questions whose categories include *category* or ``'all'``."""
    return [
        q for q in questions
        if category in q.applicable_categories
        or "all" in q.applicable_categories
    ]


def _filter_by_prerequisites(
    questions: list[FollowupQuestion],
    available_context: set[str],
) -> list[FollowupQuestion]:
    """Keep questions whose prerequisites are ALL satisfied."""
    return [
        q for q in questions
        if all(prereq in available_context for prereq in q.prerequisites)
    ]


def _filter_answered(
    questions: list[FollowupQuestion],
    known_facts: set[str],
) -> list[FollowupQuestion]:
    """Remove questions whose ``required_fact`` is already known."""
    return [
        q for q in questions
        if q.required_fact not in known_facts
    ]


def _filter_emergency(
    questions: list[FollowupQuestion],
    is_emergency: bool,
) -> list[FollowupQuestion]:
    """Remove ``emergency_only`` questions when not in an emergency."""
    if is_emergency:
        # All questions eligible
        return questions
    return [q for q in questions if not q.emergency_only]


def _sort(questions: list[FollowupQuestion]) -> list[FollowupQuestion]:
    """Sort: emergency_only DESC → clinical_priority ASC → id ASC."""
    return sorted(
        questions,
        key=lambda q: (
            not q.emergency_only,   # True first (False=0 < True=1)
            q.clinical_priority,
            q.id,
        ),
    )


def _apply_group_diversity(
    sorted_questions: list[FollowupQuestion],
    max_questions: int,
) -> list[FollowupQuestion]:
    """Pick questions round-robin across groups.

    Pass 1: Walk the sorted list and take the first question from each
            unseen group (preserving clinical-priority order within
            the pass).
    Pass 2+: If slots remain, repeat — allowing additional questions
             from already-picked groups.

    Emergency-only questions bypass diversity: they are always placed
    first, then diversity is applied to the remaining slots.
    """
    if not sorted_questions:
        return []

    # Separate emergency-only questions (they bypass diversity).
    emergency: list[FollowupQuestion] = [
        q for q in sorted_questions if q.emergency_only
    ]
    routine: list[FollowupQuestion] = [
        q for q in sorted_questions if not q.emergency_only
    ]

    # Start with all emergency questions.
    result: list[FollowupQuestion] = list(emergency)
    remaining_slots = max_questions - len(result)

    if remaining_slots <= 0:
        return result[:max_questions]

    # Round-robin passes over routine questions.
    picked_ids: set[str] = {q.id for q in result}
    remaining = [q for q in routine if q.id not in picked_ids]

    while remaining and len(result) < max_questions:
        seen_groups: set[str] = set()
        next_remaining: list[FollowupQuestion] = []

        for q in remaining:
            if q.id in picked_ids:
                continue
            if q.group not in seen_groups and len(result) < max_questions:
                result.append(q)
                picked_ids.add(q.id)
                seen_groups.add(q.group)
            else:
                next_remaining.append(q)

        # If we didn't pick anything new this pass, stop to avoid
        # infinite loop (shouldn't happen, but defensive).
        if len(next_remaining) == len(remaining):
            break
        remaining = next_remaining

    return result[:max_questions]
