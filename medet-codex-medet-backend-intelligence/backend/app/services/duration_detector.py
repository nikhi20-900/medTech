"""
Duration detection for the Medet triage pipeline.

Extracts temporal expressions from a user message and returns a
human-readable duration string, or ``None`` if no duration is found.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Duration patterns (order matters — more specific patterns first)
# ---------------------------------------------------------------------------

_WORD_NUMBERS: dict[str, str] = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}

_DURATION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # "since yesterday", "from yesterday"
    (re.compile(r"\b(?:since|from)\s+yesterday\b", re.IGNORECASE), "since yesterday"),

    # "since today", "from today", "from this morning"
    (re.compile(r"\b(?:since|from)\s+(?:today|this morning)\b", re.IGNORECASE), "since today"),

    # "<N> days / weeks / months / hours"  (digit form)
    (re.compile(
        r"\b(\d+)\s+(day|days|week|weeks|month|months|hour|hours)\b",
        re.IGNORECASE,
    ), "{0} {1}"),

    # "<word> days / weeks / months"  (word form: "three days")
    (re.compile(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s+(day|days|week|weeks|month|months|hour|hours)\b",
        re.IGNORECASE,
    ), "{0} {1}"),

    # standalone "yesterday"
    (re.compile(r"\byesterday\b", re.IGNORECASE), "yesterday"),

    # standalone "today"
    (re.compile(r"\btoday\b", re.IGNORECASE), "today"),
)


def extract_duration(message: str) -> str | None:
    """Return a human-readable duration string or ``None``."""
    text = message.lower().strip()

    for pattern, template in _DURATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return _format_match(match, template)

    return None


def _format_match(match: re.Match[str], template: str) -> str:
    """Build the duration string from the regex match and template."""
    if "{0}" not in template:
        # Static template (e.g. "yesterday", "since yesterday")
        return template

    groups = match.groups()
    value = groups[0]
    unit = groups[1].lower()

    # Normalize word numbers → digits
    if value.lower() in _WORD_NUMBERS:
        value = _WORD_NUMBERS[value.lower()]

    # Normalize unit to consistent form
    if not unit.endswith("s") and int(value) > 1:
        unit = unit + "s"
    elif unit.endswith("s") and value == "1":
        unit = unit[:-1]

    return f"{value} {unit}"
