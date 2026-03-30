"""SARIF output formatter.

Produces Static Analysis Results Interchange Format (SARIF) v2.1.0 for
integration with GitHub Code Scanning, Azure DevOps, and other tools.

Specification: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html

The output includes:
    - Tool metadata (name, version, information URI)
    - Rules definitions (one per violation type)
    - Results with locations, messages, and related locations (inference chain)
    - Invocation metadata
"""

from __future__ import annotations

import json
from typing import Any, Optional

from unit_checker import __version__
from unit_checker.core.unit_registry import UnitRegistry, default_registry
from unit_checker.models.violations import (
    Violation,
    ViolationSeverity,
    ViolationType,
)
from unit_checker.inference.propagator import PropagationResult


# Map violation types to SARIF rule IDs and descriptions
_RULES: dict[ViolationType, dict[str, str]] = {
    ViolationType.ADDITION_MISMATCH: {
        "id": "UC001",
        "name": "AdditionUnitMismatch",
        "shortDescription": "Unit mismatch in addition or subtraction",
        "fullDescription": (
            "The operands of an addition or subtraction have incompatible "
            "physical dimensions. For example, adding a velocity (m/s) to "
            "an acceleration (m/s^2) is physically meaningless."
        ),
        "helpUri": "https://github.com/unit-checker/unit-checker/wiki/UC001",
    },
    ViolationType.ASSIGNMENT_MISMATCH: {
        "id": "UC002",
        "name": "AssignmentUnitMismatch",
        "shortDescription": "Conflicting units in assignment",
        "fullDescription": (
            "A variable is being assigned a value whose physical dimensions "
            "conflict with a previously inferred or annotated unit for that variable."
        ),
        "helpUri": "https://github.com/unit-checker/unit-checker/wiki/UC002",
    },
    ViolationType.FUNCTION_ARG_MISMATCH: {
        "id": "UC003",
        "name": "FunctionArgumentUnitMismatch",
        "shortDescription": "Unit mismatch in function argument",
        "fullDescription": (
            "A function is being called with an argument whose physical "
            "dimensions do not match the expected parameter unit."
        ),
        "helpUri": "https://github.com/unit-checker/unit-checker/wiki/UC003",
    },
    ViolationType.RETURN_MISMATCH: {
        "id": "UC004",
        "name": "ReturnUnitMismatch",
        "shortDescription": "Unit mismatch in return value",
        "fullDescription": (
            "A function returns a value whose physical dimensions do not "
            "match the declared return unit."
        ),
        "helpUri": "https://github.com/unit-checker/unit-checker/wiki/UC004",
    },
    ViolationType.COMPARISON_MISMATCH: {
        "id": "UC005",
        "name": "ComparisonUnitMismatch",
        "shortDescription": "Unit mismatch in comparison",
        "fullDescription": (
            "The operands of a comparison have incompatible physical dimensions."
        ),
        "helpUri": "https://github.com/unit-checker/unit-checker/wiki/UC005",
    },
    ViolationType.CONFLICTING_CONSTRAINTS: {
        "id": "UC006",
        "name": "ConflictingUnitConstraints",
        "shortDescription": "Conflicting unit constraints",
        "fullDescription": (
            "A variable has been constrained to two different physical dimensions "
            "by different parts of the code. This indicates an inconsistency "
            "in the unit annotations or computations."
        ),
        "helpUri": "https://github.com/unit-checker/unit-checker/wiki/UC006",
    },
}

# Map severity to SARIF level
_SEVERITY_MAP: dict[ViolationSeverity, str] = {
    ViolationSeverity.ERROR: "error",
    ViolationSeverity.WARNING: "warning",
    ViolationSeverity.INFO: "note",
}


