"""JSON output formatter for CI/CD integration.

Produces machine-readable JSON output containing:
    - Tool version and metadata
    - List of violations with locations, units, and inference chains
    - Summary statistics
"""

from __future__ import annotations

import json
from typing import Any, Optional

from unit_checker import __version__
from unit_checker.core.unit_registry import UnitRegistry, default_registry
from unit_checker.models.violations import ViolationSeverity
from unit_checker.inference.propagator import PropagationResult


def format_json(
    result: PropagationResult,
    file_path: str,
    registry: Optional[UnitRegistry] = None,
) -> str:
    """Format analysis results as JSON.

    Returns:
        JSON string with violations, summary, and metadata.
    """
    reg = registry or default_registry

    violations_json = []
    for v in result.violations:
        violation_dict: dict[str, Any] = {
            "severity": v.severity.value,
            "type": v.violation_type.value,
            "file": v.location.file,
            "line": v.location.line,
            "column": v.location.column,
            "message": v.message,
        }

        if v.expected_unit:
            violation_dict["expected_unit"] = {
                "L": float(v.expected_unit.length),
                "M": float(v.expected_unit.mass),
                "T": float(v.expected_unit.time),
                "I": float(v.expected_unit.current),
                "Th": float(v.expected_unit.temperature),
                "N": float(v.expected_unit.amount),
                "J": float(v.expected_unit.luminosity),
            }
            violation_dict["expected_unit_string"] = v.expected_unit.to_unit_string()
            name = reg.get_name(v.expected_unit)
            if name:
                violation_dict["expected_unit_name"] = name

        if v.actual_unit:
            violation_dict["actual_unit"] = {
                "L": float(v.actual_unit.length),
                "M": float(v.actual_unit.mass),
                "T": float(v.actual_unit.time),
                "I": float(v.actual_unit.current),
                "Th": float(v.actual_unit.temperature),
                "N": float(v.actual_unit.amount),
                "J": float(v.actual_unit.luminosity),
            }
            violation_dict["actual_unit_string"] = v.actual_unit.to_unit_string()
            name = reg.get_name(v.actual_unit)
            if name:
                violation_dict["actual_unit_name"] = name

        if v.inference_chain_expected:
            violation_dict["inference_chain_expected"] = [
                {
                    "variable": step.variable,
                    "unit": step.unit.to_unit_string(),
                    "reason": step.reason,
                    "line": step.location.line,
                }
                for step in v.inference_chain_expected
            ]

        if v.inference_chain_actual:
            violation_dict["inference_chain_actual"] = [
                {
                    "variable": step.variable,
                    "unit": step.unit.to_unit_string(),
                    "reason": step.reason,
                    "line": step.location.line,
                }
                for step in v.inference_chain_actual
            ]

        violations_json.append(violation_dict)

    num_errors = sum(1 for v in result.violations if v.severity == ViolationSeverity.ERROR)
    num_warnings = sum(1 for v in result.violations if v.severity == ViolationSeverity.WARNING)

    output = {
        "version": __version__,
        "file": file_path,
        "summary": {
            "errors": num_errors,
            "warnings": num_warnings,
            "variables_analyzed": len(result.inferred_units) + len(result.unknown_variables),
            "units_inferred": len(result.inferred_units),
        },
        "violations": violations_json,
    }

    return json.dumps(output, indent=2)
