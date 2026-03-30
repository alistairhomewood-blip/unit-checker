"""Violation data model.

Represents unit consistency violations found during analysis.
Each violation includes:
    - Where it occurred (file, line, column)
    - What was expected vs what was found
    - How each unit was inferred (provenance chain)
    - A physics-language explanation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from unit_checker.core.unit_algebra import UnitVector
from unit_checker.parsers.common.ir import SourceLocation


class ViolationSeverity(Enum):
    """Severity level of a violation."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ViolationType(Enum):
    """Type of unit violation."""
    ADDITION_MISMATCH = "addition_mismatch"
    ASSIGNMENT_MISMATCH = "assignment_mismatch"
    FUNCTION_ARG_MISMATCH = "function_argument_mismatch"
    RETURN_MISMATCH = "return_mismatch"
    COMPARISON_MISMATCH = "comparison_mismatch"
    CONFLICTING_CONSTRAINTS = "conflicting_constraints"


@dataclass(frozen=True)
class InferenceStep:
    """One step in the chain explaining how a unit was inferred.

    Example chain:
        'velocity' is [m/s] because:
            Line 8: velocity annotated as [m/s]       <- KnownStep
        'distance' is [m] because:
            Line 10: distance = velocity * time        <- InferredStep
            Line 8: velocity is [m/s] (annotation)
            Line 9: time is [s] (annotation)
    """
    variable: str          # Variable name
    unit: UnitVector       # The unit at this step
    reason: str            # Human-readable reason
    location: SourceLocation


@dataclass
class Violation:
    """A unit consistency violation.

    Attributes:
        severity: error, warning, or info
        violation_type: What kind of mismatch
        location: Where in source code
        message: Human-readable physics-language message
        expected_unit: What the unit should be
        actual_unit: What the unit actually is
        inference_chain_expected: How expected_unit was derived
        inference_chain_actual: How actual_unit was derived
        source_line: The actual line of source code (for display)
        expression_text: The specific expression that has the mismatch
    """
    severity: ViolationSeverity
    violation_type: ViolationType
    location: SourceLocation
    message: str
    expected_unit: Optional[UnitVector] = None
    actual_unit: Optional[UnitVector] = None
    inference_chain_expected: list[InferenceStep] = field(default_factory=list)
    inference_chain_actual: list[InferenceStep] = field(default_factory=list)
    source_line: Optional[str] = None
    expression_text: Optional[str] = None
