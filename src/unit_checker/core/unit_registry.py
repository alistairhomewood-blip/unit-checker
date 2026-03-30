"""Unit registry: maps unit names and symbols to their dimensional vectors.

Contains:
    - SI base units (m, kg, s, A, K, mol, cd)
    - SI derived units (N, J, W, Pa, Hz, C, V, ohm, etc.)
    - SI prefixes (k, M, G, m, mu, n, etc.)
    - Unit string parser (converts "kg*m/s^2" -> UnitVector)
"""

from __future__ import annotations

from fractions import Fraction
from typing import Optional

from unit_checker.core.unit_algebra import UnitVector, DIMENSIONLESS, _to_fraction


class UnitRegistry:
    """Registry of named units and their dimension vectors.

    Provides lookup by name/symbol and parsing of compound unit strings.
    """

    def __init__(self) -> None:
        self._units: dict[str, UnitVector] = {}
        self._aliases: dict[str, str] = {}  # alias -> canonical name
        self._names_for_unit: dict[tuple[Fraction, ...], list[str]] = {}

    def register(self, name: str, unit: UnitVector, aliases: Optional[list[str]] = None) -> None:
        """Register a named unit."""
        self._units[name] = unit
        key = self._unit_key(unit)
        self._names_for_unit.setdefault(key, []).append(name)
        if aliases:
            for alias in aliases:
                self._aliases[alias] = name
                self._units[alias] = unit

    @staticmethod
    def _unit_key(unit: UnitVector) -> tuple:
        """Create a hashable key for a unit vector (dimensions + scale + kind)."""
        return (*tuple(unit.to_list()), unit.scale_factor, unit.kind)

    def lookup(self, name: str) -> Optional[UnitVector]:
        """Look up a unit by name or alias. Returns None if not found."""
        return self._units.get(name)

    def get_name(self, unit: UnitVector) -> Optional[str]:
        """Find a common name for a unit vector, if one exists.

        Prefers short names (e.g., "N" over "newton").
        Uses full key (dimensions + scale + kind) for lookup.
        """
        key = self._unit_key(unit)
        names = self._names_for_unit.get(key)
        if not names:
            return None
        # Prefer shortest name (symbol over full name)
        return min(names, key=len)

    def parse_unit_string(self, unit_str: str) -> UnitVector:
        """Parse a unit string like 'kg*m/s^2' into a UnitVector.

        Grammar:
            unit_string := unit_term (('*' | '/') unit_term)*
            unit_term   := unit_name ('^' exponent)?
            unit_name   := registered name or symbol
            exponent    := integer | '-' integer | fraction

        Special cases:
            '1' or 'dimensionless' -> DIMENSIONLESS
        """
        unit_str = unit_str.strip()
        if unit_str in ("1", "dimensionless", ""):
            return DIMENSIONLESS

        return self._parse_compound(unit_str)

    def _parse_compound(self, unit_str: str) -> UnitVector:
        """Parse a compound unit string with * and / operators."""
        # Preprocess: expand parenthesized groups in denominators.
        # E.g. "kg/(m*s^2)" -> "kg/m/s^2"
        # This handles the common pattern X/(A*B*...) by distributing the division.
        unit_str = _expand_parenthesized_denominators(unit_str)

        # Tokenize: split on * and /, preserving the operator
        tokens = _tokenize_unit_string(unit_str)

        result = UnitVector.dimensionless()
        current_op = "*"  # initial implied multiplication

        for token in tokens:
            if token in ("*", "/"):
                current_op = token
                continue

            # Parse single unit term (possibly with exponent)
            term_unit = self._parse_term(token)

            if current_op == "*":
                result = result.multiply(term_unit)
            else:
                result = result.divide(term_unit)

        return result

    def _parse_term(self, term: str) -> UnitVector:
        """Parse a single unit term like 'kg', 'm^2', 's^-1'."""
        # Split on ^
        if "^" in term:
            parts = term.split("^", 1)
            name = parts[0].strip()
            exp_str = parts[1].strip()
            # Handle parenthesized exponents like ^(1/2)
            exp_str = exp_str.strip("()")
            try:
                exponent = _to_fraction(exp_str)
            except (ValueError, ZeroDivisionError):
                raise ValueError(f"Invalid exponent in unit term: {term!r}")
        else:
            name = term.strip()
            exponent = Fraction(1)

        # Look up base unit
        base_unit = self.lookup(name)
        if base_unit is None:
            raise ValueError(f"Unknown unit: {name!r}")

        if exponent == 1:
            return base_unit
        return base_unit.power(exponent)

    def format_unit(self, unit: UnitVector) -> str:
        """Format a unit vector as a human-readable string.

        Tries named units first (e.g., "N"), then falls back to
        the unit vector's own rendering (e.g., "kg*m/s^2").
        """
        name = self.get_name(unit)
        if name:
            expanded = unit.to_unit_string()
            if name != expanded:
                return f"{name} = {expanded}"
            return name
        return unit.to_unit_string()


