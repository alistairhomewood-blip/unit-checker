"""Constraint builder: walks the IR and generates unit constraints.

This is the bridge between parsing and inference. It takes an IRModule
and produces a set of constraints that the propagator will solve.

Constraint generation rules:
    c = a          -> EqualityConstraint(c, a)
    c = a + b      -> AdditionConstraint(c, a, b)
    c = a - b      -> AdditionConstraint(c, a, b)
    c = a * b      -> ProductConstraint(c, a, b)
    c = a / b      -> QuotientConstraint(c, a, b)
    c = a ** n     -> PowerConstraint(c, a, n)
    f(x) with f(a) -> EqualityConstraint(x, a) for each param-arg pair
    return expr    -> EqualityConstraint(__return_f__, expr)
    annotation     -> KnownUnitConstraint(var, unit)
"""

from __future__ import annotations

from fractions import Fraction
from typing import Optional

from unit_checker.core.unit_algebra import UnitVector, DIMENSIONLESS
from unit_checker.core.unit_registry import UnitRegistry, default_registry
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
)
from unit_checker.parsers.common.ir import (
    SourceLocation,
    BinaryOperator,
    UnaryOperator,
    IRModule,
    IRFunction,
    IRVariable,
    IRExpression,
    IRVariableRef,
    IRLiteral,
    IRBinaryOp,
    IRUnaryOp,
    IRCallExpr,
    IRComparison,
    IRStatement,
    IRAssignment,
    IRReturn,
    IRAugmentedAssignment,
)


