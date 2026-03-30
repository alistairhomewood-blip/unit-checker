"""Tests for the unit algebra engine (Checkpoint 1).

Tests cover:
    1.1  Vector representation (Rational exponents)
    1.2  Multiplication (dimension addition)
    1.3  Division (dimension subtraction)
    1.4  Exponentiation (dimension scaling)
    1.5  Square root
    1.6  Equality
    1.7  Inequality
    1.8  Dimensionless
    1.9  Named unit lookup
    1.10 Unit string parsing
    1.11 Unit string rendering
    1.12 Property-based: multiply then divide returns original
    1.13 Property-based: multiply by dimensionless is identity
"""

from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from unit_checker.core.unit_algebra import UnitVector, DIMENSIONLESS
from unit_checker.core.unit_registry import default_registry


# === 1.1 Vector Representation ===

class TestVectorRepresentation:
    """All 7 SI dimensions stored as Rational, not float."""

    def test_from_list_creates_fractions(self):
        uv = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert isinstance(uv.length, Fraction)
        assert isinstance(uv.time, Fraction)
        assert uv.length == Fraction(1)
        assert uv.time == Fraction(-1)

    def test_all_seven_dimensions(self):
        uv = UnitVector.from_list([1, 2, 3, 4, 5, 6, 7])
        assert uv.length == 1
        assert uv.mass == 2
        assert uv.time == 3
        assert uv.current == 4
        assert uv.temperature == 5
        assert uv.amount == 6
        assert uv.luminosity == 7

    def test_fractional_exponents(self):
        uv = UnitVector.from_list([0.5, 0, 0, 0, 0, 0, 0])
        assert uv.length == Fraction(1, 2)

    def test_dimensionless_is_all_zero(self):
        d = DIMENSIONLESS
        assert all(x == 0 for x in d.to_list())
        assert d.is_dimensionless

    def test_invalid_dimension_count_raises(self):
        with pytest.raises(ValueError):
            UnitVector.from_list([1, 0])


# === 1.2 Multiplication ===

class TestMultiplication:
    """velocity * time = distance: [1,0,-1] + [0,0,1] = [1,0,0]."""

    def test_velocity_times_time_is_distance(self):
        velocity = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])  # m/s
        time = UnitVector.from_list([0, 0, 1, 0, 0, 0, 0])       # s
        result = velocity * time
        expected = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])   # m
        assert result.dimensions_equal(expected)

    def test_mass_times_acceleration_is_force(self):
        mass = UnitVector.from_list([0, 1, 0, 0, 0, 0, 0])       # kg
        accel = UnitVector.from_list([1, 0, -2, 0, 0, 0, 0])     # m/s^2
        result = mass * accel
        force = UnitVector.from_list([1, 1, -2, 0, 0, 0, 0])     # N = kg*m/s^2
        assert result.dimensions_equal(force)

    def test_multiply_by_dimensionless(self):
        velocity = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        result = velocity * DIMENSIONLESS
        assert result.dimensions_equal(velocity)


# === 1.3 Division ===

class TestDivision:
    """distance / time = velocity: [1,0,0] - [0,0,1] = [1,0,-1]."""

    def test_distance_over_time_is_velocity(self):
        distance = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])  # m
        time = UnitVector.from_list([0, 0, 1, 0, 0, 0, 0])      # s
        result = distance / time
        velocity = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0]) # m/s
        assert result.dimensions_equal(velocity)

    def test_divide_same_unit_is_dimensionless(self):
        m = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        result = m / m
        assert result.is_dimensionless


# === 1.4 Exponentiation ===

class TestExponentiation:
    """length^2 = area: 2 * [1,0,0] = [2,0,0]."""

    def test_length_squared_is_area(self):
        length = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        area = length ** 2
        expected = UnitVector.from_list([2, 0, 0, 0, 0, 0, 0])
        assert area.dimensions_equal(expected)

    def test_length_cubed_is_volume(self):
        length = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        volume = length ** 3
        expected = UnitVector.from_list([3, 0, 0, 0, 0, 0, 0])
        assert volume.dimensions_equal(expected)

    def test_negative_exponent(self):
        time = UnitVector.from_list([0, 0, 1, 0, 0, 0, 0])
        hz = time ** -1
        expected = UnitVector.from_list([0, 0, -1, 0, 0, 0, 0])
        assert hz.dimensions_equal(expected)


