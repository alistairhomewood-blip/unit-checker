"""Tests for the SARIF output formatter.

Tests cover:
    - Valid SARIF 2.1.0 structure
    - Tool metadata
    - Rules generation from violation types
    - Result locations and messages
    - Related locations (inference chains)
    - Properties (unit information)
    - Summary statistics
    - Empty results (no violations)
"""

import json

from unit_checker.output.sarif import format_sarif
from unit_checker.inference.propagator import PropagationResult
from unit_checker.models.violations import (
    Violation,
    ViolationSeverity,
    ViolationType,
    InferenceStep,
)
from unit_checker.core.unit_algebra import UnitVector
from unit_checker.parsers.common.ir import SourceLocation


def _make_violation(
    severity=ViolationSeverity.ERROR,
    vtype=ViolationType.ADDITION_MISMATCH,
    line=10,
    message="test violation",
    expected_unit=None,
    actual_unit=None,
) -> Violation:
    """Helper to create a test violation."""
    return Violation(
        severity=severity,
        violation_type=vtype,
        location=SourceLocation("test.py", line, 5),
        message=message,
        expected_unit=expected_unit or UnitVector.from_list([1, 0, -1, 0, 0, 0, 0]),
        actual_unit=actual_unit or UnitVector.from_list([1, 0, -2, 0, 0, 0, 0]),
    )


class TestSarifStructure:
    def test_valid_json(self):
        result = PropagationResult()
        output = format_sarif(result, "test.py")
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_has_schema(self):
        result = PropagationResult()
        parsed = json.loads(format_sarif(result, "test.py"))
        assert "$schema" in parsed
        assert "sarif-schema-2.1.0" in parsed["$schema"]

    def test_has_version(self):
        result = PropagationResult()
        parsed = json.loads(format_sarif(result, "test.py"))
        assert parsed["version"] == "2.1.0"

    def test_has_runs(self):
        result = PropagationResult()
        parsed = json.loads(format_sarif(result, "test.py"))
        assert "runs" in parsed
        assert len(parsed["runs"]) == 1

    def test_has_tool(self):
        result = PropagationResult()
        parsed = json.loads(format_sarif(result, "test.py"))
        run = parsed["runs"][0]
        assert "tool" in run
        assert "driver" in run["tool"]
        driver = run["tool"]["driver"]
        assert driver["name"] == "unit-checker"
        assert "version" in driver
        assert "informationUri" in driver


class TestSarifResults:
    def test_violation_produces_result(self):
        result = PropagationResult()
        result.violations = [_make_violation()]
        parsed = json.loads(format_sarif(result, "test.py"))
        results = parsed["runs"][0]["results"]
        assert len(results) == 1

    def test_result_has_location(self):
        result = PropagationResult()
        result.violations = [_make_violation(line=42)]
        parsed = json.loads(format_sarif(result, "test.py"))
        res = parsed["runs"][0]["results"][0]
        loc = res["locations"][0]["physicalLocation"]
        assert loc["region"]["startLine"] == 42
        assert loc["artifactLocation"]["uri"] == "test.py"

    def test_result_has_message(self):
        result = PropagationResult()
        result.violations = [_make_violation(message="cannot add m/s to m/s^2")]
        parsed = json.loads(format_sarif(result, "test.py"))
        res = parsed["runs"][0]["results"][0]
        assert "cannot add" in res["message"]["text"]

    def test_result_has_rule_id(self):
        result = PropagationResult()
        result.violations = [_make_violation(vtype=ViolationType.ADDITION_MISMATCH)]
        parsed = json.loads(format_sarif(result, "test.py"))
        res = parsed["runs"][0]["results"][0]
        assert res["ruleId"] == "UC001"

    def test_result_severity_levels(self):
        result = PropagationResult()
        result.violations = [
            _make_violation(severity=ViolationSeverity.ERROR),
            _make_violation(severity=ViolationSeverity.WARNING, line=20),
        ]
        parsed = json.loads(format_sarif(result, "test.py"))
        results = parsed["runs"][0]["results"]
        assert results[0]["level"] == "error"
        assert results[1]["level"] == "warning"

    def test_result_unit_properties(self):
        result = PropagationResult()
        result.violations = [_make_violation()]
        parsed = json.loads(format_sarif(result, "test.py"))
        res = parsed["runs"][0]["results"][0]
        assert "properties" in res
        assert "expectedUnit" in res["properties"]
        assert "actualUnit" in res["properties"]


class TestSarifRules:
    def test_rules_generated_for_used_types(self):
        result = PropagationResult()
        result.violations = [
            _make_violation(vtype=ViolationType.ADDITION_MISMATCH),
            _make_violation(vtype=ViolationType.ASSIGNMENT_MISMATCH, line=20),
        ]
        parsed = json.loads(format_sarif(result, "test.py"))
        rules = parsed["runs"][0]["tool"]["driver"]["rules"]
        rule_ids = {r["id"] for r in rules}
        assert "UC001" in rule_ids
        assert "UC002" in rule_ids


class TestSarifRelatedLocations:
    def test_inference_chain_as_related_locations(self):
        v = _make_violation()
        v.inference_chain_expected = [
            InferenceStep(
                variable="global::velocity",
                unit=UnitVector.from_list([1, 0, -1, 0, 0, 0, 0]),
                reason="annotation",
                location=SourceLocation("test.py", 5, 0),
            )
        ]
        result = PropagationResult()
        result.violations = [v]
        parsed = json.loads(format_sarif(result, "test.py"))
        res = parsed["runs"][0]["results"][0]
        assert "relatedLocations" in res
        assert len(res["relatedLocations"]) >= 1


class TestSarifNoViolations:
    def test_empty_results_valid_sarif(self):
        result = PropagationResult()
        result.inferred_units = {"global::x": UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])}
        parsed = json.loads(format_sarif(result, "test.py"))
        assert len(parsed["runs"][0]["results"]) == 0
        assert parsed["runs"][0]["properties"]["summary"]["errors"] == 0


class TestSarifSummary:
    def test_summary_properties(self):
        result = PropagationResult()
        result.inferred_units = {"global::x": UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])}
        result.unknown_variables = {"global::y"}
        result.violations = [_make_violation()]
        parsed = json.loads(format_sarif(result, "test.py"))
        summary = parsed["runs"][0]["properties"]["summary"]
        assert summary["errors"] == 1
        assert summary["variablesAnalyzed"] == 2
        assert summary["unitsInferred"] == 1
