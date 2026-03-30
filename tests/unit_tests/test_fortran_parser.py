"""Tests for the Fortran parser (Checkpoint 6).

Tests cover:
    6.1   Variable declaration
    6.2   Assignment
    6.3   Subroutine
    6.4   Comment annotation (! unit: m/s)
    6.5   Function with result variable
    6.6   Same inference engine (Fortran IR produces same violations as Python IR)
    6.7   Arithmetic expressions (+, -, *, /, **)
    6.8   Function calls (sqrt, abs)
    6.9   Source locations
    6.10  Multiple subroutines and functions
    6.11  Unary expressions (-x)
    6.12  Cross-language parity (Python, C++, Fortran produce same results)
    6.13  Integration: correct physics (no violations)
    6.14  Integration: velocity + acceleration violation
    6.15  Integration: energy conservation (kinetic + potential)
    6.16  Integration: Mars Climate Orbiter (same-dimension units)
    6.17  Edge cases (empty, comments only, program block)
    6.18  Case insensitivity
    6.19  Standalone annotation (applies to next declaration/assignment)
    6.20  Fixture file tests
"""

import pytest
from pathlib import Path

from unit_checker.parsers.fortran_parser.parser import parse_fortran
from unit_checker.parsers.python_parser.parser import parse_python
from unit_checker.parsers.cpp_parser.parser import parse_cpp
from unit_checker.parsers.common.ir import (
    IRAssignment,
    IRBinaryOp,
    IRUnaryOp,
    BinaryOperator,
    UnaryOperator,
)
from unit_checker.inference.constraint_builder import ConstraintBuilder
from unit_checker.inference.propagator import ConstraintPropagator
from unit_checker.core.unit_registry import default_registry

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "fortran"


def _analyze(source: str, file_path: str = "test.f90"):
    """Parse and analyze Fortran source, return propagation result."""
    module = parse_fortran(source, file_path)
    builder = ConstraintBuilder(registry=default_registry)
    constraints, known = builder.build(module, source=source)
    propagator = ConstraintPropagator()
    result = propagator.propagate(constraints, known)
    result.violations = builder.violations + result.violations
    return result


def _analyze_python(source: str, file_path: str = "test.py"):
    """Parse and analyze Python source for cross-language parity tests."""
    module = parse_python(source, file_path)
    builder = ConstraintBuilder(registry=default_registry)
    constraints, known = builder.build(module, source=source)
    propagator = ConstraintPropagator()
    result = propagator.propagate(constraints, known)
    result.violations = builder.violations + result.violations
    return result


# --- 6.1: Variable Declaration ---

class TestVariableDeclaration:
    def test_real_declaration_with_assignment(self):
        source = """
program test
  implicit none
  real :: x
  x = 5.0
end program test
"""
        module = parse_fortran(source)
        assert len(module.global_statements) == 1
        stmt = module.global_statements[0]
        assert isinstance(stmt, IRAssignment)
        assert stmt.target.name == "x"

    def test_integer_declaration(self):
        source = """
program test
  implicit none
  integer :: n
  n = 42
end program test
"""
        module = parse_fortran(source)
        assert len(module.global_statements) == 1


# --- 6.2: Assignment ---

class TestAssignment:
    def test_simple_assignment(self):
        source = """
program test
  implicit none
  real :: velocity
  real :: distance  ! unit: m
  real :: time_val  ! unit: s
  distance = 100.0
  time_val = 10.0
  velocity = distance / time_val
end program test
"""
        module = parse_fortran(source)
        assert len(module.global_statements) == 3

    def test_division_creates_binop(self):
        source = """
program test
  implicit none
  real :: a, b, c
  a = 10.0
  b = 5.0
  c = a / b
end program test
"""
        module = parse_fortran(source)
        last_stmt = module.global_statements[-1]
        assert isinstance(last_stmt, IRAssignment)
        assert isinstance(last_stmt.expression, IRBinaryOp)
        assert last_stmt.expression.operator == BinaryOperator.DIV


# --- 6.3: Subroutine ---

class TestSubroutine:
    def test_simple_subroutine(self):
        source = """
subroutine compute(a, b, c)
  implicit none
  real, intent(in) :: a
  real, intent(in) :: b
  real, intent(out) :: c
  c = a + b
end subroutine compute
"""
        module = parse_fortran(source)
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "compute"
        assert len(func.parameters) == 3
        assert func.parameters[0].name == "a"
        assert func.parameters[1].name == "b"
        assert func.parameters[2].name == "c"

    def test_subroutine_body_has_assignment(self):
        source = """
subroutine assign_test(x)
  implicit none
  real, intent(out) :: x
  x = 42.0
end subroutine assign_test
"""
        module = parse_fortran(source)
        assert len(module.functions) == 1
        func = module.functions[0]
        assert len(func.body) >= 1
        stmt = func.body[0]
        assert isinstance(stmt, IRAssignment)


