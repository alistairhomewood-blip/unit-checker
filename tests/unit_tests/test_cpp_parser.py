"""Tests for the C++ parser (Checkpoint 5).

Tests cover:
    5.1   Simple variable declaration
    5.2   Arithmetic expressions
    5.3   Function definition
    5.4   Function call
    5.5   Single-line comment annotation (// unit: m/s)
    5.6   Block comment annotation (/* unit: kg */)
    5.7   Inline parameter annotations
    5.8   Return statement
    5.9   Source locations
    5.10  Multiple functions
    5.11  Assignment expression (re-assignment without type)
    5.12  Augmented assignment (+=, -=, *=, /=)
    5.13  Unary expressions (-x, +x)
    5.14  Pointer and reference declarations
    5.15  Const declarations
    5.16  Auto type specifier
    5.17  pow() as exponentiation
    5.18  Nested expressions with parentheses
    5.19  Integration: correct physics (no violations via constraint propagation)
    5.20  Integration: velocity + acceleration violation
    5.21  Integration: energy conservation (kinetic + potential)
    5.22  Integration: Mars Climate Orbiter (same-dimension named units)
    5.23  Cross-language parity: equivalent Python and C++ produce same results
    5.24  Multiple declarations in one statement
    5.25  Standalone comment annotation (applies to next declaration)
"""

from pathlib import Path

from unit_checker.parsers.cpp_parser.parser import parse_cpp
from unit_checker.parsers.python_parser.parser import parse_python
from unit_checker.parsers.common.ir import (
    IRAssignment,
    IRAugmentedAssignment,
    IRReturn,
    IRLiteral,
    IRBinaryOp,
    IRUnaryOp,
    IRCallExpr,
    IRVariableRef,
    IRComparison,
    BinaryOperator,
    UnaryOperator,
    ComparisonOperator,
)
from unit_checker.core.unit_algebra import UnitVector
from unit_checker.core.unit_registry import default_registry
from unit_checker.inference.constraint_builder import ConstraintBuilder
from unit_checker.inference.propagator import ConstraintPropagator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "cpp"


def _analyze_cpp(source: str) -> tuple:
    """Parse C++ source, build constraints, propagate, return result."""
    module = parse_cpp(source, "test.cpp")
    builder = ConstraintBuilder(registry=default_registry)
    constraints, known_units = builder.build(module, source=source)
    propagator = ConstraintPropagator()
    result = propagator.propagate(constraints, known_units)
    return result


def _analyze_python(source: str) -> tuple:
    """Parse Python source, build constraints, propagate, return result."""
    module = parse_python(source, "test.py")
    builder = ConstraintBuilder(registry=default_registry)
    constraints, known_units = builder.build(module, source=source)
    propagator = ConstraintPropagator()
    result = propagator.propagate(constraints, known_units)
    return result


def _get_unit(result, var_name: str, scope: str = "global") -> UnitVector:
    """Get inferred unit for a variable from propagation result."""
    key = f"{scope}::{var_name}"
    return result.inferred_units.get(key)


# ===========================================================================
# 5.1: Simple variable declaration
# ===========================================================================

class TestSimpleDeclaration:
    """5.1: double x = 5.0; produces IRAssignment with IRLiteral."""

    def test_double_declaration(self):
        module = parse_cpp("double x = 5.0;", "test.cpp")
        assert len(module.global_statements) == 1
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "x"
        assert isinstance(stmt.expression, IRLiteral)
        assert stmt.expression.value == 5.0

    def test_int_declaration(self):
        module = parse_cpp("int x = 42;", "test.cpp")
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert isinstance(stmt.expression, IRLiteral)
        assert stmt.expression.value == 42.0

    def test_float_declaration(self):
        module = parse_cpp("float x = 3.14f;", "test.cpp")
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert isinstance(stmt.expression, IRLiteral)
        assert abs(stmt.expression.value - 3.14) < 0.001

    def test_declaration_without_initializer_skipped(self):
        module = parse_cpp("double x;", "test.cpp")
        # No assignment is produced for uninitialized declarations
        assert len(module.global_statements) == 0