class ConstraintBuilder:
    """Builds unit constraints from an IR module.

    The builder walks the IR, creating constraints for each statement
    and expression. It also resolves unit annotations using the registry.

    Usage:
        builder = ConstraintBuilder(registry=default_registry)
        constraints, var_map = builder.build(ir_module)
    """

    def __init__(self, registry: Optional[UnitRegistry] = None) -> None:
        self.registry = registry or default_registry
        self._constraints: list[Constraint] = []
        self._var_units: dict[str, UnitVector] = {}  # qualified_name -> known unit
        self._violations: list[Violation] = []  # violations detected during building
        self._temp_counter = 0
        self._functions: dict[str, IRFunction] = {}  # function name -> IRFunction
        self._source_lines: dict[str, list[str]] = {}

    def build(self, module: IRModule, source: Optional[str] = None) -> tuple[list[Constraint], dict[str, UnitVector]]:
        """Build constraints from an IR module.

        Args:
            module: The IR module to process.
            source: Optional source code (for reading inline annotations).

        Returns:
            Tuple of (constraints, known_units) where known_units maps
            qualified variable names to their known UnitVectors.
        """
        self._constraints = []
        self._var_units = {}
        self._violations = []

        if source:
            self._source_lines[module.file_path] = source.splitlines()

        # Index functions for call resolution
        for func in module.functions:
            self._functions[func.name] = func

        # Process annotations first -> KnownUnitConstraints
        self._process_annotations(module)

        # Process global statements
        for stmt in module.global_statements:
            self._visit_statement(stmt, "global")

        # Process function bodies
        for func in module.functions:
            scope = f"local:{func.name}"
            for stmt in func.body:
                self._visit_statement(stmt, scope)

        return self._constraints, self._var_units

    @property
    def violations(self) -> list[Violation]:
        """Return violations detected during constraint building.

        Includes warnings for unparseable annotations and errors for
        conflicting annotations on the same variable.
        """
        return list(self._violations)

    def _process_annotations(self, module: IRModule) -> None:
        """Convert IR annotations into KnownUnitConstraints."""
        for ann in module.annotations:
            try:
                unit = self.registry.parse_unit_string(ann.unit_string)
            except ValueError:
                # MED-1: Record a warning for unparseable annotations
                self._violations.append(Violation(
                    severity=ViolationSeverity.WARNING,
                    violation_type=ViolationType.CONFLICTING_CONSTRAINTS,
                    location=ann.location,
                    message=f"Could not parse unit annotation '{ann.unit_string}' on line {ann.location.line}",
                ))
                continue

            # Resolve scope: annotations marked __pending__ need scope resolution
            scope = ann.scope
            if scope == "__pending__":
                # Try to find the variable in known scopes
                scope = self._resolve_annotation_scope(ann.variable_name, module)

            qualified_name = f"{scope}::{ann.variable_name}"

            # CRIT-3: Detect conflicting annotations
            existing_unit = self._var_units.get(qualified_name)
            if existing_unit is not None and not existing_unit.dimensions_equal(unit):
                self._violations.append(Violation(
                    severity=ViolationSeverity.ERROR,
                    violation_type=ViolationType.CONFLICTING_CONSTRAINTS,
                    location=ann.location,
                    message=(
                        f"Conflicting annotations for '{ann.variable_name}': "
                        f"previously declared as [{existing_unit.to_unit_string()}], "
                        f"now declared as [{unit.to_unit_string()}]"
                    ),
                    expected_unit=existing_unit,
                    actual_unit=unit,
                ))

            self._var_units[qualified_name] = unit

            self._constraints.append(KnownUnitConstraint(
                variable=qualified_name,
                unit=unit,
                location=ann.location,
                description=f"Annotation: {ann.variable_name} has unit [{ann.unit_string}]",
            ))

    def _resolve_annotation_scope(self, var_name: str, module: IRModule) -> str:
        """Resolve the scope for an annotation.

        Check if the variable name appears as:
        1. A global statement target -> "global"
        2. A function parameter -> "param:<func>"
        3. A function local variable -> "local:<func>"

        Prioritizes global scope because annotations typically appear
        on global assignments (e.g., `distance = 100.0  # unit: m`).
        """
        # First check global statements
        for stmt in module.global_statements:
            if isinstance(stmt, IRAssignment) and stmt.target.name == var_name:
                return "global"

        # Then check function parameters and locals
        for func in module.functions:
            for param in func.parameters:
                if param.name == var_name:
                    return f"param:{func.name}"
            for stmt in func.body:
                if isinstance(stmt, IRAssignment) and stmt.target.name == var_name:
                    return f"local:{func.name}"

        return "global"

    def _visit_statement(self, stmt: IRStatement, scope: str) -> None:
        """Generate constraints for a statement."""
        if isinstance(stmt, IRAssignment):
            self._visit_assignment(stmt, scope)
        elif isinstance(stmt, IRReturn):
            self._visit_return(stmt, scope)
        elif isinstance(stmt, IRAugmentedAssignment):
            self._visit_aug_assignment(stmt, scope)

    def _visit_assignment(self, stmt: IRAssignment, scope: str) -> None:
        """Generate constraints for: target = expression."""
        target_name = self._qualified_name(stmt.target, scope)
        expr_name = self._visit_expression(stmt.expression, scope, stmt.location)

        if expr_name is not None:
            self._constraints.append(EqualityConstraint(
                var_a=target_name,
                var_b=expr_name,
                location=stmt.location,
                description=f"Assignment: {stmt.target.name} = <expr>",
            ))

    def _visit_return(self, stmt: IRReturn, scope: str) -> None:
        """Generate constraints for: return expression."""
        expr_name = self._visit_expression(stmt.expression, scope, stmt.location)
        if expr_name is None:
            return

        # Find which function this return belongs to
        func_name = self._scope_to_func_name(scope)
        if func_name:
            return_var = f"local:{func_name}::__return_{func_name}__"
            self._constraints.append(EqualityConstraint(
                var_a=return_var,
                var_b=expr_name,
                location=stmt.location,
                description=f"Return value of {func_name}",
            ))

    def _visit_aug_assignment(self, stmt: IRAugmentedAssignment, scope: str) -> None:
        """Generate constraints for: target op= expression.

        target += expr  =>  target_new = target_old + expr (addition constraint)
        target *= expr  =>  target_new = target_old * expr (product constraint)
        etc.
        """
        target_name = self._qualified_name(stmt.target, scope)
        expr_name = self._visit_expression(stmt.expression, scope, stmt.location)
        if expr_name is None:
            return

        # For += and -=, this is an addition constraint
        if stmt.operator in (BinaryOperator.ADD, BinaryOperator.SUB):
            self._constraints.append(AdditionConstraint(
                result=target_name,
                left=target_name,
                right=expr_name,
                location=stmt.location,
                description=f"Augmented assignment: {stmt.target.name} {stmt.operator.value}= <expr>",
            ))
        elif stmt.operator == BinaryOperator.MUL:
            temp = self._next_temp(scope)
            self._constraints.append(ProductConstraint(
                result=temp,
                operand_a=target_name,
                operand_b=expr_name,
                location=stmt.location,
                description=f"Augmented assignment: {stmt.target.name} *= <expr>",
            ))
            self._constraints.append(EqualityConstraint(
                var_a=target_name,
                var_b=temp,
                location=stmt.location,
                description=f"Augmented assignment result: {stmt.target.name} *= <expr>",
            ))
        elif stmt.operator == BinaryOperator.DIV:
            temp = self._next_temp(scope)
            self._constraints.append(QuotientConstraint(
                result=temp,
                numerator=target_name,
                denominator=expr_name,
                location=stmt.location,
                description=f"Augmented assignment: {stmt.target.name} /= <expr>",
            ))
            self._constraints.append(EqualityConstraint(
                var_a=target_name,
                var_b=temp,
                location=stmt.location,
                description=f"Augmented assignment result: {stmt.target.name} /= <expr>",
            ))

    def _visit_expression(self, expr: IRExpression, scope: str, loc: SourceLocation) -> Optional[str]:
        """Generate constraints for an expression, returning its representative variable name.

        For simple references, returns the variable's qualified name.
        For complex expressions, creates temporary variables with appropriate constraints.
        Returns None if the expression cannot be analyzed.
        """
        if isinstance(expr, IRVariableRef):
            return self._qualified_name(expr.variable, scope)

        if isinstance(expr, IRLiteral):
            # Numeric literals are unconstrained by default when in
            # assignment context (allows annotated variables like
            # `velocity = 10.0  # unit: m/s`).
            # In binary operation context (multiplication, division, addition),
            # the constraint_builder handles them specially via _visit_binop.
            temp = self._next_temp(scope)
            return temp

        if isinstance(expr, IRBinaryOp):
            return self._visit_binop(expr, scope)

        if isinstance(expr, IRUnaryOp):
            return self._visit_unaryop(expr, scope)

        if isinstance(expr, IRCallExpr):
            return self._visit_call(expr, scope)

        if isinstance(expr, IRComparison):
            return self._visit_comparison(expr, scope)

        return None

    def _visit_binop(self, expr: IRBinaryOp, scope: str) -> Optional[str]:
        """Generate constraints for a binary operation."""
        left_name = self._visit_expression(expr.left, scope, expr.location)
        right_name = self._visit_expression(expr.right, scope, expr.location)

        if left_name is None or right_name is None:
            return None

        # Mark literal operands as dimensionless in multiplication/division.
        # In `0.5 * mass * velocity ** 2`, the 0.5 is a scaling factor (dimensionless).
        # But in `velocity = 10.0  # unit: m/s`, the literal adopts the annotation.
        # Note: for POW, the exponent is handled separately by _extract_constant_exponent,
        # so we only mark the base as dimensionless if it's a literal.
        if expr.operator in (BinaryOperator.MUL, BinaryOperator.DIV,
                             BinaryOperator.FLOOR_DIV):
            if isinstance(expr.left, IRLiteral):
                self._mark_dimensionless(left_name, expr.location)
            if isinstance(expr.right, IRLiteral):
                self._mark_dimensionless(right_name, expr.location)

        result_name = self._next_temp(scope)

        if expr.operator in (BinaryOperator.ADD, BinaryOperator.SUB):
            # Addition/subtraction: all must have same dimensions
            self._constraints.append(AdditionConstraint(
                result=result_name,
                left=left_name,
                right=right_name,
                location=expr.location,
                description="Addition/subtraction: dimensions must match",
            ))

        elif expr.operator == BinaryOperator.MUL:
            self._constraints.append(ProductConstraint(
                result=result_name,
                operand_a=left_name,
                operand_b=right_name,
                location=expr.location,
                description="Multiplication: dimensions add",
            ))

        elif expr.operator in (BinaryOperator.DIV, BinaryOperator.FLOOR_DIV):
            self._constraints.append(QuotientConstraint(
                result=result_name,
                numerator=left_name,
                denominator=right_name,
                location=expr.location,
                description="Division: dimensions subtract",
            ))

        elif expr.operator == BinaryOperator.POW:
            # Power: the exponent must be a known constant
            exponent = self._extract_constant_exponent(expr.right)
            if exponent is not None:
                self._constraints.append(PowerConstraint(
                    result=result_name,
                    base=left_name,
                    exponent=exponent,
                    location=expr.location,
                    description=f"Exponentiation: dimensions scale by {exponent}",
                ))
            else:
                # Non-constant exponent: require base to be dimensionless
                self._constraints.append(KnownUnitConstraint(
                    variable=left_name,
                    unit=DIMENSIONLESS,
                    location=expr.location,
                    description="Non-constant exponent: base must be dimensionless",
                ))
                self._var_units[result_name] = DIMENSIONLESS
                self._constraints.append(KnownUnitConstraint(
                    variable=result_name,
                    unit=DIMENSIONLESS,
                    location=expr.location,
                    description="Non-constant exponent: result is dimensionless",
                ))

        elif expr.operator == BinaryOperator.MOD:
            # Modulo: same as division for dimensional analysis (result has same units as numerator)
            # Actually, x % y requires same units and produces same units
            self._constraints.append(AdditionConstraint(
                result=result_name,
                left=left_name,
                right=right_name,
                location=expr.location,
                description="Modulo: dimensions must match",
            ))

        return result_name

    def _visit_unaryop(self, expr: IRUnaryOp, scope: str) -> Optional[str]:
        """Generate constraints for a unary operation.

        Unary +/- preserves the unit of the operand.
        """
        operand_name = self._visit_expression(expr.operand, scope, expr.location)
        if operand_name is None:
            return None

        result_name = self._next_temp(scope)
        self._constraints.append(EqualityConstraint(
            var_a=result_name,
            var_b=operand_name,
            location=expr.location,
            description=f"Unary {expr.operator.value}: preserves unit",
        ))
        return result_name

    def _visit_call(self, expr: IRCallExpr, scope: str) -> Optional[str]:
        """Generate constraints for a function call.

        For known functions (defined in the same module), creates constraints
        mapping arguments to parameters and the result to the return value.
        """
        result_name = self._next_temp(scope)

        # Check for built-in math functions
        builtin_result = self._handle_builtin_call(expr, scope, result_name)
        if builtin_result:
            return result_name

        # Check if function is defined in this module
        func = self._functions.get(expr.function_name)
        if func is None:
            # Unknown function -- result is unconstrained
            return result_name

        # Map arguments to parameters
        for i, (param, arg) in enumerate(zip(func.parameters, expr.arguments)):
            arg_name = self._visit_expression(arg, scope, expr.location)
            if arg_name is not None:
                param_name = f"param:{func.name}::{param.name}"
                self._constraints.append(EqualityConstraint(
                    var_a=param_name,
                    var_b=arg_name,
                    location=expr.location,
                    description=f"Function call: {func.name}() arg {i} ({param.name})",
                ))

        # Map result to return value
        return_var = f"local:{func.name}::__return_{func.name}__"
        self._constraints.append(EqualityConstraint(
            var_a=result_name,
            var_b=return_var,
            location=expr.location,
            description=f"Function call: result of {func.name}()",
        ))

        return result_name

    def _handle_builtin_call(self, expr: IRCallExpr, scope: str, result_name: str) -> bool:
        """Handle built-in math functions with known unit behavior.

        Returns True if the call was handled, False otherwise.
        """
        name = expr.function_name

        # sqrt(x) => result = x^(1/2)
        if name in ("math.sqrt", "sqrt", "np.sqrt", "numpy.sqrt",
                     "std::sqrt", "sqrtf", "sqrtl"):
            if expr.arguments:
                arg_name = self._visit_expression(expr.arguments[0], scope, expr.location)
                if arg_name:
                    self._constraints.append(PowerConstraint(
                        result=result_name,
                        base=arg_name,
                        exponent=Fraction(1, 2),
                        location=expr.location,
                        description="sqrt(): result = arg^(1/2)",
                    ))
                    return True

        # cbrt(x) => result = x^(1/3)
        if name in ("cbrt", "std::cbrt"):
            if expr.arguments:
                arg_name = self._visit_expression(expr.arguments[0], scope, expr.location)
                if arg_name:
                    self._constraints.append(PowerConstraint(
                        result=result_name,
                        base=arg_name,
                        exponent=Fraction(1, 3),
                        location=expr.location,
                        description="cbrt(): result = arg^(1/3)",
                    ))
                    return True

        # abs(x) => result has same unit as x
        if name in ("abs", "math.fabs", "np.abs", "numpy.abs",
                     "std::abs", "std::fabs", "fabsf"):
            if expr.arguments:
                arg_name = self._visit_expression(expr.arguments[0], scope, expr.location)
                if arg_name:
                    self._constraints.append(EqualityConstraint(
                        var_a=result_name,
                        var_b=arg_name,
                        location=expr.location,
                        description=f"{name}(): preserves unit",
                    ))
                    return True

        # Trig functions: sin, cos, tan etc. -- arg should be dimensionless, result is dimensionless
        trig_names = {
            "math.sin", "math.cos", "math.tan",
            "math.asin", "math.acos", "math.atan",
            "np.sin", "np.cos", "np.tan",
            "numpy.sin", "numpy.cos", "numpy.tan",
            "sin", "cos", "tan",
            "std::sin", "std::cos", "std::tan",
            "sinf", "cosf", "tanf",
            "std::asin", "std::acos", "std::atan",
        }
        if name in trig_names:
            if expr.arguments:
                arg_name = self._visit_expression(expr.arguments[0], scope, expr.location)
                if arg_name:
                    self._constraints.append(KnownUnitConstraint(
                        variable=arg_name,
                        unit=DIMENSIONLESS,
                        location=expr.location,
                        description=f"{name}(): argument must be dimensionless",
                    ))
            self._var_units[result_name] = DIMENSIONLESS
            self._constraints.append(KnownUnitConstraint(
                variable=result_name,
                unit=DIMENSIONLESS,
                location=expr.location,
                description=f"{name}(): result is dimensionless",
            ))
            return True

        # exp, log: argument and result must be dimensionless
        exp_log_names = {
            "math.exp", "math.log", "math.log10", "math.log2",
            "np.exp", "np.log", "np.log10", "np.log2",
            "numpy.exp", "numpy.log", "numpy.log10", "numpy.log2",
            "exp", "log",
            "std::exp", "std::log", "std::log10", "std::log2",
        }
        if name in exp_log_names:
            if expr.arguments:
                arg_name = self._visit_expression(expr.arguments[0], scope, expr.location)
                if arg_name:
                    self._constraints.append(KnownUnitConstraint(
                        variable=arg_name,
                        unit=DIMENSIONLESS,
                        location=expr.location,
                        description=f"{name}(): argument must be dimensionless",
                    ))
            self._var_units[result_name] = DIMENSIONLESS
            self._constraints.append(KnownUnitConstraint(
                variable=result_name,
                unit=DIMENSIONLESS,
                location=expr.location,
                description=f"{name}(): result is dimensionless",
            ))
            return True

        return False

    def _visit_comparison(self, expr: IRComparison, scope: str) -> Optional[str]:
        """Generate constraints for a comparison.

        Comparisons require both sides to have the same unit.
        Result is boolean (dimensionless).
        """
        left_name = self._visit_expression(expr.left, scope, expr.location)
        right_name = self._visit_expression(expr.right, scope, expr.location)

        if left_name and right_name:
            self._constraints.append(EqualityConstraint(
                var_a=left_name,
                var_b=right_name,
                location=expr.location,
                description="Comparison: both sides must have same unit",
            ))

        # Result is boolean/dimensionless
        result_name = self._next_temp(scope)
        self._var_units[result_name] = DIMENSIONLESS
        self._constraints.append(KnownUnitConstraint(
            variable=result_name,
            unit=DIMENSIONLESS,
            location=expr.location,
            description="Comparison result is boolean",
        ))
        return result_name

    def _extract_constant_exponent(self, expr: IRExpression) -> Optional[Fraction]:
        """Try to extract a constant exponent from an expression."""
        if isinstance(expr, IRLiteral):
            return Fraction(expr.value).limit_denominator(1000)
        if isinstance(expr, IRUnaryOp) and expr.operator == UnaryOperator.NEG:
            inner = self._extract_constant_exponent(expr.operand)
            if inner is not None:
                return -inner
        return None

    def _qualified_name(self, var: IRVariable, scope: str) -> str:
        """Get the qualified name for a variable.

        If the variable has its own scope set, use that.
        Otherwise, use the provided scope.
        """
        if var.scope and var.scope != "global":
            return f"{var.scope}::{var.name}"
        return f"{scope}::{var.name}"

    def _scope_to_func_name(self, scope: str) -> Optional[str]:
        """Extract function name from scope string."""
        if scope.startswith("local:"):
            return scope[6:]
        return None

    def _mark_dimensionless(self, var_name: str, location: SourceLocation) -> None:
        """Mark a variable as dimensionless (for numeric literals in operations)."""
        if var_name not in self._var_units:
            self._var_units[var_name] = DIMENSIONLESS
            self._constraints.append(KnownUnitConstraint(
                variable=var_name,
                unit=DIMENSIONLESS,
                location=location,
                description="Numeric literal (dimensionless scaling factor)",
            ))

    def _next_temp(self, scope: str) -> str:
        """Generate a unique temporary variable name."""
        self._temp_counter += 1
        return f"{scope}::__temp_{self._temp_counter}__"