# === 1.5 Square Root ===

class TestSquareRoot:
    """area^0.5 = length: 0.5 * [2,0,0] = [1,0,0]."""

    def test_sqrt_of_area_is_length(self):
        area = UnitVector.from_list([2, 0, 0, 0, 0, 0, 0])
        length = area ** Fraction(1, 2)
        expected = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        assert length.dimensions_equal(expected)

    def test_sqrt_of_dimensionless_is_dimensionless(self):
        result = DIMENSIONLESS ** Fraction(1, 2)
        assert result.is_dimensionless


# === 1.6 Equality ===

class TestEquality:
    """m/s == m/s."""

    def test_same_units_are_equal(self):
        a = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        b = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert a.dimensions_equal(b)
        assert a.compatible_with(b)

    def test_frozen_dataclass_equality(self):
        a = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        b = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert a == b


# === 1.7 Inequality ===

class TestInequality:
    """m/s != m/s^2."""

    def test_different_units_are_not_equal(self):
        velocity = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        accel = UnitVector.from_list([1, 0, -2, 0, 0, 0, 0])
        assert not velocity.dimensions_equal(accel)

    def test_different_dimensions_not_compatible(self):
        m = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        kg = UnitVector.from_list([0, 1, 0, 0, 0, 0, 0])
        assert not m.compatible_with(kg)


# === 1.8 Dimensionless ===

class TestDimensionless:
    """m/m = dimensionless."""

    def test_same_unit_division_is_dimensionless(self):
        m = UnitVector.from_list([1, 0, 0, 0, 0, 0, 0])
        result = m / m
        assert result.is_dimensionless
        assert result.dimensions_equal(DIMENSIONLESS)

    def test_dimensionless_multiply_preserves_unit(self):
        velocity = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        result = velocity * DIMENSIONLESS
        assert result.dimensions_equal(velocity)


# === 1.9 Named Unit Lookup ===

class TestNamedUnitLookup:
    """'N' resolves to [1,1,-2,0,0,0,0]."""

    def test_newton(self):
        n = default_registry.lookup("N")
        assert n is not None
        expected = UnitVector.from_list([1, 1, -2, 0, 0, 0, 0])
        assert n.dimensions_equal(expected)

    def test_joule(self):
        j = default_registry.lookup("J")
        assert j is not None
        expected = UnitVector.from_list([2, 1, -2, 0, 0, 0, 0])
        assert j.dimensions_equal(expected)

    def test_watt(self):
        w = default_registry.lookup("W")
        assert w is not None
        expected = UnitVector.from_list([2, 1, -3, 0, 0, 0, 0])
        assert w.dimensions_equal(expected)

    def test_aliases(self):
        assert default_registry.lookup("newton") is not None
        assert default_registry.lookup("meter") is not None
        n1 = default_registry.lookup("N")
        n2 = default_registry.lookup("newton")
        assert n1 is not None and n2 is not None
        assert n1.dimensions_equal(n2)


# === 1.10 Unit String Parsing ===

class TestUnitStringParsing:
    """'kg*m/s^2' parses to [1,1,-2,0,0,0,0]."""

    def test_parse_compound(self):
        result = default_registry.parse_unit_string("kg*m/s^2")
        expected = UnitVector.from_list([1, 1, -2, 0, 0, 0, 0])
        assert result.dimensions_equal(expected)

    def test_parse_velocity(self):
        result = default_registry.parse_unit_string("m/s")
        expected = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert result.dimensions_equal(expected)

    def test_parse_dimensionless(self):
        result = default_registry.parse_unit_string("1")
        assert result.is_dimensionless

    def test_parse_dimensionless_word(self):
        result = default_registry.parse_unit_string("dimensionless")
        assert result.is_dimensionless

    def test_parse_energy(self):
        result = default_registry.parse_unit_string("kg*m^2/s^2")
        j = default_registry.lookup("J")
        assert result.dimensions_equal(j)

    def test_parse_pressure(self):
        result = default_registry.parse_unit_string("kg/m/s^2")
        pa = default_registry.lookup("Pa")
        assert result.dimensions_equal(pa)

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError, match="Unknown unit"):
            default_registry.parse_unit_string("furlongs")