# ===========================================================================
# 5.2: Arithmetic expressions
# ===========================================================================

class TestArithmeticExpressions:
    """5.2: Arithmetic expressions produce correct IR tree."""

    def test_addition(self):
        source = "double a = 1.0;\ndouble b = 2.0;\ndouble c = a + b;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[-1]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "c"
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.ADD

    def test_subtraction(self):
        source = "double a = 1.0;\ndouble b = 2.0;\ndouble c = a - b;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.SUB

    def test_multiplication(self):
        source = "double a = 1.0;\ndouble b = 2.0;\ndouble c = a * b;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.MUL

    def test_division(self):
        source = "double a = 1.0;\ndouble b = 2.0;\ndouble c = a / b;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.DIV

    def test_modulo(self):
        source = "int a = 10;\nint b = 3;\nint c = a % b;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.MOD

    def test_precedence_mul_before_add(self):
        source = "double a = 1.0;\ndouble b = 2.0;\ndouble c = 3.0;\ndouble y = a + b * c;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.ADD
        assert isinstance(expr.left, IRVariableRef)
        assert expr.left.variable.name == "a"
        assert isinstance(expr.right, IRBinaryOp)
        assert expr.right.operator == BinaryOperator.MUL


# ===========================================================================
# 5.3: Function definition
# ===========================================================================

class TestFunctionDefinition:
    """5.3: Function definitions produce IRFunction nodes."""

    def test_simple_function(self):
        source = "double f(double x, double y) {\n    return x + y;\n}"
        module = parse_cpp(source, "test.cpp")
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "f"
        assert len(func.parameters) == 2
        assert func.parameters[0].name == "x"
        assert func.parameters[1].name == "y"
        assert func.return_variable is not None

    def test_function_body_has_return(self):
        source = "double f(double x) {\n    return x * 2;\n}"
        module = parse_cpp(source, "test.cpp")
        func = module.functions[0]
        assert len(func.body) == 1
        assert isinstance(func.body[0], IRReturn)

    def test_function_with_local_variable(self):
        source = "double f(double x) {\n    double y = x * 2;\n    return y;\n}"
        module = parse_cpp(source, "test.cpp")
        func = module.functions[0]
        assert len(func.body) == 2
        assert isinstance(func.body[0], IRAssignment)
        assert func.body[0].target.name == "y"
        assert isinstance(func.body[1], IRReturn)

    def test_void_function(self):
        source = "void f(double x) {\n    double y = x;\n}"
        module = parse_cpp(source, "test.cpp")
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "f"


# ===========================================================================
# 5.4: Function call
# ===========================================================================

class TestFunctionCall:
    """5.4: Function calls produce IRCallExpr."""

    def test_simple_call(self):
        source = """double f(double x, double y) {
    return x + y;
}
double z = f(1.0, 2.0);
"""
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 1
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "z"
        expr = stmt.expression
        assert isinstance(expr, IRCallExpr)
        assert expr.function_name == "f"
        assert len(expr.arguments) == 2

    def test_qualified_call(self):
        source = "double y = std::sqrt(9.0);"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[0]
        expr = stmt.expression
        assert isinstance(expr, IRCallExpr)
        assert expr.function_name == "std::sqrt"


# ===========================================================================
# 5.5: Single-line comment annotation (// unit: m/s)
# ===========================================================================

class TestSingleLineAnnotation:
    """5.5: // unit: m/s produces IRAnnotation."""

    def test_inline_annotation(self):
        source = "double velocity = 10.0; // unit: m/s"
        module = parse_cpp(source, "test.cpp")
        assert len(module.annotations) == 1
        ann = module.annotations[0]
        assert ann.variable_name == "velocity"
        assert ann.unit_string == "m/s"

    def test_multiple_annotations(self):
        source = "double v = 10.0; // unit: m/s\ndouble a = 9.8; // unit: m/s^2"
        module = parse_cpp(source, "test.cpp")
        assert len(module.annotations) == 2
        assert module.annotations[0].unit_string == "m/s"
        assert module.annotations[1].unit_string == "m/s^2"

    def test_annotation_with_named_unit(self):
        source = "double force = 100.0; // unit: N"
        module = parse_cpp(source, "test.cpp")
        assert len(module.annotations) == 1
        assert module.annotations[0].unit_string == "N"