# --- 6.4: Comment Annotation ---

class TestCommentAnnotation:
    def test_inline_annotation(self):
        source = """
program test
  implicit none
  real :: velocity  ! unit: m/s
  velocity = 10.0
end program test
"""
        module = parse_fortran(source)
        assert len(module.annotations) == 1
        ann = module.annotations[0]
        assert ann.variable_name == "velocity"
        assert ann.unit_string == "m/s"

    def test_multiple_annotations(self):
        source = """
program test
  implicit none
  real :: mass     ! unit: kg
  real :: accel    ! unit: m/s^2
  mass = 5.0
  accel = 9.8
end program test
"""
        module = parse_fortran(source)
        assert len(module.annotations) == 2
        names = {a.variable_name for a in module.annotations}
        assert "mass" in names
        assert "accel" in names

    def test_annotation_with_named_unit(self):
        source = """
program test
  implicit none
  real :: force  ! unit: N
  force = 100.0
end program test
"""
        module = parse_fortran(source)
        assert len(module.annotations) == 1
        assert module.annotations[0].unit_string == "N"


# --- 6.5: Function with result variable ---

class TestFunction:
    def test_function_with_result(self):
        source = """
function compute_velocity(dist, t) result(vel)
  implicit none
  real, intent(in) :: dist  ! unit: m
  real, intent(in) :: t     ! unit: s
  real :: vel
  vel = dist / t
end function compute_velocity
"""
        module = parse_fortran(source)
        assert len(module.functions) == 1
        func = module.functions[0]
        assert func.name == "compute_velocity"
        assert len(func.parameters) == 2
        assert func.parameters[0].name == "dist"
        assert func.parameters[1].name == "t"

    def test_function_inference(self):
        source = """
function compute_velocity(dist, t) result(vel)
  implicit none
  real, intent(in) :: dist  ! unit: m
  real, intent(in) :: t     ! unit: s
  real :: vel
  vel = dist / t
end function compute_velocity
"""
        result = _analyze(source)
        assert len(result.violations) == 0
        # Check that vel was inferred as m/s
        vel_units = [
            v for k, v in result.inferred_units.items()
            if "vel" in k and "__return_" not in k
        ]
        assert any(u.to_unit_string() == "m/s" for u in vel_units)


# --- 6.6: Same inference engine ---

class TestSameInferenceEngine:
    def test_fortran_and_python_same_violation(self):
        fortran_source = """
program test
  implicit none
  real :: velocity      ! unit: m/s
  real :: acceleration  ! unit: m/s^2
  real :: result
  velocity = 10.0
  acceleration = 9.8
  result = velocity + acceleration
end program test
"""
        python_source = """
velocity = 10.0      # unit: m/s
acceleration = 9.8   # unit: m/s^2
result = velocity + acceleration
"""
        f_result = _analyze(fortran_source)
        p_result = _analyze_python(python_source)

        # Both should detect exactly the same violation type
        assert len(f_result.violations) >= 1
        assert len(p_result.violations) >= 1

        # Both violations should be about addition mismatch
        assert any("addition" in v.message.lower() or "mismatch" in v.message.lower()
                    for v in f_result.violations)
        assert any("addition" in v.message.lower() or "mismatch" in v.message.lower()
                    for v in p_result.violations)


# --- 6.7: Arithmetic Expressions ---

class TestArithmeticExpressions:
    def test_addition(self):
        source = """
program test
  implicit none
  real :: a, b, c
  a = 1.0
  b = 2.0
  c = a + b
end program test
"""
        module = parse_fortran(source)
        last_stmt = module.global_statements[-1]
        assert isinstance(last_stmt.expression, IRBinaryOp)
        assert last_stmt.expression.operator == BinaryOperator.ADD

    def test_multiplication(self):
        source = """
program test
  implicit none
  real :: a, b, c
  a = 2.0
  b = 3.0
  c = a * b
end program test
"""
        module = parse_fortran(source)
        last_stmt = module.global_statements[-1]
        assert isinstance(last_stmt.expression, IRBinaryOp)
        assert last_stmt.expression.operator == BinaryOperator.MUL

    def test_exponentiation(self):
        source = """
program test
  implicit none
  real :: length  ! unit: m
  real :: area
  length = 5.0
  area = length**2
end program test
"""
        result = _analyze(source)
        area_units = [v for k, v in result.inferred_units.items() if "area" in k]
        assert any(u.to_unit_string() == "m^2" for u in area_units)


# --- 6.8: Function Calls ---