# === 1.11 Unit String Rendering ===

class TestUnitStringRendering:
    """[1,1,-2,0,0,0,0] renders as 'kg*m/s^2' or 'N'."""

    def test_render_velocity(self):
        v = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])
        assert v.to_unit_string() == "m/s"

    def test_render_force(self):
        f = UnitVector.from_list([1, 1, -2, 0, 0, 0, 0])
        s = f.to_unit_string()
        assert "m" in s and "kg" in s and "s" in s

    def test_render_dimensionless(self):
        assert DIMENSIONLESS.to_unit_string() == "dimensionless"

    def test_render_area(self):
        a = UnitVector.from_list([2, 0, 0, 0, 0, 0, 0])
        assert a.to_unit_string() == "m^2"

    def test_named_unit_lookup_for_render(self):
        n = UnitVector.from_list([1, 1, -2, 0, 0, 0, 0])
        name = default_registry.get_name(n)
        assert name == "N"


# === 1.12 Property-Based: Multiply then Divide ===

class TestPropertyMultiplyDivide:
    """For random unit U, (U * V) / V == U."""

    @given(
        dims=st.lists(st.integers(min_value=-5, max_value=5), min_size=7, max_size=7),
        dims2=st.lists(st.integers(min_value=-5, max_value=5), min_size=7, max_size=7),
    )
    @settings(max_examples=200)
    def test_multiply_then_divide_identity(self, dims, dims2):
        u = UnitVector.from_list(dims)
        v = UnitVector.from_list(dims2)
        result = (u * v) / v
        assert result.dimensions_equal(u)

    @given(
        dims=st.lists(st.integers(min_value=-5, max_value=5), min_size=7, max_size=7),
    )
    @settings(max_examples=200)
    def test_divide_then_multiply_identity(self, dims):
        u = UnitVector.from_list(dims)
        v = UnitVector.from_list([1, 0, -1, 0, 0, 0, 0])  # m/s
        result = (u / v) * v
        assert result.dimensions_equal(u)


# === 1.13 Property-Based: Multiply by Dimensionless ===

class TestPropertyDimensionless:
    """For random unit U, U * dimensionless == U."""

    @given(
        dims=st.lists(st.integers(min_value=-5, max_value=5), min_size=7, max_size=7),
    )
    @settings(max_examples=200)
    def test_multiply_by_dimensionless_is_identity(self, dims):
        u = UnitVector.from_list(dims)
        result = u * DIMENSIONLESS
        assert result.dimensions_equal(u)

    @given(
        dims=st.lists(st.integers(min_value=-5, max_value=5), min_size=7, max_size=7),
    )
    @settings(max_examples=200)
    def test_power_zero_is_dimensionless(self, dims):
        u = UnitVector.from_list(dims)
        result = u ** 0
        assert result.is_dimensionless

    @given(
        dims=st.lists(st.integers(min_value=-5, max_value=5), min_size=7, max_size=7),
    )
    @settings(max_examples=200)
    def test_power_one_is_identity(self, dims):
        u = UnitVector.from_list(dims)
        result = u ** 1
        assert result.dimensions_equal(u)


# === 1.14 Scale Factor ===