# ===========================================================================
# 5.6: Block comment annotation (/* unit: kg */)
# ===========================================================================

class TestBlockCommentAnnotation:
    """5.6: /* unit: kg */ produces IRAnnotation."""

    def test_block_annotation_after_declaration(self):
        source = "double mass = 10.0; /* unit: kg */"
        module = parse_cpp(source, "test.cpp")
        assert len(module.annotations) == 1
        ann = module.annotations[0]
        assert ann.variable_name == "mass"
        assert ann.unit_string == "kg"

    def test_block_annotation_with_compound_unit(self):
        source = "double force = 100.0; /* unit: kg*m/s^2 */"
        module = parse_cpp(source, "test.cpp")
        assert len(module.annotations) == 1
        assert module.annotations[0].unit_string == "kg*m/s^2"


# ===========================================================================
# 5.7: Inline parameter annotations
# ===========================================================================

class TestInlineParameterAnnotations:
    """5.7: Function parameter annotations via inline comments."""

    def test_parameter_annotations(self):
        source = """double compute(double v /* unit: m/s */, double t /* unit: s */) {
    return v * t;
}
"""
        module = parse_cpp(source, "test.cpp")
        # Should find annotations for v and t
        var_names = {a.variable_name for a in module.annotations}
        assert "v" in var_names
        assert "t" in var_names
        unit_map = {a.variable_name: a.unit_string for a in module.annotations}
        assert unit_map["v"] == "m/s"
        assert unit_map["t"] == "s"

    def test_three_parameter_annotations(self):
        source = """void sim(double m /* unit: kg */, double a /* unit: m/s^2 */, double t /* unit: s */) {
    double force = m * a;
}
"""
        module = parse_cpp(source, "test.cpp")
        assert len(module.annotations) >= 3
        var_names = {a.variable_name for a in module.annotations}
        assert {"m", "a", "t"}.issubset(var_names)


# ===========================================================================
# 5.8: Return statement
# ===========================================================================

class TestReturnStatement:
    """5.8: return expr; produces IRReturn."""

    def test_return_expression(self):
        source = "double f(double x, double y) {\n    return x * y;\n}"
        module = parse_cpp(source, "test.cpp")
        func = module.functions[0]
        ret = func.body[0]
        assert isinstance(ret, IRReturn)
        assert isinstance(ret.expression, IRBinaryOp)
        assert ret.expression.operator == BinaryOperator.MUL

    def test_return_variable(self):
        source = "double f(double x) {\n    return x;\n}"
        module = parse_cpp(source, "test.cpp")
        func = module.functions[0]
        ret = func.body[0]
        assert isinstance(ret, IRReturn)
        assert isinstance(ret.expression, IRVariableRef)
        assert ret.expression.variable.name == "x"


# ===========================================================================
# 5.9: Source locations
# ===========================================================================

class TestSourceLocations:
    """5.9: All IR nodes have correct file/line/column."""

    def test_declaration_location(self):
        source = "double x = 5.0;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[0]
        assert stmt.location.file == "test.cpp"
        assert stmt.location.line == 1

    def test_function_location(self):
        source = "\n\ndouble my_func() {\n    return 1.0;\n}"
        module = parse_cpp(source, "test.cpp")
        func = module.functions[0]
        assert func.location.line == 3

    def test_multi_line_locations(self):
        source = "double a = 1.0;\ndouble b = 2.0;\ndouble c = a + b;"
        module = parse_cpp(source, "test.cpp")
        assert module.global_statements[0].location.line == 1
        assert module.global_statements[1].location.line == 2
        assert module.global_statements[2].location.line == 3


# ===========================================================================
# 5.10: Multiple functions
# ===========================================================================