def _expand_parenthesized_denominators(unit_str: str) -> str:
    """Expand parenthesized groups in unit strings.

    Converts patterns like ``X/(A*B)`` into ``X/A/B`` by distributing
    the division operator across the ``*``-separated terms inside the
    parenthesized group.  This works because left-to-right evaluation
    of ``X/A/B`` is equivalent to ``X/(A*B)``.

    Handles nested and multiple groups, e.g.:
        ``kg/(m*s^2)`` -> ``kg/m/s^2``
        ``A*B/(C*D)``  -> ``A*B/C/D``
    """
    result: list[str] = []
    i = 0
    while i < len(unit_str):
        if unit_str[i] == "(":
            # Find the preceding operator to decide how to expand
            # Look back to find if there is a '/' immediately before '('
            preceding_op = None
            j = i - 1
            while j >= 0 and unit_str[j] == " ":
                j -= 1
            if j >= 0 and unit_str[j] == "/":
                preceding_op = "/"
            elif j >= 0 and unit_str[j] == "*":
                preceding_op = "*"

            # Find the matching closing paren
            depth = 1
            end = i + 1
            while end < len(unit_str) and depth > 0:
                if unit_str[end] == "(":
                    depth += 1
                elif unit_str[end] == ")":
                    depth -= 1
                end += 1
            # end now points past the closing paren
            inner = unit_str[i + 1 : end - 1]

            if preceding_op == "/":
                # Replace * inside parens with / to distribute division
                result.append(inner.replace("*", "/"))
            else:
                # Multiplication or no operator: just unwrap parens
                result.append(inner)
            i = end
        else:
            result.append(unit_str[i])
            i += 1

    return "".join(result)


def _tokenize_unit_string(unit_str: str) -> list[str]:
    """Tokenize a unit string into names, operators, and exponents.

    Handles: 'kg*m/s^2', 'kg*m*s^-2', 'J/mol/K', 'N*m'
    """
    tokens: list[str] = []
    current = ""

    i = 0
    while i < len(unit_str):
        ch = unit_str[i]
        if ch in ("*", "/"):
            if current.strip():
                tokens.append(current.strip())
            tokens.append(ch)
            current = ""
        elif ch == " ":
            # whitespace acts as separator only if not inside an exponent
            if current.strip():
                tokens.append(current.strip())
                current = ""
        else:
            current += ch
        i += 1

    if current.strip():
        tokens.append(current.strip())

    return tokens