def format_sarif(
    result: PropagationResult,
    file_path: str,
    registry: Optional[UnitRegistry] = None,
) -> str:
    """Format analysis results as SARIF 2.1.0 JSON.

    Args:
        result: The propagation result containing violations.
        file_path: Path to the analyzed file.
        registry: Unit registry for name lookups.

    Returns:
        SARIF 2.1.0 compliant JSON string.
    """
    reg = registry or default_registry

    # Collect which rules are actually used
    used_rule_types: set[ViolationType] = set()
    for v in result.violations:
        used_rule_types.add(v.violation_type)

    # Build rules array (only include rules that have results)
    rules: list[dict[str, Any]] = []
    rule_index_map: dict[str, int] = {}
    for vtype, rule_info in _RULES.items():
        if vtype in used_rule_types:
            rule_index_map[rule_info["id"]] = len(rules)
            rules.append({
                "id": rule_info["id"],
                "name": rule_info["name"],
                "shortDescription": {"text": rule_info["shortDescription"]},
                "fullDescription": {"text": rule_info["fullDescription"]},
                "helpUri": rule_info["helpUri"],
                "defaultConfiguration": {
                    "level": "error",
                },
                "properties": {
                    "tags": ["correctness", "physics", "dimensional-analysis"],
                },
            })

    # Build results array
    results: list[dict[str, Any]] = []
    for violation in result.violations:
        sarif_result = _build_result(violation, file_path, reg)
        results.append(sarif_result)

    # Build the SARIF document
    num_errors = sum(1 for v in result.violations if v.severity == ViolationSeverity.ERROR)
    num_warnings = sum(1 for v in result.violations if v.severity == ViolationSeverity.WARNING)

    sarif: dict[str, Any] = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "unit-checker",
                        "version": __version__,
                        "semanticVersion": __version__,
                        "informationUri": "https://github.com/unit-checker/unit-checker",
                        "rules": rules,
                    },
                },
                "results": results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "toolExecutionNotifications": [],
                    },
                ],
                "properties": {
                    "summary": {
                        "errors": num_errors,
                        "warnings": num_warnings,
                        "variablesAnalyzed": len(result.inferred_units) + len(result.unknown_variables),
                        "unitsInferred": len(result.inferred_units),
                    },
                },
            },
        ],
    }

    return json.dumps(sarif, indent=2)


def _build_result(
    violation: Violation,
    file_path: str,
    registry: UnitRegistry,
) -> dict[str, Any]:
    """Build a SARIF result object from a violation."""
    rule_info = _RULES.get(violation.violation_type, _RULES[ViolationType.CONFLICTING_CONSTRAINTS])
    level = _SEVERITY_MAP.get(violation.severity, "warning")

    # Build the primary location
    # SARIF uses 1-based line numbers and 1-based column numbers
    region: dict[str, int] = {
        "startLine": max(1, violation.location.line),
        "startColumn": max(1, violation.location.column + 1),  # Convert 0-based to 1-based
    }

    # Add source line as snippet if available
    snippet: dict[str, Any] = {}
    if violation.source_line:
        snippet = {"snippet": {"text": violation.source_line}}

    location: dict[str, Any] = {
        "physicalLocation": {
            "artifactLocation": {
                "uri": file_path,
                "uriBaseId": "%SRCROOT%",
            },
            "region": {**region, **snippet},
        },
    }

    # Build related locations from inference chains
    related_locations: list[dict[str, Any]] = []
    rel_id = 1

    for chain_name, chain in [
        ("expected", violation.inference_chain_expected),
        ("actual", violation.inference_chain_actual),
    ]:
        for step in chain:
            unit_str = step.unit.to_unit_string()
            named = registry.get_name(step.unit)
            if named and named != unit_str:
                unit_display = f"{named} = {unit_str}"
            else:
                unit_display = unit_str

            var_display = step.variable.split("::")[-1] if "::" in step.variable else step.variable

            related_locations.append({
                "id": rel_id,
                "message": {
                    "text": f"[{chain_name}] '{var_display}' has unit [{unit_display}]: {step.reason}",
                },
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": step.location.file,
                        "uriBaseId": "%SRCROOT%",
                    },
                    "region": {
                        "startLine": max(1, step.location.line),
                        "startColumn": max(1, step.location.column + 1),
                    },
                },
            })
            rel_id += 1

    result: dict[str, Any] = {
        "ruleId": rule_info["id"],
        "ruleIndex": 0,  # Simplified: use first matching rule
        "level": level,
        "message": {
            "text": violation.message,
        },
        "locations": [location],
    }

    if related_locations:
        result["relatedLocations"] = related_locations

    # Add unit information as properties
    properties: dict[str, Any] = {}
    if violation.expected_unit:
        expected_str = violation.expected_unit.to_unit_string()
        properties["expectedUnit"] = expected_str
        name = registry.get_name(violation.expected_unit)
        if name:
            properties["expectedUnitName"] = name
    if violation.actual_unit:
        actual_str = violation.actual_unit.to_unit_string()
        properties["actualUnit"] = actual_str
        name = registry.get_name(violation.actual_unit)
        if name:
            properties["actualUnitName"] = name

    if properties:
        result["properties"] = properties

    return result