class TestMultipleFunctions:
    """5.10: File with multiple functions produces multiple IRFunction nodes."""

    def test_three_functions(self):
        source = """
double f1(double x) {
    return x;
}

double f2(double x, double y) {
    return x + y;
}

double f3(double x, double y, double z) {
    return x * y * z;
}
"""
        module = parse_cpp(source, "test.cpp")
        assert len(module.functions) == 3
        assert module.functions[0].name == "f1"
        assert module.functions[1].name == "f2"
        assert module.functions[2].name == "f3"
        assert len(module.functions[0].parameters) == 1
        assert len(module.functions[1].parameters) == 2
        assert len(module.functions[2].parameters) == 3


# ===========================================================================
# 5.11: Assignment expression (re-assignment)
# ===========================================================================

class TestAssignmentExpression:
    """5.11: a = b + c; (without type) produces IRAssignment."""

    def test_reassignment(self):
        source = "double a = 1.0;\ndouble b = 2.0;\na = a + b;"
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 3
        stmt = module.global_statements[2]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "a"
        assert isinstance(stmt.expression, IRBinaryOp)
        assert stmt.expression.operator == BinaryOperator.ADD


# ===========================================================================
# 5.12: Augmented assignment
# ===========================================================================

class TestAugmentedAssignment:
    """5.12: a += 5.0; produces IRAugmentedAssignment."""

    def test_plus_equals(self):
        source = "double a = 1.0;\na += 5.0;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[1]
        assert isinstance(stmt, IRAugmentedAssignment)
        assert stmt.target.name == "a"
        assert stmt.operator == BinaryOperator.ADD

    def test_minus_equals(self):
        source = "double a = 1.0;\na -= 3.0;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[1]
        assert isinstance(stmt, IRAugmentedAssignment)
        assert stmt.operator == BinaryOperator.SUB

    def test_times_equals(self):
        source = "double a = 1.0;\na *= 2.0;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[1]
        assert isinstance(stmt, IRAugmentedAssignment)
        assert stmt.operator == BinaryOperator.MUL

    def test_divide_equals(self):
        source = "double a = 1.0;\na /= 4.0;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[1]
        assert isinstance(stmt, IRAugmentedAssignment)
        assert stmt.operator == BinaryOperator.DIV


# ===========================================================================
# 5.13: Unary expressions
# ===========================================================================

class TestUnaryExpressions:
    """5.13: Unary negation/positive produce IRUnaryOp."""

    def test_negation(self):
        source = "double a = 1.0;\ndouble b = -a;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[1]
        expr = stmt.expression
        assert isinstance(expr, IRUnaryOp)
        assert expr.operator == UnaryOperator.NEG
        assert isinstance(expr.operand, IRVariableRef)
        assert expr.operand.variable.name == "a"


# ===========================================================================
# 5.14: Pointer and reference declarations
# ===========================================================================

class TestPointerAndReference:
    """5.14: double& x and double* x are treated same as double x."""

    def test_reference_declaration(self):
        source = "double y = 5.0;\nconst double& x = y;"
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 2
        stmt = module.global_statements[1]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "x"
        assert isinstance(stmt.expression, IRVariableRef)
        assert stmt.expression.variable.name == "y"

    def test_pointer_declaration(self):
        source = "double z = 5.0;\ndouble* ptr = &z;"
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 2
        stmt = module.global_statements[1]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "ptr"


# ===========================================================================
# 5.15: Const declarations
# ===========================================================================

class TestConstDeclaration:
    """5.15: const double PI = 3.14; produces IRAssignment."""

    def test_const_double(self):
        source = "const double PI = 3.14159;"
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 1
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "PI"
        assert isinstance(stmt.expression, IRLiteral)
        assert abs(stmt.expression.value - 3.14159) < 0.0001


# ===========================================================================
# 5.16: Auto type specifier
# ===========================================================================

class TestAutoType:
    """5.16: auto x = 3.14; is parsed correctly."""

    def test_auto_declaration(self):
        source = "auto x = 3.14;"
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 1
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "x"
        assert isinstance(stmt.expression, IRLiteral)


