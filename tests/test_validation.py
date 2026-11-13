import pytest

from portal.validation import (
    classify_report,
    validate_identifiers,
    validate_inspector_id_dfa,
    validate_inspector_id_regex,
    validate_violation_code_dfa,
    validate_violation_code_regex,
)


@pytest.mark.parametrize("value", ["INSAB1234", "INSZX0000", "INSAA9999"])
def test_valid_inspector_ids_agree_between_dfa_and_regex(value):
    assert validate_inspector_id_dfa(value)
    assert validate_inspector_id_regex(value)


@pytest.mark.parametrize("value", ["INSAB123", "insAB1234", "INSA12345", "INSAB12345", "INS-AB1234"])
def test_invalid_inspector_ids_are_rejected(value):
    assert not validate_inspector_id_dfa(value)
    assert not validate_inspector_id_regex(value)


@pytest.mark.parametrize("value", ["V01-CRITICAL", "V99-ADVISORY_NOTE", "V00-PASSED"])
def test_valid_violation_codes_agree_between_dfa_and_regex(value):
    assert validate_violation_code_dfa(value)
    assert validate_violation_code_regex(value)


@pytest.mark.parametrize("value", ["V1-CRITICAL", "V01-critical", "V01-", "X01-MAJOR", "V010-MAJOR"])
def test_invalid_violation_codes_are_rejected(value):
    assert not validate_violation_code_dfa(value)
    assert not validate_violation_code_regex(value)


def test_validation_response_exposes_meaningful_errors_and_agreement():
    result = validate_identifiers("INSAB123", "V01-")
    assert not result["valid"]
    assert result["agreement"] is True
    assert "Inspector ID" in result["message"]
    assert "Violation code" in result["message"]


@pytest.mark.parametrize("code, expected", [("V01-CRITICAL", "Critical"), ("V02-MAJOR", "Major"), ("V03-MINOR", "Minor"), ("V04-ADVISORY", "Advisory"), ("V05-PASSED", "Passed")])
def test_all_five_categories_are_supported(code, expected):
    assert classify_report(code, "Routine inspection note")["category"] == expected


def test_conflicting_patterns_use_documented_critical_first_precedence():
    result = classify_report("V04-ADVISORY", "Advisory note also mentions expired food and critical contamination.")
    assert result["category"] == "Critical"
    assert "Critical" in result["matched"] and "Major" in result["matched"]


def test_unknown_category_token_has_safe_deterministic_default():
    result = classify_report("V77-UNKNOWN", "Routine inspection note")
    assert result["category"] is None
    assert result["mapped"] is False
    assert "not mapped" in result["reason"]

