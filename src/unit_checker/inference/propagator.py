"""Constraint propagation engine.

Implements a worklist-based algorithm that propagates unit information
through the constraint graph until:
    - All reachable variables have inferred units (success), or
    - A contradiction is found (unit violation), or
    - No more propagation is possible (some variables remain unknown).

The propagator tracks provenance for every inference, enabling the
conflict resolver to produce human-readable explanations.

ALGORITHM (from PLANNING.md):
    1. Initialize worklist W with all variables that have known units.
    2. For each variable v in W:
       a. For each constraint C involving v:
          i.   Evaluate C given current known units.
          ii.  If C allows inferring a new variable's unit:
               - If that variable's unit was None: set it, add to W.
               - If already set and MATCHES: no-op.
               - If already set and CONFLICTS: record Violation.
          iii. If C cannot be evaluated yet: skip, revisit later.
    3. Repeat until W is empty.
    4. Return (inferred_units, violations).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from fractions import Fraction

from unit_checker.core.unit_algebra import UnitVector
from unit_checker.models.constraints import (
    Constraint,
    EqualityConstraint,
    ProductConstraint,
    QuotientConstraint,
    PowerConstraint,
    KnownUnitConstraint,
    AdditionConstraint,
)
from unit_checker.models.violations import (
    Violation,
    ViolationSeverity,
    ViolationType,
    InferenceStep,
)
from unit_checker.parsers.common.ir import SourceLocation


@dataclass
class Provenance:
    """Records how a unit was inferred for a variable."""
    unit: UnitVector
    reason: str
    location: SourceLocation
    source_variables: list[str] = field(default_factory=list)


@dataclass
class PropagationResult:
    """Result of constraint propagation.

    Attributes:
        inferred_units: Map of qualified variable name -> inferred UnitVector.
        violations: List of detected unit violations.
        provenance: Map of qualified variable name -> how the unit was inferred.
        unknown_variables: Variables whose units could not be inferred.
    """
    inferred_units: dict[str, UnitVector] = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)
    provenance: dict[str, Provenance] = field(default_factory=dict)
    unknown_variables: set[str] = field(default_factory=set)


class ConstraintPropagator:
    """Worklist-based constraint propagation engine.

    Usage:
        propagator = ConstraintPropagator()
        result = propagator.propagate(constraints, known_units)
    """

    def __init__(self, max_iterations: int = 10000) -> None:
        self.max_iterations = max_iterations
        self._scale_warnings: list[Violation] = []

    def propagate(
        self,
        constraints: list[Constraint],
        known_units: dict[str, UnitVector],
    ) -> PropagationResult:
        """Run constraint propagation.

        Args:
            constraints: All constraints from the constraint builder.
            known_units: Initially known units (from annotations and literals).

        Returns:
            PropagationResult with inferred units and violations.
        """
        result = PropagationResult()

        # Copy known units into result
        result.inferred_units = dict(known_units)

        # Build constraint index: variable -> list of constraints involving it
        var_constraints: dict[str, list[Constraint]] = defaultdict(list)
        all_variables: set[str] = set()

        for constraint in constraints:
            for var in constraint.involved_variables():
                var_constraints[var].append(constraint)
                all_variables.add(var)

        # Record provenance for initially known units
        for var_name, unit in known_units.items():
            result.provenance[var_name] = Provenance(
                unit=unit,
                reason="annotation or literal",
                location=SourceLocation("<init>", 0, 0),
            )

        # Initialize worklist with variables that have known units
        worklist: deque[str] = deque(
            var for var in known_units if var in var_constraints
        )
        in_worklist: set[str] = set(worklist)

        iterations = 0

        while worklist and iterations < self.max_iterations:
            iterations += 1
            var = worklist.popleft()
            in_worklist.discard(var)

            # Process each constraint involving this variable
            for constraint in var_constraints[var]:
                inferences = self._evaluate_constraint(constraint, result.inferred_units)

                for inferred_var, inferred_unit, reason, source_vars in inferences:
                    existing_unit = result.inferred_units.get(inferred_var)

                    if existing_unit is None:
                        # New inference -- record it
                        result.inferred_units[inferred_var] = inferred_unit
                        result.provenance[inferred_var] = Provenance(
                            unit=inferred_unit,
                            reason=reason,
                            location=constraint.location,
                            source_variables=source_vars,
                        )
                        # Add to worklist for further propagation
                        if inferred_var not in in_worklist:
                            worklist.append(inferred_var)
                            in_worklist.add(inferred_var)

                    elif not existing_unit.dimensions_equal(inferred_unit):
                        # CONFLICT -- dimensions don't match
                        violation = self._create_violation(
                            constraint=constraint,
                            variable=inferred_var,
                            expected_unit=existing_unit,
                            actual_unit=inferred_unit,
                            result=result,
                        )
                        result.violations.append(violation)

        # Deduplicate violations by location and unit pair
        seen: set[tuple] = set()
        unique_violations: list[Violation] = []
        for v in result.violations:
            key = (
                v.location.file, v.location.line, v.location.column,
                tuple(v.expected_unit.to_list()) if v.expected_unit else (),
                tuple(v.actual_unit.to_list()) if v.actual_unit else (),
            )
            if key not in seen:
                seen.add(key)
                unique_violations.append(v)
        result.violations = unique_violations

        # Collect unknown variables
        result.unknown_variables = all_variables - set(result.inferred_units.keys())

        # Append scale/kind mismatch warnings
        result.violations.extend(self._scale_warnings)

        return result

    def _evaluate_constraint(
        self,
        constraint: Constraint,
        known_units: dict[str, UnitVector],
    ) -> list[tuple[str, UnitVector, str, list[str]]]:
        """Evaluate a constraint given current known units.

        Returns a list of (variable, unit, reason, source_vars) tuples
        for each new inference that can be made.
        """
        if isinstance(constraint, KnownUnitConstraint):
            return self._eval_known(constraint, known_units)
        elif isinstance(constraint, EqualityConstraint):
            return self._eval_equality(constraint, known_units)
        elif isinstance(constraint, AdditionConstraint):
            return self._eval_addition(constraint, known_units)
        elif isinstance(constraint, ProductConstraint):
            return self._eval_product(constraint, known_units)
        elif isinstance(constraint, QuotientConstraint):
            return self._eval_quotient(constraint, known_units)
        elif isinstance(constraint, PowerConstraint):
            return self._eval_power(constraint, known_units)
        return []

    def _eval_known(
        self,
        c: KnownUnitConstraint,
        known: dict[str, UnitVector],
    ) -> list[tuple[str, UnitVector, str, list[str]]]:
        """Known unit: unit(var) == specific_unit."""
        if c.variable not in known:
            return [(c.variable, c.unit, c.description, [])]
        # CRIT-3: If already known, check for conflict
        existing = known[c.variable]
        if not existing.dimensions_equal(c.unit):
            # Return inference that will trigger conflict detection in the main loop
            return [(c.variable, c.unit, c.description, [])]
        return []

    def _eval_equality(
        self,
        c: EqualityConstraint,
        known: dict[str, UnitVector],
    ) -> list[tuple[str, UnitVector, str, list[str]]]:
        """Equality: unit(a) == unit(b)."""
        a_unit = known.get(c.var_a)
        b_unit = known.get(c.var_b)

        results = []

        if a_unit is not None and b_unit is None:
            results.append((c.var_b, a_unit, c.description, [c.var_a]))
        elif b_unit is not None and a_unit is None:
            results.append((c.var_a, b_unit, c.description, [c.var_b]))
        elif a_unit is not None and b_unit is not None:
            # Both known: check for conflict
            if not a_unit.dimensions_equal(b_unit):
                # Report as inference on b using a's unit -> triggers conflict
                results.append((c.var_b, a_unit, c.description, [c.var_a]))

        return results

    def _eval_addition(
        self,
        c: AdditionConstraint,
        known: dict[str, UnitVector],
    ) -> list[tuple[str, UnitVector, str, list[str]]]:
        """Addition: unit(result) == unit(left) == unit(right).

        All three must have the same dimensions.
        This also checks for conflicts when both operands are known
        but have different dimensions.
        """
        left_unit = known.get(c.left)
        right_unit = known.get(c.right)
        result_unit = known.get(c.result)

        results = []

        # Check for conflict between the two operands when both are known
        if left_unit is not None and right_unit is not None:
            if not left_unit.dimensions_equal(right_unit):
                # Both operands known with different dimensions -> violation.
                # Report this as an inference on the right operand using the
                # left operand's unit, which will conflict with the right's
                # existing unit and trigger a violation in the main loop.
                results.append((
                    c.right, left_unit,
                    f"Addition requires same units: must match [{left_unit.to_unit_string()}]",
                    [c.left],
                ))
                return results

            # Dimensions match, but check scale factor and kind compatibility
            if not left_unit.scale_compatible_with(right_unit):
                # Scale mismatch warning (e.g., adding km to m)
                self._scale_warnings.append(Violation(
                    severity=ViolationSeverity.WARNING,
                    violation_type=ViolationType.ADDITION_MISMATCH,
                    location=c.location,
                    message=(
                        f"Possible unit scale mismatch in addition: "
                        f"left operand has scale {left_unit.scale_factor}, "
                        f"right operand has scale {right_unit.scale_factor}. "
                        f"Check if a conversion factor is needed."
                    ),
                    expected_unit=left_unit,
                    actual_unit=right_unit,
                ))
            if not left_unit._kinds_compatible(right_unit):
                # Kind mismatch (e.g., adding angle to pure dimensionless)
                self._scale_warnings.append(Violation(
                    severity=ViolationSeverity.WARNING,
                    violation_type=ViolationType.ADDITION_MISMATCH,
                    location=c.location,
                    message=(
                        f"Unit kind mismatch in addition: "
                        f"left has kind={left_unit.kind!r}, "
                        f"right has kind={right_unit.kind!r}."
                    ),
                    expected_unit=left_unit,
                    actual_unit=right_unit,
                ))

        # Find the first known unit among the three
        known_unit = left_unit or right_unit or result_unit
        known_source: list[str] = []

        if known_unit is None:
            return []

        if left_unit is not None:
            known_source = [c.left]
        elif right_unit is not None:
            known_source = [c.right]
        elif result_unit is not None:
            known_source = [c.result]

        # Propagate to unknowns
        if left_unit is None:
            results.append((c.left, known_unit, f"Addition: must match {known_source}", known_source))
        if right_unit is None:
            results.append((c.right, known_unit, f"Addition: must match {known_source}", known_source))
        if result_unit is None:
            results.append((c.result, known_unit, "Addition: result has same unit", known_source))

        return results

    def _eval_product(
        self,
        c: ProductConstraint,
        known: dict[str, UnitVector],
    ) -> list[tuple[str, UnitVector, str, list[str]]]:
        """Product: unit(result) == unit(a) + unit(b) [dimension addition].

        Three propagation directions:
            a, b known -> infer result = a + b
            result, b known -> infer a = result - b
            result, a known -> infer b = result - a
        """
        a_unit = known.get(c.operand_a)
        b_unit = known.get(c.operand_b)
        result_unit = known.get(c.result)

        results = []

        if a_unit is not None and b_unit is not None:
            inferred = a_unit.multiply(b_unit)
            if result_unit is None:
                results.append((c.result, inferred,
                               f"Product of {c.operand_a} and {c.operand_b}",
                               [c.operand_a, c.operand_b]))
            elif not result_unit.dimensions_equal(inferred):
                # All three known, but product doesn't match result
                results.append((c.result, inferred,
                               f"Product of {c.operand_a} and {c.operand_b}",
                               [c.operand_a, c.operand_b]))

        elif result_unit is not None and b_unit is not None and a_unit is None:
            inferred = result_unit.divide(b_unit)
            results.append((c.operand_a, inferred,
                           f"Inferred from {c.result} / {c.operand_b}",
                           [c.result, c.operand_b]))

        elif result_unit is not None and a_unit is not None and b_unit is None:
            inferred = result_unit.divide(a_unit)
            results.append((c.operand_b, inferred,
                           f"Inferred from {c.result} / {c.operand_a}",
                           [c.result, c.operand_a]))

        return results

    def _eval_quotient(
        self,
        c: QuotientConstraint,
        known: dict[str, UnitVector],
    ) -> list[tuple[str, UnitVector, str, list[str]]]:
        """Quotient: unit(result) == unit(num) - unit(den) [dimension subtraction].

        Three propagation directions:
            num, den known -> infer result = num - den
            result, den known -> infer num = result + den
            result, num known -> infer den = num - result
        """
        num_unit = known.get(c.numerator)
        den_unit = known.get(c.denominator)
        result_unit = known.get(c.result)

        results = []

        if num_unit is not None and den_unit is not None:
            inferred = num_unit.divide(den_unit)
            if result_unit is None:
                results.append((c.result, inferred,
                               f"Quotient of {c.numerator} / {c.denominator}",
                               [c.numerator, c.denominator]))
            elif not result_unit.dimensions_equal(inferred):
                results.append((c.result, inferred,
                               f"Quotient of {c.numerator} / {c.denominator}",
                               [c.numerator, c.denominator]))

        elif result_unit is not None and den_unit is not None and num_unit is None:
            inferred = result_unit.multiply(den_unit)
            results.append((c.numerator, inferred,
                           f"Inferred from {c.result} * {c.denominator}",
                           [c.result, c.denominator]))

        elif result_unit is not None and num_unit is not None and den_unit is None:
            inferred = num_unit.divide(result_unit)
            results.append((c.denominator, inferred,
                           f"Inferred from {c.numerator} / {c.result}",
                           [c.numerator, c.result]))

        return results

    def _eval_power(
        self,
        c: PowerConstraint,
        known: dict[str, UnitVector],
    ) -> list[tuple[str, UnitVector, str, list[str]]]:
        """Power: unit(result) == exponent * unit(base) [dimension scaling].

        Two propagation directions:
            base known -> infer result = exp * base
            result known, exp != 0 -> infer base = result / exp
        """
        base_unit = known.get(c.base)
        result_unit = known.get(c.result)

        results = []

        if base_unit is not None:
            inferred = base_unit.power(c.exponent)
            if result_unit is None:
                results.append((c.result, inferred,
                               f"Power: {c.base} ^ {c.exponent}",
                               [c.base]))
            elif not result_unit.dimensions_equal(inferred):
                results.append((c.result, inferred,
                               f"Power: {c.base} ^ {c.exponent}",
                               [c.base]))

        elif result_unit is not None and base_unit is None and c.exponent != 0:
            inv_exp = Fraction(1) / c.exponent
            inferred = result_unit.power(inv_exp)
            results.append((c.base, inferred,
                           f"Inverse power: {c.result} ^ (1/{c.exponent})",
                           [c.result]))

        return results

    def _create_violation(
        self,
        constraint: Constraint,
        variable: str,
        expected_unit: UnitVector,
        actual_unit: UnitVector,
        result: PropagationResult,
    ) -> Violation:
        """Create a Violation object with provenance chains."""
        # Build inference chains
        expected_chain = self._build_inference_chain(variable, result.provenance)
        actual_chain = [InferenceStep(
            variable=variable,
            unit=actual_unit,
            reason=constraint.description,
            location=constraint.location,
        )]

        # Determine violation type from constraint type
        if isinstance(constraint, AdditionConstraint):
            vtype = ViolationType.ADDITION_MISMATCH
        elif isinstance(constraint, EqualityConstraint):
            vtype = ViolationType.ASSIGNMENT_MISMATCH
        else:
            vtype = ViolationType.CONFLICTING_CONSTRAINTS

        # Create physics-language message
        message = self._format_violation_message(
            vtype, variable, expected_unit, actual_unit, constraint
        )

        return Violation(
            severity=ViolationSeverity.ERROR,
            violation_type=vtype,
            location=constraint.location,
            message=message,
            expected_unit=expected_unit,
            actual_unit=actual_unit,
            inference_chain_expected=expected_chain,
            inference_chain_actual=actual_chain,
        )

    def _build_inference_chain(
        self,
        variable: str,
        provenance: dict[str, Provenance],
        max_depth: int = 10,
    ) -> list[InferenceStep]:
        """Build the chain of inferences that led to a variable's unit."""
        chain: list[InferenceStep] = []
        visited: set[str] = set()
        current = variable

        for _ in range(max_depth):
            if current in visited or current not in provenance:
                break
            visited.add(current)

            prov = provenance[current]
            chain.append(InferenceStep(
                variable=current,
                unit=prov.unit,
                reason=prov.reason,
                location=prov.location,
            ))

            if prov.source_variables:
                current = prov.source_variables[0]
            else:
                break

        return chain

    def _format_violation_message(
        self,
        vtype: ViolationType,
        variable: str,
        expected: UnitVector,
        actual: UnitVector,
        constraint: Constraint,
    ) -> str:
        """Create a physics-language error message."""
        expected_str = expected.to_unit_string()
        actual_str = actual.to_unit_string()

        # Clean up variable name for display
        display_var = variable.split("::")[-1] if "::" in variable else variable
        if display_var.startswith("__temp_"):
            display_var = "<expression>"

        if vtype == ViolationType.ADDITION_MISMATCH:
            return (
                f"Unit mismatch in addition/subtraction: "
                f"cannot combine [{expected_str}] with [{actual_str}]"
            )
        elif vtype == ViolationType.ASSIGNMENT_MISMATCH:
            return (
                f"Conflicting units for '{display_var}': "
                f"expected [{expected_str}], got [{actual_str}]"
            )
        else:
            return (
                f"Conflicting unit constraints for '{display_var}': "
                f"[{expected_str}] vs [{actual_str}]"
            )