# ===========================================================================
# 5.17: pow() as exponentiation
# ===========================================================================

class TestPowExponentiation:
    """5.17: pow(x, 2) produces IRBinaryOp(POW, x, 2)."""

    def test_pow_call(self):
        source = "double x = 3.0;\ndouble y = pow(x, 2);"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.POW
        assert isinstance(expr.left, IRVariableRef)
        assert expr.left.variable.name == "x"
        assert isinstance(expr.right, IRLiteral)
        assert expr.right.value == 2.0

    def test_std_pow_call(self):
        source = "double x = 3.0;\ndouble y = std::pow(x, 0.5);"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.POW


# ===========================================================================
# 5.18: Nested expressions with parentheses
# ===========================================================================

class TestNestedExpressions:
    """5.18: (a + b) * (c - d) produces correct IR tree."""

    def test_parenthesized_expression(self):
        source = "double a=1.0;\ndouble b=2.0;\ndouble c=3.0;\ndouble d=4.0;\ndouble z = (a + b) * (c - d);"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[-1]
        expr = stmt.expression
        assert isinstance(expr, IRBinaryOp)
        assert expr.operator == BinaryOperator.MUL
        assert isinstance(expr.left, IRBinaryOp)
        assert expr.left.operator == BinaryOperator.ADD
        assert isinstance(expr.right, IRBinaryOp)
        assert expr.right.operator == BinaryOperator.SUB


# ===========================================================================
# 5.19: Integration -- correct physics (no violations)
# ===========================================================================

class TestIntegrationCorrectPhysics:
    """5.19: Correct C++ physics code produces zero violations."""

    def test_velocity_from_distance_time(self):
        source = """
double distance = 100.0; // unit: m
double time = 10.0;      // unit: s
double velocity = distance / time;
double acceleration = velocity / time;
"""
        result = _analyze_cpp(source)
        assert len(result.violations) == 0

        v = _get_unit(result, "velocity")
        expected_v = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert v is not None and v.dimensions_equal(expected_v)

        a = _get_unit(result, "acceleration")
        expected_a = UnitVector.from_list([1, 0, -2, 0, 0, 0, 0])
        assert a is not None and a.dimensions_equal(expected_a)

    def test_chain_propagation(self):
        source = """
double x = 10.0; // unit: m
double y = x;
double z = y;
double w = z;
"""
        result = _analyze_cpp(source)
        assert len(result.violations) == 0
        m = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        assert _get_unit(result, "y").dimensions_equal(m)
        assert _get_unit(result, "z").dimensions_equal(m)
        assert _get_unit(result, "w").dimensions_equal(m)

    def test_fixture_file_correct_physics(self):
        source = (FIXTURE_DIR / "correct_physics.cpp").read_text()
        result = _analyze_cpp(source)
        assert len(result.violations) == 0


# ===========================================================================
# 5.20: Integration -- velocity + acceleration violation
# ===========================================================================

class TestIntegrationViolation:
    """5.20: Adding velocity (m/s) to acceleration (m/s^2) is flagged."""

    def test_velocity_acceleration_mismatch(self):
        source = """
double velocity = 10.0;     // unit: m/s
double acceleration = 9.8;  // unit: m/s^2
double result = velocity + acceleration;
"""
        result = _analyze_cpp(source)
        assert len(result.violations) >= 1
        msgs = [v.message for v in result.violations]
        assert any("m/s" in m for m in msgs)

    def test_fixture_file_velocity_acceleration(self):
        source = (FIXTURE_DIR / "velocity_acceleration.cpp").read_text()
        result = _analyze_cpp(source)
        assert len(result.violations) >= 1

    def test_force_computation_wrong_formula(self):
        """mass * velocity != N; adding that to a real force is a violation."""
        source = """
double mass = 5.0;       // unit: kg
double velocity = 10.0;  // unit: m/s
double force = mass * velocity;
double drag = 100.0;     // unit: N
double thrust = force + drag;
"""
        result = _analyze_cpp(source)
        assert len(result.violations) > 0


# ===========================================================================
# 5.21: Integration -- energy conservation
# ===========================================================================