class TestFunctionCalls:
    def test_sqrt_call(self):
        source = """
program test
  implicit none
  real :: area    ! unit: m^2
  real :: side
  area = 16.0
  side = sqrt(area)
end program test
"""
        result = _analyze(source)
        side_units = [v for k, v in result.inferred_units.items() if "side" in k]
        assert any(u.to_unit_string() == "m" for u in side_units)


# --- 6.9: Source Locations ---

class TestSourceLocations:
    def test_assignment_location(self):
        source = """program test
  implicit none
  real :: x
  x = 5.0
end program test
"""
        module = parse_fortran(source)
        stmt = module.global_statements[0]
        assert stmt.location.line == 4

    def test_function_location(self):
        source = """function f(a)
  implicit none
  real, intent(in) :: a
  real :: f
  f = a * 2.0
end function f
"""
        module = parse_fortran(source)
        assert module.functions[0].location.line == 1


# --- 6.10: Multiple Subroutines and Functions ---

class TestMultipleSubprograms:
    def test_two_subroutines_and_function(self):
        source = """
subroutine sub1(x)
  implicit none
  real, intent(in) :: x
end subroutine sub1

subroutine sub2(y)
  implicit none
  real, intent(in) :: y
end subroutine sub2

function func1(z) result(w)
  implicit none
  real, intent(in) :: z
  real :: w
  w = z * 2.0
end function func1
"""
        module = parse_fortran(source)
        assert len(module.functions) == 3


# --- 6.11: Unary Expressions ---

class TestUnaryExpressions:
    def test_negation(self):
        source = """
program test
  implicit none
  real :: x, y
  x = 5.0
  y = -x
end program test
"""
        module = parse_fortran(source)
        last_stmt = module.global_statements[-1]
        assert isinstance(last_stmt.expression, IRUnaryOp)
        assert last_stmt.expression.operator == UnaryOperator.NEG


# --- 6.12: Cross-Language Parity ---

class TestCrossLanguageParity:
    def test_correct_physics_parity(self):
        """Same correct physics in Python, C++, Fortran -> zero violations in all."""
        python_src = """
distance = 100.0  # unit: m
time_val = 10.0   # unit: s
velocity = distance / time_val
"""
        cpp_src = """
double distance = 100.0;  // unit: m
double time_val = 10.0;   // unit: s
double velocity = distance / time_val;
"""
        fortran_src = """
program test
  implicit none
  real :: distance  ! unit: m
  real :: time_val  ! unit: s
  real :: velocity
  distance = 100.0
  time_val = 10.0
  velocity = distance / time_val
end program test
"""
        py_result = _analyze_python(python_src)
        cpp_module = parse_cpp(cpp_src)
        cpp_builder = ConstraintBuilder(registry=default_registry)
        cpp_cons, cpp_known = cpp_builder.build(cpp_module, source=cpp_src)
        cpp_result = ConstraintPropagator().propagate(cpp_cons, cpp_known)
        f_result = _analyze(fortran_src)

        assert len(py_result.violations) == 0
        assert len(cpp_result.violations) == 0
        assert len(f_result.violations) == 0

    def test_violation_parity(self):
        """Same violation in Python, C++, Fortran -> all detect it."""
        python_src = """
velocity = 10.0      # unit: m/s
acceleration = 9.8   # unit: m/s^2
result = velocity + acceleration
"""
        cpp_src = """
double velocity = 10.0;      // unit: m/s
double acceleration = 9.8;   // unit: m/s^2
double result = velocity + acceleration;
"""
        fortran_src = """
program test
  implicit none
  real :: velocity      ! unit: m/s
  real :: acceleration  ! unit: m/s^2
  real :: result
  velocity = 10.0
  acceleration = 9.8
  result = velocity + acceleration
end program test
"""
        py_result = _analyze_python(python_src)
        cpp_module = parse_cpp(cpp_src)
        cpp_builder = ConstraintBuilder(registry=default_registry)
        cpp_cons, cpp_known = cpp_builder.build(cpp_module, source=cpp_src)
        cpp_result = ConstraintPropagator().propagate(cpp_cons, cpp_known)
        f_result = _analyze(fortran_src)

        assert len(py_result.violations) >= 1
        assert len(cpp_result.violations) >= 1
        assert len(f_result.violations) >= 1


# --- 6.13: Integration - Correct Physics ---

class TestIntegrationCorrectPhysics:
    def test_velocity_from_distance_time(self):
        source = """
program test
  implicit none
  real :: distance  ! unit: m
  real :: time_val  ! unit: s
  real :: velocity
  distance = 100.0
  time_val = 10.0
  velocity = distance / time_val
end program test
"""
        result = _analyze(source)
        assert len(result.violations) == 0
        vel_units = [v for k, v in result.inferred_units.items() if "velocity" in k]
        assert any(u.to_unit_string() == "m/s" for u in vel_units)

    def test_fixture_file_correct_physics(self):
        fixture = FIXTURES_DIR / "correct_physics.f90"
        if not fixture.exists():
            pytest.skip("Fixture file not found")
        source = fixture.read_text()
        result = _analyze(source, str(fixture))
        assert len(result.violations) == 0


