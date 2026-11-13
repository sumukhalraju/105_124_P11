"""DFA and equivalent regular-expression validation for inspection identifiers.

The implementation deliberately keeps the DFA explicit so that the academic
requirement can be demonstrated in code and in the UI.  The regex validators
are run independently and are expected to agree with the DFA.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable


INSPECTOR_REGEX = re.compile(r"^INS[A-Z]{2}\d{4}$")
VIOLATION_REGEX = re.compile(r"^V\d{2}-[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    message: str
    method: str


def _run_dfa(value: str, transitions: dict[tuple[int, str], int], accepting: set[int], classifier: Callable[[str], str]) -> bool:
    state = 0
    for char in value:
        symbol = classifier(char)
        state = transitions.get((state, symbol), -1)
        if state == -1:
            return False
    return state in accepting


def validate_inspector_id_dfa(value: str) -> bool:
    transitions: dict[tuple[int, str], int] = {}
    for state in range(10):
        if state == 0:
            transitions[(state, "I")] = 1
        elif state == 1:
            transitions[(state, "N")] = 2
        elif state == 2:
            transitions[(state, "S")] = 3
        elif state in (3, 4):
            transitions[(state, "A")] = state + 1
        elif 5 <= state <= 8:
            transitions[(state, "D")] = state + 1
    state = 0
    for char in value:
        if state == 0:
            symbol = "I" if char == "I" else "?"
        elif state == 1:
            symbol = "N" if char == "N" else "?"
        elif state == 2:
            symbol = "S" if char == "S" else "?"
        elif state in (3, 4):
            symbol = "A" if "A" <= char <= "Z" else "?"
        else:
            symbol = "D" if char.isdigit() else "?"
        state = transitions.get((state, symbol), -1)
        if state == -1:
            return False
    return state == 9


def validate_violation_code_dfa(value: str) -> bool:
    transitions: dict[tuple[int, str], int] = {
        (0, "V"): 1,
        (1, "D"): 2,
        (2, "D"): 3,
        (3, "-"): 4,
        (4, "A"): 5,
    }
    for state in range(5, 7):
        transitions[(state, "A")] = 6
        transitions[(state, "D")] = 6
        transitions[(state, "_")] = 6
    state = 0
    for char in value:
        if state == 0:
            symbol = "V" if char == "V" else "?"
        elif state in (1, 2):
            symbol = "D" if char.isdigit() else "?"
        elif state == 3:
            symbol = "-" if char == "-" else "?"
        else:
            symbol = "A" if "A" <= char <= "Z" else "D" if char.isdigit() else "_" if char == "_" else "?"
        state = transitions.get((state, symbol), -1)
        if state == -1:
            return False
    return state in {5, 6}


def validate_inspector_id_regex(value: str) -> bool:
    return bool(INSPECTOR_REGEX.fullmatch(value or ""))


def validate_violation_code_regex(value: str) -> bool:
    return bool(VIOLATION_REGEX.fullmatch(value or ""))


def validate_identifiers(inspector_id: str, violation_code: str) -> dict:
    inspector_dfa = validate_inspector_id_dfa(inspector_id)
    inspector_regex = validate_inspector_id_regex(inspector_id)
    violation_dfa = validate_violation_code_dfa(violation_code)
    violation_regex = validate_violation_code_regex(violation_code)
    errors: list[str] = []
    if not inspector_dfa:
        errors.append("Inspector ID must match INS + two uppercase letters + four digits (example: INSAB1234).")
    if not violation_dfa:
        errors.append("Violation code must match V + two digits + hyphen + uppercase category token (example: V01-CRITICAL).")
    return {
        "valid": inspector_dfa and inspector_regex and violation_dfa and violation_regex,
        "errors": errors,
        "dfa": {"inspector_id": inspector_dfa, "violation_code": violation_dfa},
        "regex": {"inspector_id": inspector_regex, "violation_code": violation_regex},
        "agreement": inspector_dfa == inspector_regex and violation_dfa == violation_regex,
        "message": "Identifiers accepted by DFA and regex." if not errors else " ".join(errors),
    }


CATEGORIES = ("Critical", "Major", "Minor", "Advisory", "Passed")
CATEGORY_PRIORITY = {category: index + 1 for index, category in enumerate(CATEGORIES)}
CODE_CATEGORY_MAP = {
    "CRITICAL": "Critical",
    "MAJOR": "Major",
    "MINOR": "Minor",
    "ADVISORY": "Advisory",
    "PASSED": "Passed",
}

_DESCRIPTION_PATTERNS = {
    "Critical": re.compile(r"\b(critical|poison|contaminat|allergen|sewage|pest infestation|raw meat|temperature abuse)\b", re.I),
    "Major": re.compile(r"\b(major|expired|cross[- ]contaminat|unclean|refrigerat|hygiene|unsafe)\b", re.I),
    "Minor": re.compile(r"\b(minor|label|storage|cleaning|documentation gap)\b", re.I),
    "Advisory": re.compile(r"\b(advisory|recommend|training|guidance|observation)\b", re.I),
    "Passed": re.compile(r"\b(passed|pass|compliant|no violation|satisfactory|clear)\b", re.I),
}


def classify_report(violation_code: str, description: str) -> dict:
    """Classify with an explicit Critical > Major > Minor > Advisory > Passed rule."""
    candidates: list[tuple[int, str, str]] = []
    token = (violation_code or "").split("-", 1)[1] if "-" in (violation_code or "") else ""
    if token not in CODE_CATEGORY_MAP:
        return {
            "category": None,
            "priority": None,
            "reason": f"Violation token {token or '[missing]'} is not mapped to one of the five supported categories.",
            "matched": [],
            "mapped": False,
        }
    category = CODE_CATEGORY_MAP[token]
    candidates.append((CATEGORY_PRIORITY[category], category, f"Mapped violation token {token}."))
    for category, pattern in _DESCRIPTION_PATTERNS.items():
        if pattern.search(description or ""):
            candidates.append((CATEGORY_PRIORITY[category], category, f"Description matched {category.lower()} classification pattern."))
    candidates.sort(key=lambda item: (item[0], item[1]))
    priority, category, reason = candidates[0]
    return {
        "category": category,
        "priority": priority,
        "reason": reason + " Priority order: Critical > Major > Minor > Advisory > Passed.",
        "matched": [item[1] for item in candidates],
        "mapped": token in CODE_CATEGORY_MAP,
    }