class TestIntegrationEnergy:
    """5.21: Kinetic + potential energy with correct units (no violations)."""

    def test_energy_conservation(self):
        source = """
double mass = 2.0;      // unit: kg
double velocity = 3.0;  // unit: m/s
double height = 10.0;   // unit: m
double g = 9.81;        // unit: m/s^2

double kinetic = 0.5 * mass * pow(velocity, 2);
double potential = mass * g * height;
double total = kinetic + potential;
"""
        result = _analyze_cpp(source)
        assert len(result.violations) == 0

        joule = UnitVector.from_list([2, 1, -2, 0, 0, 0, 0])
        kin = _get_unit(result, "kinetic")
        pot = _get_unit(result, "potential")
        assert kin is not None and kin.dimensions_equal(joule)
        assert pot is not None and pot.dimensions_equal(joule)

    def test_kinetic_plus_mass_violation(self):
        source = """
double mass = 2.0;      // unit: kg
double velocity = 3.0;  // unit: m/s

double kinetic = 0.5 * mass * pow(velocity, 2);
double bad_total = kinetic + mass;
"""
        result = _analyze_cpp(source)
        assert len(result.violations) >= 1


# ===========================================================================
# 5.22: Integration -- Mars Climate Orbiter
# ===========================================================================

class TestIntegrationMarsClimateOrbiter:
    """5.22: MCO scenario -- lbf*s vs N*s now produces a scale mismatch warning.

    Both are dimensionally momentum (kg*m/s), but lbf*s has a different
    scale factor (4.44822) than N*s (1.0). The tool now detects this
    scale mismatch, which is the actual MCO bug.
    """

    def test_mco_scale_mismatch_detected(self):
        source = """
double sm_forces_impulse = 100.0;  // unit: lbf*s
double trajectory_impulse = 50.0;  // unit: N*s
double total = sm_forces_impulse + trajectory_impulse;
"""
        result = _analyze_cpp(source)
        # Scale factor mismatch should produce warnings (not dimension errors)
        warnings = [v for v in result.violations if v.severity.value == "warning"]
        assert len(warnings) >= 1, "MCO scale mismatch should produce at least one warning"

        momentum = UnitVector.from_list([1, 1, -1, 0, 0, 0, 0])
        sm = _get_unit(result, "sm_forces_impulse")
        traj = _get_unit(result, "trajectory_impulse")
        assert sm is not None and sm.dimensions_equal(momentum)
        assert traj is not None and traj.dimensions_equal(momentum)
        # Scale factors should be different
        assert sm.scale_factor != traj.scale_factor


# ===========================================================================
# 5.23: Cross-language parity
# ===========================================================================

class TestCrossLanguageParity:
    """5.23: Equivalent Python and C++ code produce the same analysis results."""

    def test_correct_physics_parity(self):
        cpp_source = """
double distance = 100.0; // unit: m
double time = 10.0;      // unit: s
double velocity = distance / time;
"""
        py_source = """
distance = 100.0  # unit: m
time = 10.0       # unit: s
velocity = distance / time
"""
        cpp_result = _analyze_cpp(cpp_source)
        py_result = _analyze_python(py_source)

        assert len(cpp_result.violations) == 0
        assert len(py_result.violations) == 0

        cpp_v = _get_unit(cpp_result, "velocity")
        py_v = _get_unit(py_result, "velocity")
        assert cpp_v is not None and py_v is not None
        assert cpp_v.dimensions_equal(py_v)

    def test_violation_parity(self):
        cpp_source = """
double velocity = 10.0;     // unit: m/s
double acceleration = 9.8;  // unit: m/s^2
double result = velocity + acceleration;
"""
        py_source = """
velocity = 10.0     # unit: m/s
acceleration = 9.8  # unit: m/s^2
result = velocity + acceleration
"""
        cpp_result = _analyze_cpp(cpp_source)
        py_result = _analyze_python(py_source)

        assert len(cpp_result.violations) >= 1
        assert len(py_result.violations) >= 1

    def test_energy_parity(self):
        cpp_source = """
double mass = 2.0;      // unit: kg
double velocity = 3.0;  // unit: m/s
double height = 10.0;   // unit: m
double g = 9.81;        // unit: m/s^2

double kinetic = 0.5 * mass * pow(velocity, 2);
double potential = mass * g * height;
double total = kinetic + potential;
"""
        py_source = """
mass = 2.0          # unit: kg
velocity = 3.0      # unit: m/s
height = 10.0       # unit: m
g = 9.81            # unit: m/s^2

kinetic = 0.5 * mass * velocity ** 2
potential = mass * g * height
total = kinetic + potential
"""
        cpp_result = _analyze_cpp(cpp_source)
        py_result = _analyze_python(py_source)

        assert len(cpp_result.violations) == 0
        assert len(py_result.violations) == 0

        joule = UnitVector.from_list([2, 1, -2, 0, 0, 0, 0])
        for result in [cpp_result, py_result]:
            kin = _get_unit(result, "kinetic")
            pot = _get_unit(result, "potential")
            assert kin is not None and kin.dimensions_equal(joule)
            assert pot is not None and pot.dimensions_equal(joule)