class TestScaleFactor:
    """Scale factors distinguish prefixed units from base units."""

    def test_km_has_scale_1000(self):
        km = default_registry.lookup("km")
        assert km is not None
        assert km.scale_factor == 1e3

    def test_m_has_scale_1(self):
        m = default_registry.lookup("m")
        assert m is not None
        assert m.scale_factor == 1.0

    def test_km_and_m_same_dimensions(self):
        km = default_registry.lookup("km")
        m = default_registry.lookup("m")
        assert km.dimensions_equal(m)

    def test_km_and_m_not_compatible(self):
        km = default_registry.lookup("km")
        m = default_registry.lookup("m")
        assert not km.compatible_with(m)

    def test_liter_has_scale_1e_minus_3(self):
        L = default_registry.lookup("L")
        assert L is not None
        assert L.scale_factor == 1e-3

    def test_liter_and_m3_same_dimensions(self):
        L = default_registry.lookup("L")
        m3 = default_registry.lookup("m^3")
        assert L.dimensions_equal(m3)

    def test_liter_and_m3_not_compatible(self):
        L = default_registry.lookup("L")
        m3 = default_registry.lookup("m^3")
        assert not L.compatible_with(m3)

    def test_multiply_scales(self):
        km = default_registry.lookup("km")
        m = default_registry.lookup("m")
        result = km.multiply(m)
        assert result.scale_factor == 1000.0

    def test_divide_scales(self):
        km = default_registry.lookup("km")
        m = default_registry.lookup("m")
        result = km.divide(m)
        assert result.scale_factor == 1000.0

    def test_power_scales(self):
        km = default_registry.lookup("km")
        result = km.power(2)
        assert result.scale_factor == 1e6

    def test_minute_scale(self):
        minute = default_registry.lookup("min")
        assert minute is not None
        assert minute.scale_factor == 60.0

    def test_hour_scale(self):
        hr = default_registry.lookup("hr")
        assert hr is not None
        assert hr.scale_factor == 3600.0

    def test_ms_scale(self):
        ms = default_registry.lookup("ms")
        assert ms is not None
        assert ms.scale_factor == 1e-3

    def test_g_scale(self):
        g = default_registry.lookup("g")
        assert g is not None
        assert g.scale_factor == 1e-3

    def test_mg_scale(self):
        mg = default_registry.lookup("mg")
        assert mg is not None
        assert mg.scale_factor == 1e-6

    def test_kJ_scale(self):
        kJ = default_registry.lookup("kJ")
        assert kJ is not None
        assert kJ.scale_factor == 1e3

    def test_get_name_distinguishes_km_from_m(self):
        km = default_registry.lookup("km")
        m = default_registry.lookup("m")
        km_name = default_registry.get_name(km)
        m_name = default_registry.get_name(m)
        assert km_name != m_name
        assert m_name == "m"

    def test_get_name_distinguishes_L_from_m3(self):
        L = default_registry.lookup("L")
        m3 = default_registry.lookup("m^3")
        L_name = default_registry.get_name(L)
        m3_name = default_registry.get_name(m3)
        assert L_name != m3_name


# === 1.15 Kind Tags ===

class TestKindTags:
    """Kind tags distinguish angle, solid angle, temperature types."""

    def test_rad_is_dimensionless_with_angle_kind(self):
        rad = default_registry.lookup("rad")
        assert rad is not None
        assert rad.is_dimensionless
        assert rad.kind == "angle"

    def test_sr_is_dimensionless_with_solid_angle_kind(self):
        sr = default_registry.lookup("sr")
        assert sr is not None
        assert sr.is_dimensionless
        assert sr.kind == "solid_angle"

    def test_rad_not_equal_to_dimensionless(self):
        rad = default_registry.lookup("rad")
        dimless = default_registry.lookup("dimensionless")
        assert rad != dimless

    def test_rad_not_compatible_with_sr(self):
        rad = default_registry.lookup("rad")
        sr = default_registry.lookup("sr")
        assert not rad.compatible_with(sr)

    def test_rad_compatible_with_rad(self):
        rad = default_registry.lookup("rad")
        assert rad.compatible_with(rad)

    def test_degC_has_absolute_temperature_kind(self):
        degC = default_registry.lookup("degC")
        assert degC is not None
        assert degC.kind == "absolute_temperature"

    def test_deltaK_has_temperature_difference_kind(self):
        deltaK = default_registry.lookup("deltaK")
        assert deltaK is not None
        assert deltaK.kind == "temperature_difference"

    def test_K_has_no_kind(self):
        K = default_registry.lookup("K")
        assert K is not None
        assert K.kind is None

    def test_degC_not_compatible_with_deltaK(self):
        degC = default_registry.lookup("degC")
        deltaK = default_registry.lookup("deltaK")
        assert not degC.compatible_with(deltaK)

    def test_kinds_compatible_both_none(self):
        m = default_registry.lookup("m")
        kg = default_registry.lookup("kg")
        assert m._kinds_compatible(kg)

    def test_kinds_compatible_one_none(self):
        K = default_registry.lookup("K")
        degC = default_registry.lookup("degC")
        assert K._kinds_compatible(degC)