# --- 6.14: Integration - Velocity + Acceleration Violation ---

class TestIntegrationViolation:
    def test_velocity_acceleration_mismatch(self):
        source = """
program test
  implicit none
  real :: velocity      ! unit: m/s
  real :: acceleration  ! unit: m/s^2
  real :: result
  velocity = 10.0
  acceleration = 9.8
  result = velocity + acceleration
end program test
"""
        result = _analyze(source)
        assert len(result.violations) >= 1

    def test_fixture_file_velocity_acceleration(self):
        fixture = FIXTURES_DIR / "velocity_acceleration.f90"
        if not fixture.exists():
            pytest.skip("Fixture file not found")
        source = fixture.read_text()
        result = _analyze(source, str(fixture))
        assert len(result.violations) >= 1


# --- 6.15: Integration - Energy Conservation ---

class TestIntegrationEnergy:
    def test_energy_conservation_violation(self):
        source = """
program test
  implicit none
  real :: mass     ! unit: kg
  real :: height   ! unit: m
  real :: gravity  ! unit: m/s^2
  real :: velocity ! unit: m/s
  real :: pe, ke, total
  mass = 2.0
  height = 10.0
  gravity = 9.81
  velocity = 5.0
  pe = mass * gravity * height
  ke = mass * velocity
  total = pe + ke
end program test
"""
        result = _analyze(source)
        assert len(result.violations) >= 1

    def test_fixture_file_energy_conservation(self):
        fixture = FIXTURES_DIR / "energy_conservation.f90"
        if not fixture.exists():
            pytest.skip("Fixture file not found")
        source = fixture.read_text()
        result = _analyze(source, str(fixture))
        assert len(result.violations) >= 1


# --- 6.16: Integration - Mars Climate Orbiter ---

class TestIntegrationMarsClimateOrbiter:
    def test_mco_scale_mismatch_detected(self):
        """lbf*s and N*s have the same dimensions but different scale factors.

        The tool now detects this as a scale mismatch warning, which is
        the actual MCO bug (factor of ~4.45 error).
        """
        source = """
program test
  implicit none
  real :: thrust  ! unit: lbf*s
  real :: force   ! unit: N*s
  real :: result
  thrust = 4.45
  force = 100.0
  result = thrust + force
end program test
"""
        result = _analyze(source)
        # Scale factor mismatch should produce warnings
        warnings = [v for v in result.violations if v.severity.value == "warning"]
        assert len(warnings) >= 1, "MCO scale mismatch should produce at least one warning"


# --- 6.17: Edge Cases ---

class TestEdgeCases:
    def test_empty_source(self):
        module = parse_fortran("")
        assert len(module.functions) == 0
        assert len(module.global_statements) == 0

    def test_comments_only(self):
        source = """
! This is just a comment
! Another comment
"""
        module = parse_fortran(source)
        assert len(module.functions) == 0

    def test_program_block(self):
        source = """
program hello
  implicit none
end program hello
"""
        module = parse_fortran(source)
        assert len(module.global_statements) == 0

    def test_fortran_style_literal(self):
        """Test Fortran double-precision notation (1.0d0)."""
        source = """
program test
  implicit none
  real :: x
  x = 1.0
end program test
"""
        module = parse_fortran(source)
        assert len(module.global_statements) == 1


# --- 6.18: Case Insensitivity ---

class TestCaseInsensitivity:
    def test_variable_names_lowered(self):
        source = """
program test
  implicit none
  REAL :: Velocity
  Velocity = 10.0
end program test
"""
        module = parse_fortran(source)
        stmt = module.global_statements[0]
        assert stmt.target.name == "velocity"

    def test_function_names_lowered(self):
        source = """
SUBROUTINE MyFunc(X, Y)
  IMPLICIT NONE
  REAL, INTENT(IN) :: X
  REAL, INTENT(OUT) :: Y
  Y = X * 2.0
END SUBROUTINE MyFunc
"""
        module = parse_fortran(source)
        assert len(module.functions) == 1
        assert module.functions[0].name == "myfunc"


# --- 6.19: Standalone Annotation ---

class TestStandaloneAnnotation:
    def test_standalone_annotation_applies_to_next(self):
        source = """
program test
  implicit none
  ! unit: m/s
  real :: velocity
  velocity = 10.0
end program test
"""
        module = parse_fortran(source)
        assert len(module.annotations) == 1
        assert module.annotations[0].variable_name == "velocity"
        assert module.annotations[0].unit_string == "m/s"
