"""Conflict resolver: traces propagation chains to explain violations.

When the propagator finds a contradiction, this module produces
a minimal, human-readable explanation showing how two conflicting
units were derived from the original annotations.
"""

from __future__ import annotations

from typing import Optional

from unit_checker.core.unit_registry import UnitRegistry, default_registry
from unit_checker.models.violations import Violation
from unit_checker.inference.propagator import PropagationResult


def enrich_violation(
    violation: Violation,
    result: PropagationResult,
    registry: Optional[UnitRegistry] = None,
    source_lines: Optional[dict[str, list[str]]] = None,
) -> Violation:
    """Enrich a violation with additional context.

    Adds:
        - Named unit equivalents (e.g., "N = kg*m/s^2")
        - Source code lines
        - More detailed inference chains
    """
    reg = registry or default_registry

    # Enrich unit display with named units
    if violation.expected_unit:
        expected_name = reg.get_name(violation.expected_unit)
        actual_name = reg.get_name(violation.actual_unit) if violation.actual_unit else None

        expected_str = violation.expected_unit.to_unit_string()
        actual_str = violation.actual_unit.to_unit_string() if violation.actual_unit else "unknown"

        if expected_name and expected_name != expected_str:
            expected_display = f"{expected_name} = {expected_str}"
        else:
            expected_display = expected_str

        if actual_name and actual_name != actual_str:
            actual_display = f"{actual_name} = {actual_str}"
        else:
            actual_display = actual_str

        # Rebuild message with named units
        violation.message = violation.message.replace(
            f"[{expected_str}]", f"[{expected_display}]"
        ).replace(
            f"[{actual_str}]", f"[{actual_display}]"
        )

    # Add source line context
    if source_lines and violation.location.file in source_lines:
        lines = source_lines[violation.location.file]
        line_idx = violation.location.line - 1
        if 0 <= line_idx < len(lines):
            violation.source_line = lines[line_idx]

    return violation