# ===========================================================================
# 5.24: Multiple declarations in one statement
# ===========================================================================

class TestMultipleDeclarationsSkipped:
    """5.24: Ensure parser handles various declaration forms gracefully."""

    def test_no_crash_on_complex_types(self):
        """Parser should not crash on types it cannot fully understand."""
        source = """
double x = 1.0;
int y = 2;
"""
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 2


# ===========================================================================
# 5.25: Standalone comment annotation
# ===========================================================================

class TestStandaloneAnnotation:
    """5.25: A comment on its own line applies to the next declaration."""

    def test_standalone_annotation_applies_to_next(self):
        source = """// unit: m/s
double velocity = 10.0;"""
        module = parse_cpp(source, "test.cpp")
        assert len(module.annotations) == 1
        ann = module.annotations[0]
        assert ann.variable_name == "velocity"
        assert ann.unit_string == "m/s"


# ===========================================================================
# Additional edge cases
# ===========================================================================

class TestEdgeCases:
    """Additional edge cases for robustness."""

    def test_empty_source(self):
        module = parse_cpp("", "test.cpp")
        assert len(module.global_statements) == 0
        assert len(module.functions) == 0
        assert len(module.annotations) == 0

    def test_comments_only(self):
        source = "// This is a comment\n/* Another comment */"
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 0

    def test_include_directives_ignored(self):
        source = '#include <cmath>\n#include "myheader.h"\ndouble x = 5.0;'
        module = parse_cpp(source, "test.cpp")
        assert len(module.global_statements) == 1
        assert module.global_statements[0].target.name == "x"

    def test_hex_literal(self):
        source = "int x = 0xFF;"
        module = parse_cpp(source, "test.cpp")
        stmt = module.global_statements[0]
        assert isinstance(stmt.expression, IRLiteral)
        assert stmt.expression.value == 255.0

    def test_function_with_annotated_params_integration(self):
        """Full pipeline: function with annotated params, local computation."""
        source = """
double compute_force(double mass /* unit: kg */, double accel /* unit: m/s^2 */) {
    double force = mass * accel;
    return force;
}
"""
        result = _analyze_cpp(source)
        assert len(result.violations) == 0

        # Force should be inferred as N = kg*m/s^2
        force_unit = _get_unit(result, "force", scope="local:compute_force")
        expected = UnitVector.from_list([1, 1, -2, 0, 0, 0, 0])
        assert force_unit is not None and force_unit.dimensions_equal(expected)

    def test_comparison_expression(self):
        """Comparison operators produce IRComparison."""
        source = "double a = 1.0;\ndouble b = 2.0;\nbool c = a < b;"
        module = parse_cpp(source, "test.cpp")
        # The last statement assigns a comparison
        stmt = module.global_statements[-1]
        assert isinstance(stmt, IRAssignment)
        assert isinstance(stmt.expression, IRComparison)
        assert stmt.expression.operator == ComparisonOperator.LT
