"""
Response policy domain types for the Medet triage pipeline.

Defines the :class:`ResponsePolicy` enum and the
:class:`ResponsePolicyContext` frozen dataclass that carries the
backend's policy decision along with behavioural constraints.

These types are **data-only** — no business logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResponsePolicy(Enum):
    """The four response strategies the backend can select."""

    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"
    FOLLOW_UP = "follow_up"


@dataclass(frozen=True)
class ResponsePolicyContext:
    """Immutable snapshot of the response policy decision.

    Every constraint field is authoritative — downstream modules
    (prompt builder, response templates) must read from this dataclass
    rather than maintaining their own copies of the limits.
    """

    policy: ResponsePolicy
    max_questions: int
    allow_self_care: bool
    allow_home_remedies: bool
    show_emergency_warning: bool
    require_doctor_visit: bool
    max_response_words: int
