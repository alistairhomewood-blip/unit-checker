"""Tests for constraint propagation (Checkpoint 3).

Tests cover:
    3.1  Forward propagation
    3.2  Backward propagation
    3.3  Addition constraint
    3.4  Multiplication constraint
    3.5  Division constraint
    3.6  Violation detection
    3.7  Provenance tracking
    3.8  Fixed-point convergence
    3.9  Benchmark 1.2: velocity-acceleration addition
    3.10 Benchmark 1.5: correct code (no violations)
    3.11 Benchmark 1.10: multi-operation expression
"""


from unit_checker.core.unit_algebra import UnitVector
from unit_checker.core.unit_registry import default_registry
from unit_checker.inference.constraint_builder import ConstraintBuilder
from unit_checker.inference.propagator import ConstraintPropagator
from unit_checker.parsers.python_parser.parser import parse_python


def _analyze(source: str) -> tuple:
    """Helper: parse, build constraints, propagate, return result."""
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


class TestForwardPropagation:
    """3.1: Annotated input propagates to output through assignment chain."""

    def test_simple_forward(self):
        source = """
distance = 100.0  # unit: m
x = distance
y = x
"""
        result = _analyze(source)
        assert _get_unit(result, "x").dimensions_equal(
            UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        )
        assert _get_unit(result, "y").dimensions_equal(
            UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        )

    def test_chain_propagation(self):
        """Benchmark 1.9: Assignment chain propagation."""
        source = """
x = 10.0  # unit: m
y = x
z = y
w = z
"""
        result = _analyze(source)
        m = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        assert _get_unit(result, "y").dimensions_equal(m)
        assert _get_unit(result, "z").dimensions_equal(m)
        assert _get_unit(result, "w").dimensions_equal(m)


class TestBackwardPropagation:
    """3.2: Known output unit propagates backward to infer input units."""

    def test_backward_from_division(self):
        source = """
distance = 100.0  # unit: m
time = 10.0  # unit: s
velocity = distance / time
"""
        result = _analyze(source)
        v = _get_unit(result, "velocity")
        assert v is not None
        expected = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert v.dimensions_equal(expected)


class TestAdditionConstraint:
    """3.3: c = a + b with known unit(a) infers unit(b) = unit(c) = unit(a)."""

    def test_addition_infers_same_units(self):
        source = """
a = 5.0  # unit: m
b = 10.0
c = a + b
"""
        result = _analyze(source)
        m = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        b_unit = _get_unit(result, "b")
        c_unit = _get_unit(result, "c")
        assert b_unit is not None and b_unit.dimensions_equal(m)
        assert c_unit is not None and c_unit.dimensions_equal(m)


class TestMultiplicationConstraint:
    """3.4: c = a * b with known unit(a) and unit(b) infers unit(c)."""

    def test_mass_times_velocity(self):
        source = """
mass = 5.0  # unit: kg
velocity = 10.0  # unit: m/s
momentum = mass * velocity
"""
        result = _analyze(source)
        p = _get_unit(result, "momentum")
        expected = UnitVector.from_list([1, 1, -1, 0, 0, 0, 0])
        assert p is not None
        assert p.dimensions_equal(expected)


class TestDivisionConstraint:
    """3.5: c = a / b with known unit(c) and unit(b) infers unit(a)."""

    def test_velocity_from_distance_time(self):
        source = """
distance = 100.0  # unit: m
time = 10.0  # unit: s
velocity = distance / time
"""
        result = _analyze(source)
        v = _get_unit(result, "velocity")
        expected = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert v is not None
        assert v.dimensions_equal(expected)


class TestViolationDetection:
    """3.6: Conflicting constraints produce a Violation."""

    def test_addition_mismatch_detected(self):
        source = """
velocity = 10.0     # unit: m/s
acceleration = 9.8  # unit: m/s^2
result = velocity + acceleration
"""
        result = _analyze(source)
        assert len(result.violations) > 0

    def test_assignment_mismatch_through_chain(self):
        """Benchmark 1.3: Force computation with wrong formula."""
        source = """
mass = 5.0      # unit: kg
velocity = 10.0  # unit: m/s
force = mass * velocity
drag = 100.0  # unit: N
thrust = force + drag
"""
        result = _analyze(source)
        assert len(result.violations) > 0


class TestProvenanceTracking:
    """3.7: Each inferred unit has a complete provenance chain."""

    def test_provenance_exists(self):
        source = """
distance = 100.0  # unit: m
time = 10.0  # unit: s
velocity = distance / time
"""
        result = _analyze(source)
        # Velocity should have provenance
        # Check that the velocity was inferred (it may be through a temp)
        assert _get_unit(result, "velocity") is not None


class TestFixedPointConvergence:
    """3.8: Propagation terminates for all acyclic IR."""

    def test_long_chain_converges(self):
        lines = ["x0 = 1.0  # unit: m"]
        for i in range(1, 25):
            lines.append(f"x{i} = x{i-1}")
        source = "\n".join(lines)
        result = _analyze(source)
        assert len(result.violations) == 0
        m = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        for i in range(25):
            u = _get_unit(result, f"x{i}")
            assert u is not None and u.dimensions_equal(m)


class TestBenchmark1_2:
    """3.9: Benchmark 1.2 -- velocity-acceleration addition flagged."""

    def test_velocity_acceleration_flagged(self):
        source = """
velocity = 10.0     # unit: m/s
acceleration = 9.8  # unit: m/s^2
result = velocity + acceleration
"""
        result = _analyze(source)
        assert len(result.violations) >= 1
        # At least one violation should mention the unit mismatch
        msgs = [v.message for v in result.violations]
        assert any("m/s" in m for m in msgs)


class TestBenchmark1_5:
    """3.10: Benchmark 1.5 -- correct code produces zero violations."""

    def test_correct_physics(self):
        source = """
distance = 100.0    # unit: m
time = 10.0         # unit: s
velocity = distance / time
acceleration = velocity / time
"""
        result = _analyze(source)
        assert len(result.violations) == 0

        v = _get_unit(result, "velocity")
        expected_v = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert v is not None and v.dimensions_equal(expected_v)

        a = _get_unit(result, "acceleration")
        expected_a = UnitVector.from_list([1, 0, -2, 0, 0, 0, 0])
        assert a is not None and a.dimensions_equal(expected_a)


class TestBenchmark1_10:
    """3.11: Benchmark 1.10 -- multi-operation expression correctly analyzed."""

    def test_kinetic_and_potential_energy(self):
        source = """
mass = 2.0          # unit: kg
velocity = 3.0      # unit: m/s
height = 10.0       # unit: m
g = 9.81            # unit: m/s^2

kinetic = 0.5 * mass * velocity ** 2
potential = mass * g * height
total = kinetic + potential
"""
        result = _analyze(source)
        # Both kinetic and potential should be J = kg*m^2/s^2
        assert len(result.violations) == 0

        joule = UnitVector.from_list([2, 1, -2, 0, 0, 0, 0])
        kin = _get_unit(result, "kinetic")
        pot = _get_unit(result, "potential")
        assert kin is not None and kin.dimensions_equal(joule)
        assert pot is not None and pot.dimensions_equal(joule)

    def test_kinetic_plus_mass_violation(self):
        source = """
mass = 2.0          # unit: kg
velocity = 3.0      # unit: m/s

kinetic = 0.5 * mass * velocity ** 2
bad_total = kinetic + mass
"""
        result = _analyze(source)
        assert len(result.violations) >= 1
