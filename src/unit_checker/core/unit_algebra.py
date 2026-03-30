"""Unit algebra engine.

Represents physical units as 7-dimensional vectors over SI base dimensions:
    [length (m), mass (kg), time (s), current (A), temperature (K), amount (mol), luminosity (cd)]

Operations:
    - Multiplication: vector addition     (velocity * time = distance)
    - Division: vector subtraction        (distance / time = velocity)
    - Exponentiation: scalar multiply     (length^2 = area)
    - Equality: vector comparison         (m/s == m/s)

All exponents use fractions.Fraction for exact rational arithmetic,
avoiding floating-point comparison issues (important for sqrt, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional, Sequence


# Indices into the dimension vector
DIM_LENGTH = 0       # meters (m)
DIM_MASS = 1         # kilograms (kg)
DIM_TIME = 2         # seconds (s)
DIM_CURRENT = 3      # amperes (A)
DIM_TEMPERATURE = 4  # kelvin (K)
DIM_AMOUNT = 5       # moles (mol)
DIM_LUMINOSITY = 6   # candela (cd)

NUM_DIMENSIONS = 7

DIMENSION_NAMES = ("length", "mass", "time", "current", "temperature", "amount", "luminosity")
DIMENSION_SYMBOLS = ("m", "kg", "s", "A", "K", "mol", "cd")


def _to_fraction(val: int | float | Fraction | str) -> Fraction:
    """Convert a value to a Fraction, handling common cases."""
    if isinstance(val, Fraction):
        return val
    if isinstance(val, int):
        return Fraction(val)
    if isinstance(val, float):
        return Fraction(val).limit_denominator(1000)
    if isinstance(val, str):
        return Fraction(val)
    raise TypeError(f"Cannot convert {type(val).__name__} to Fraction")


@dataclass(frozen=True, slots=True)
class UnitVector:
    """A 7-dimensional vector representing physical dimensions.

    Each component is a rational exponent of the corresponding SI base unit.
    For example, velocity (m/s) = UnitVector(length=1, time=-1).
    Force (N = kg*m/s^2) = UnitVector(length=1, mass=1, time=-2).
    """

    length: Fraction = field(default_factory=lambda: Fraction(0))
    mass: Fraction = field(default_factory=lambda: Fraction(0))
    time: Fraction = field(default_factory=lambda: Fraction(0))
    current: Fraction = field(default_factory=lambda: Fraction(0))
    temperature: Fraction = field(default_factory=lambda: Fraction(0))
    amount: Fraction = field(default_factory=lambda: Fraction(0))
    luminosity: Fraction = field(default_factory=lambda: Fraction(0))
    kind: Optional[str] = None
    scale_factor: float = 1.0

    @classmethod
    def from_list(
        cls,
        dims: Sequence[int | float | Fraction],
        kind: Optional[str] = None,
        scale_factor: float = 1.0,
    ) -> UnitVector:
        """Create a UnitVector from a list of 7 dimension exponents."""
        if len(dims) != NUM_DIMENSIONS:
            raise ValueError(f"Expected {NUM_DIMENSIONS} dimensions, got {len(dims)}")
        return cls(
            length=_to_fraction(dims[0]),
            mass=_to_fraction(dims[1]),
            time=_to_fraction(dims[2]),
            current=_to_fraction(dims[3]),
            temperature=_to_fraction(dims[4]),
            amount=_to_fraction(dims[5]),
            luminosity=_to_fraction(dims[6]),
            kind=kind,
            scale_factor=scale_factor,
        )

    @classmethod
    def dimensionless(cls, kind: Optional[str] = None, scale_factor: float = 1.0) -> UnitVector:
        """Create a dimensionless unit vector."""
        return cls(kind=kind, scale_factor=scale_factor)

    def to_list(self) -> list[Fraction]:
        """Return the 7 dimension exponents as a list."""
        return [
            self.length, self.mass, self.time,
            self.current, self.temperature, self.amount, self.luminosity,
        ]

    @property
    def is_dimensionless(self) -> bool:
        """True if all dimension exponents are zero."""
        return all(d == 0 for d in self.to_list())

    def _kinds_compatible(self, other: UnitVector) -> bool:
        """Check if kind tags are compatible.

        Compatible means: both None, or both equal, or one is None.
        (Untagged dimensionless is compatible with any kind.)
        """
        if self.kind is None or other.kind is None:
            return True
        return self.kind == other.kind

    def dimensions_equal(self, other: UnitVector) -> bool:
        """Check if two unit vectors have the same dimensions (ignoring kind)."""
        return self.to_list() == other.to_list()

    def compatible_with(self, other: UnitVector) -> bool:
        """Check if two unit vectors are fully compatible (dimensions + kind + scale)."""
        return (
            self.dimensions_equal(other)
            and self._kinds_compatible(other)
            and self.scale_factor == other.scale_factor
        )

    def scale_compatible_with(self, other: UnitVector) -> bool:
        """Check if two unit vectors have the same scale factor."""
        return self.scale_factor == other.scale_factor

    def multiply(self, other: UnitVector) -> UnitVector:
        """Multiply two units: dimensions add.

        Example: velocity (m/s) * time (s) = distance (m)
            [1,0,-1,...] + [0,0,1,...] = [1,0,0,...]
        """
        result_kind = self._resolve_kind_multiply(other)
        return UnitVector(
            length=self.length + other.length,
            mass=self.mass + other.mass,
            time=self.time + other.time,
            current=self.current + other.current,
            temperature=self.temperature + other.temperature,
            amount=self.amount + other.amount,
            luminosity=self.luminosity + other.luminosity,
            kind=result_kind,
            scale_factor=self.scale_factor * other.scale_factor,
        )

    def divide(self, other: UnitVector) -> UnitVector:
        """Divide two units: dimensions subtract.

        Example: distance (m) / time (s) = velocity (m/s)
            [1,0,0,...] - [0,0,1,...] = [1,0,-1,...]
        """
        result_kind = self._resolve_kind_divide(other)
        new_scale = self.scale_factor / other.scale_factor if other.scale_factor != 0 else 1.0
        return UnitVector(
            length=self.length - other.length,
            mass=self.mass - other.mass,
            time=self.time - other.time,
            current=self.current - other.current,
            temperature=self.temperature - other.temperature,
            amount=self.amount - other.amount,
            luminosity=self.luminosity - other.luminosity,
            kind=result_kind,
            scale_factor=new_scale,
        )

    def power(self, exponent: int | float | Fraction) -> UnitVector:
        """Raise unit to a power: dimensions scale.

        Example: length^2 = area: 2 * [1,0,0,...] = [2,0,0,...]
        """
        exp = _to_fraction(exponent)
        return UnitVector(
            length=self.length * exp,
            mass=self.mass * exp,
            time=self.time * exp,
            current=self.current * exp,
            temperature=self.temperature * exp,
            amount=self.amount * exp,
            luminosity=self.luminosity * exp,
            kind=self.kind,
            scale_factor=self.scale_factor ** float(exp),
        )

    def _resolve_kind_multiply(self, other: UnitVector) -> Optional[str]:
        """Resolve kind tag for multiplication.

        If both operands have the same kind, result keeps it.
        If one is None, inherit the other.
        If different non-None kinds, result is None (mixed operation).
        """
        if self.kind is None:
            return other.kind
        if other.kind is None:
            return self.kind
        if self.kind == other.kind:
            return self.kind
        return None

    def _resolve_kind_divide(self, other: UnitVector) -> Optional[str]:
        """Resolve kind tag for division.

        Same-kind division may produce a dimensionless result (e.g., m/m),
        in which case kind should be None (plain dimensionless).
        """
        result = UnitVector(
            length=self.length - other.length,
            mass=self.mass - other.mass,
            time=self.time - other.time,
            current=self.current - other.current,
            temperature=self.temperature - other.temperature,
            amount=self.amount - other.amount,
            luminosity=self.luminosity - other.luminosity,
        )
        if result.is_dimensionless:
            return None
        return self._resolve_kind_multiply(other)

    def __mul__(self, other: UnitVector) -> UnitVector:
        if not isinstance(other, UnitVector):
            return NotImplemented
        return self.multiply(other)

    def __truediv__(self, other: UnitVector) -> UnitVector:
        if not isinstance(other, UnitVector):
            return NotImplemented
        return self.divide(other)

    def __pow__(self, exponent: int | float | Fraction) -> UnitVector:
        return self.power(exponent)

    def __repr__(self) -> str:
        parts = []
        for name, val in zip(DIMENSION_NAMES, self.to_list(), strict=True):
            if val != 0:
                parts.append(f"{name}={val}")
        kind_str = f", kind={self.kind!r}" if self.kind else ""
        scale_str = f", scale={self.scale_factor}" if self.scale_factor != 1.0 else ""
        return f"UnitVector({', '.join(parts)}{kind_str}{scale_str})"

    def to_unit_string(self) -> str:
        """Render as a human-readable unit string like 'kg*m/s^2'.

        Uses SI base unit symbols. Groups positive exponents in the numerator
        and negative exponents in the denominator.
        """
        dims = self.to_list()
        if all(d == 0 for d in dims):
            return "dimensionless"

        numerator_parts: list[str] = []
        denominator_parts: list[str] = []

        for symbol, exp in zip(DIMENSION_SYMBOLS, dims, strict=True):
            if exp > 0:
                if exp == 1:
                    numerator_parts.append(symbol)
                else:
                    numerator_parts.append(f"{symbol}^{_format_exponent(exp)}")
            elif exp < 0:
                abs_exp = -exp
                if abs_exp == 1:
                    denominator_parts.append(symbol)
                else:
                    denominator_parts.append(f"{symbol}^{_format_exponent(abs_exp)}")

        if numerator_parts and denominator_parts:
            denom = "*".join(denominator_parts)
            if len(denominator_parts) > 1:
                denom = f"({denom})"
            return "*".join(numerator_parts) + "/" + denom
        elif numerator_parts:
            return "*".join(numerator_parts)
        else:
            # Only negative exponents, e.g., 1/s = Hz
            denom = "*".join(denominator_parts)
            if len(denominator_parts) > 1:
                denom = f"({denom})"
            return "1/" + denom


def _format_exponent(exp: Fraction) -> str:
    """Format an exponent for display. Integers show without denominator."""
    if exp.denominator == 1:
        return str(exp.numerator)
    return str(exp)


# Singleton for the dimensionless unit
DIMENSIONLESS = UnitVector.dimensionless()