def _build_si_registry() -> UnitRegistry:
    """Build the default SI unit registry with base and derived units."""
    reg = UnitRegistry()

    # === SI Base Units ===
    reg.register("m", UnitVector.from_list([1, 0, 0, 0, 0, 0, 0]), aliases=["meter", "meters", "metre", "metres"])
    reg.register("kg", UnitVector.from_list([0, 1, 0, 0, 0, 0, 0]), aliases=["kilogram", "kilograms"])
    reg.register("s", UnitVector.from_list([0, 0, 1, 0, 0, 0, 0]), aliases=["second", "seconds", "sec"])
    reg.register("A", UnitVector.from_list([0, 0, 0, 1, 0, 0, 0]), aliases=["ampere", "amperes", "amp", "amps"])
    reg.register("K", UnitVector.from_list([0, 0, 0, 0, 1, 0, 0]), aliases=["kelvin"])
    reg.register("mol", UnitVector.from_list([0, 0, 0, 0, 0, 1, 0]), aliases=["mole", "moles"])
    reg.register("cd", UnitVector.from_list([0, 0, 0, 0, 0, 0, 1]), aliases=["candela"])

    # === SI Derived Units ===
    # Force: Newton = kg*m/s^2
    reg.register("N", UnitVector.from_list([1, 1, -2, 0, 0, 0, 0]), aliases=["newton", "newtons"])
    # Energy: Joule = kg*m^2/s^2
    reg.register("J", UnitVector.from_list([2, 1, -2, 0, 0, 0, 0]), aliases=["joule", "joules"])
    # Power: Watt = kg*m^2/s^3
    reg.register("W", UnitVector.from_list([2, 1, -3, 0, 0, 0, 0]), aliases=["watt", "watts"])
    # Pressure: Pascal = kg/(m*s^2)
    reg.register("Pa", UnitVector.from_list([-1, 1, -2, 0, 0, 0, 0]), aliases=["pascal", "pascals"])
    # Frequency: Hertz = 1/s
    reg.register("Hz", UnitVector.from_list([0, 0, -1, 0, 0, 0, 0]), aliases=["hertz"])
    # Electric charge: Coulomb = A*s
    reg.register("C", UnitVector.from_list([0, 0, 1, 1, 0, 0, 0]), aliases=["coulomb", "coulombs"])
    # Electric potential: Volt = kg*m^2/(A*s^3)
    reg.register("V", UnitVector.from_list([2, 1, -3, -1, 0, 0, 0]), aliases=["volt", "volts"])
    # Electric resistance: Ohm = kg*m^2/(A^2*s^3)
    reg.register("ohm", UnitVector.from_list([2, 1, -3, -2, 0, 0, 0]), aliases=["Ohm"])
    # Electric capacitance: Farad = A^2*s^4/(kg*m^2)
    reg.register("F", UnitVector.from_list([-2, -1, 4, 2, 0, 0, 0]), aliases=["farad", "farads"])
    # Magnetic flux: Weber = kg*m^2/(A*s^2)
    reg.register("Wb", UnitVector.from_list([2, 1, -2, -1, 0, 0, 0]), aliases=["weber", "webers"])
    # Magnetic flux density: Tesla = kg/(A*s^2)
    reg.register("T", UnitVector.from_list([0, 1, -2, -1, 0, 0, 0]), aliases=["tesla", "teslas"])
    # Inductance: Henry = kg*m^2/(A^2*s^2)
    reg.register("H", UnitVector.from_list([2, 1, -2, -2, 0, 0, 0]), aliases=["henry", "henrys", "henries"])

    # === Area and Volume ===
    reg.register("m^2", UnitVector.from_list([2, 0, 0, 0, 0, 0, 0]))
    reg.register("m^3", UnitVector.from_list([3, 0, 0, 0, 0, 0, 0]))

    # === Common non-SI but recognized ===
    # Liter = 0.001 m^3 (1e-3 scale relative to m^3)
    reg.register("L", UnitVector.from_list([3, 0, 0, 0, 0, 0, 0], scale_factor=1e-3),
                 aliases=["liter", "liters", "litre", "litres"])

    # === SI Prefixed Units (common ones) ===
    # Length prefixes -- each has same [L] dimension but distinct scale_factor
    reg.register("km", UnitVector.from_list([1, 0, 0, 0, 0, 0, 0], scale_factor=1e3),
                 aliases=["kilometer", "kilometers"])
    reg.register("cm", UnitVector.from_list([1, 0, 0, 0, 0, 0, 0], scale_factor=1e-2),
                 aliases=["centimeter", "centimeters"])
    reg.register("mm", UnitVector.from_list([1, 0, 0, 0, 0, 0, 0], scale_factor=1e-3),
                 aliases=["millimeter", "millimeters"])
    reg.register("um", UnitVector.from_list([1, 0, 0, 0, 0, 0, 0], scale_factor=1e-6),
                 aliases=["micrometer", "micrometers"])
    reg.register("nm", UnitVector.from_list([1, 0, 0, 0, 0, 0, 0], scale_factor=1e-9),
                 aliases=["nanometer", "nanometers"])

    # Mass prefixes -- kg is the base unit (scale=1), g is 1e-3, mg is 1e-6
    reg.register("g", UnitVector.from_list([0, 1, 0, 0, 0, 0, 0], scale_factor=1e-3),
                 aliases=["gram", "grams"])
    reg.register("mg", UnitVector.from_list([0, 1, 0, 0, 0, 0, 0], scale_factor=1e-6),
                 aliases=["milligram", "milligrams"])

    # Time prefixes
    reg.register("ms", UnitVector.from_list([0, 0, 1, 0, 0, 0, 0], scale_factor=1e-3),
                 aliases=["millisecond", "milliseconds"])
    reg.register("us", UnitVector.from_list([0, 0, 1, 0, 0, 0, 0], scale_factor=1e-6),
                 aliases=["microsecond", "microseconds"])
    reg.register("ns", UnitVector.from_list([0, 0, 1, 0, 0, 0, 0], scale_factor=1e-9),
                 aliases=["nanosecond", "nanoseconds"])
    reg.register("min", UnitVector.from_list([0, 0, 1, 0, 0, 0, 0], scale_factor=60.0),
                 aliases=["minute", "minutes"])
    reg.register("hr", UnitVector.from_list([0, 0, 1, 0, 0, 0, 0], scale_factor=3600.0),
                 aliases=["hour", "hours"])

    # Energy / Power prefixes
    reg.register("kJ", UnitVector.from_list([2, 1, -2, 0, 0, 0, 0], scale_factor=1e3),
                 aliases=["kilojoule", "kilojoules"])
    reg.register("MJ", UnitVector.from_list([2, 1, -2, 0, 0, 0, 0], scale_factor=1e6),
                 aliases=["megajoule", "megajoules"])
    reg.register("kW", UnitVector.from_list([2, 1, -3, 0, 0, 0, 0], scale_factor=1e3),
                 aliases=["kilowatt", "kilowatts"])
    reg.register("MW", UnitVector.from_list([2, 1, -3, 0, 0, 0, 0], scale_factor=1e6),
                 aliases=["megawatt", "megawatts"])

    # Force prefixes
    reg.register("kN", UnitVector.from_list([1, 1, -2, 0, 0, 0, 0], scale_factor=1e3),
                 aliases=["kilonewton", "kilonewtons"])
    reg.register("MN", UnitVector.from_list([1, 1, -2, 0, 0, 0, 0], scale_factor=1e6),
                 aliases=["meganewton", "meganewtons"])

    # Pressure
    reg.register("kPa", UnitVector.from_list([-1, 1, -2, 0, 0, 0, 0], scale_factor=1e3),
                 aliases=["kilopascal", "kilopascals"])
    reg.register("MPa", UnitVector.from_list([-1, 1, -2, 0, 0, 0, 0], scale_factor=1e6),
                 aliases=["megapascal", "megapascals"])
    reg.register("GPa", UnitVector.from_list([-1, 1, -2, 0, 0, 0, 0], scale_factor=1e9),
                 aliases=["gigapascal", "gigapascals"])

    # Velocity / Acceleration shortcuts
    reg.register("m/s", UnitVector.from_list([1, 0, -1, 0, 0, 0, 0]))
    reg.register("m/s^2", UnitVector.from_list([1, 0, -2, 0, 0, 0, 0]))
    # km/h: scale = 1000/3600 ~ 0.2778 relative to m/s
    reg.register("km/h", UnitVector.from_list([1, 0, -1, 0, 0, 0, 0], scale_factor=1000.0 / 3600.0))

    # Density
    reg.register("kg/m^3", UnitVector.from_list([-3, 1, 0, 0, 0, 0, 0]))

    # Momentum
    reg.register("N*s", UnitVector.from_list([1, 1, -1, 0, 0, 0, 0]))
    reg.register("kg*m/s", UnitVector.from_list([1, 1, -1, 0, 0, 0, 0]))

    # Pound-force (force unit, same dimensions as Newton, 1 lbf ~ 4.44822 N)
    reg.register("lbf", UnitVector.from_list([1, 1, -2, 0, 0, 0, 0], scale_factor=4.44822),
                 aliases=["pound_force"])

    # Impulse-force unit (pound-force-seconds for MCO test) - dimensionally same as momentum
    reg.register("lbf*s", UnitVector.from_list([1, 1, -1, 0, 0, 0, 0], scale_factor=4.44822))

    # Dimensionless
    reg.register("dimensionless", DIMENSIONLESS, aliases=["1", "unitless"])

    # Angular units -- dimensionless but with kind tags to prevent misuse
    reg.register("rad", UnitVector.dimensionless(kind="angle"),
                 aliases=["radian", "radians"])
    reg.register("sr", UnitVector.dimensionless(kind="solid_angle"),
                 aliases=["steradian", "steradians"])

    # Temperature variants -- absolute vs difference
    reg.register("degC", UnitVector.from_list([0, 0, 0, 0, 1, 0, 0], kind="absolute_temperature"),
                 aliases=["celsius", "Celsius"])
    reg.register("degF", UnitVector.from_list([0, 0, 0, 0, 1, 0, 0], kind="absolute_temperature",
                 scale_factor=5.0 / 9.0), aliases=["fahrenheit", "Fahrenheit"])
    reg.register("deltaK", UnitVector.from_list([0, 0, 0, 0, 1, 0, 0], kind="temperature_difference"),
                 aliases=["delta_K", "dK"])
    reg.register("deltadegC", UnitVector.from_list([0, 0, 0, 0, 1, 0, 0], kind="temperature_difference"),
                 aliases=["delta_degC", "ddC"])

    return reg


# Module-level default registry
default_registry: UnitRegistry = _build_si_registry()
