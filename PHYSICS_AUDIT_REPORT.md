# Physics and Dimensional Analysis Audit Report

**Auditor:** Claude Opus 4.6 (acting as rigorous physics auditor)
**Date:** 2026-03-29
**Scope:** All source files in `src/unit_checker/` and `tests/`
**Test suite status at time of audit:** 115/115 tests passing

---

## Executive Summary

The unit-checker codebase is **substantially correct** in its physics and dimensional analysis. The core unit algebra engine, the 7-dimensional SI vector representation, and the fundamental constraint propagation rules are all sound. The derived SI unit definitions are correct. The benchmark tests cover real physics scenarios and produce correct results.

However, this audit identifies **6 issues** -- 2 of which are genuine physics/correctness concerns, and 4 are design-level observations that could cause problems as the tool scales beyond MVP.

**Overall verdict: PASS with noted issues.**

---

## 1. Unit Algebra Engine (`core/unit_algebra.py`)

### 1.1 SI Base Dimension Ordering

**PASS.** The 7 SI base dimensions are defined in a standard and consistent order:

| Index | Dimension   | Symbol | SI Base Unit |
|-------|-------------|--------|-------------|
| 0     | length      | m      | meter       |
| 1     | mass        | kg     | kilogram    |
| 2     | time        | s      | second      |
| 3     | current     | A      | ampere      |
| 4     | temperature | K      | kelvin      |
| 5     | amount      | mol    | mole        |
| 6     | luminosity  | cd     | candela     |

This matches the SI standard (the ordering is conventional, not prescribed by SI, but this ordering is internally consistent throughout the codebase). The label "luminosity" at index 6 is technically "luminous intensity" in SI nomenclature, but the symbol (cd) is correct and the vector position is used consistently. This is a cosmetic naming issue only.

### 1.2 Fraction Arithmetic

**PASS.** All dimension exponents use `fractions.Fraction`, which provides exact rational arithmetic. This correctly avoids floating-point comparison issues. The `_to_fraction` helper handles int, float, str, and Fraction inputs. The `limit_denominator(1000)` call for float conversion is a reasonable guard against pathological float-to-rational expansions, and will not affect any physically meaningful exponent (exponents like 1/2, 1/3, 2/3, -1/2 all have denominators well under 1000).

### 1.3 Multiplication (Vector Addition)

**PASS.** `UnitVector.multiply()` adds corresponding dimension exponents. Verified:
- velocity * time = distance: `[1,0,-1] + [0,0,1] = [1,0,0]` -- correct.
- mass * acceleration = force: `[0,1,0] + [1,0,-2] = [1,1,-2]` -- correct.
- Multiplication by dimensionless is identity -- correct.

### 1.4 Division (Vector Subtraction)

**PASS.** `UnitVector.divide()` subtracts corresponding dimension exponents. Verified:
- distance / time = velocity: `[1,0,0] - [0,0,1] = [1,0,-1]` -- correct.
- Same unit / same unit = dimensionless: `[1,0,0] - [1,0,0] = [0,0,0]` -- correct.

### 1.5 Exponentiation (Scalar Multiplication)

**PASS.** `UnitVector.power()` multiplies all exponents by the scalar. Verified:
- length^2 = area: `2 * [1,0,0] = [2,0,0]` -- correct.
- area^(1/2) = length: `(1/2) * [2,0,0] = [1,0,0]` -- correct.
- U^0 = dimensionless -- correct.
- U^1 = U -- correct.

### 1.6 Equality Checking

**PASS.** `dimensions_equal()` compares all 7 exponents (ignoring kind tag). `compatible_with()` checks both dimensions and kind compatibility. The kind compatibility logic (None is compatible with anything, same-kind is compatible) is correct.

### 1.7 Kind Tags

**PASS.** Kind tags correctly disambiguate dimensionless quantities (e.g., radians vs strain). The propagation rules for kind through multiply/divide are sensible:
- Same kind * same kind = same kind.
- None * kind = kind (inheritance).
- Different kinds = None (mixed).
- Same kind / same kind producing dimensionless = None kind (correct -- m/m is plain dimensionless, not "length-flavored dimensionless").

### 1.8 Unit String Rendering

**PASS.** `to_unit_string()` correctly separates numerator (positive exponents) and denominator (negative exponents) and renders with `*` and `/` operators. Integer exponents display without denominators.

**Minor observation:** The rendering `m*kg/s^2` places `m` before `kg` because length (index 0) comes before mass (index 1). While this is unusual (the conventional way to write Newton is `kg*m/s^2`), it is not incorrect -- the multiplication is commutative. This is a display preference, not a physics error.

---

## 2. Unit Registry (`core/unit_registry.py`)

### 2.1 SI Base Units

| Unit | Vector | Expected | Verdict |
|------|--------|----------|---------|
| m (meter) | `[1,0,0,0,0,0,0]` | length^1 | **PASS** |
| kg (kilogram) | `[0,1,0,0,0,0,0]` | mass^1 | **PASS** |
| s (second) | `[0,0,1,0,0,0,0]` | time^1 | **PASS** |
| A (ampere) | `[0,0,0,1,0,0,0]` | current^1 | **PASS** |
| K (kelvin) | `[0,0,0,0,1,0,0]` | temperature^1 | **PASS** |
| mol (mole) | `[0,0,0,0,0,1,0]` | amount^1 | **PASS** |
| cd (candela) | `[0,0,0,0,0,0,1]` | luminosity^1 | **PASS** |

### 2.2 SI Derived Units

| Unit | Registered Vector | Correct Decomposition | Verdict |
|------|-------------------|----------------------|---------|
| N (newton) | `[1,1,-2,0,0,0,0]` | kg*m/s^2 = mass^1 * length^1 * time^-2 | **PASS** |
| J (joule) | `[2,1,-2,0,0,0,0]` | kg*m^2/s^2 = mass^1 * length^2 * time^-2 | **PASS** |
| W (watt) | `[2,1,-3,0,0,0,0]` | kg*m^2/s^3 = mass^1 * length^2 * time^-3 | **PASS** |
| Pa (pascal) | `[-1,1,-2,0,0,0,0]` | kg/(m*s^2) = mass^1 * length^-1 * time^-2 | **PASS** |
| Hz (hertz) | `[0,0,-1,0,0,0,0]` | 1/s = time^-1 | **PASS** |
| C (coulomb) | `[0,0,1,1,0,0,0]` | A*s = current^1 * time^1 | **PASS** |
| V (volt) | `[2,1,-3,-1,0,0,0]` | kg*m^2/(A*s^3) = mass^1 * length^2 * time^-3 * current^-1 | **PASS** |
| ohm (Ohm) | `[2,1,-3,-2,0,0,0]` | kg*m^2/(A^2*s^3) = mass^1 * length^2 * time^-3 * current^-2 | **PASS** |
| F (farad) | `[-2,-1,4,2,0,0,0]` | A^2*s^4/(kg*m^2) = mass^-1 * length^-2 * time^4 * current^2 | **PASS** |
| Wb (weber) | `[2,1,-2,-1,0,0,0]` | kg*m^2/(A*s^2) = mass^1 * length^2 * time^-2 * current^-1 | **PASS** |
| T (tesla) | `[0,1,-2,-1,0,0,0]` | kg/(A*s^2) = mass^1 * time^-2 * current^-1 | **PASS** |
| H (henry) | `[2,1,-2,-2,0,0,0]` | kg*m^2/(A^2*s^2) = mass^1 * length^2 * time^-2 * current^-2 | **PASS** |

**Verification methodology:** Each derived unit was independently verified by expanding its SI definition into base units and checking the resulting exponent vector. For example:
- Volt: V = W/A = J/(A*s) = kg*m^2/(A*s^3). Vector: length=2, mass=1, time=-3, current=-1. Matches `[2,1,-3,-1,0,0,0]`. Correct.
- Farad: F = C/V = A*s/(kg*m^2/(A*s^3)) = A^2*s^4/(kg*m^2). Vector: length=-2, mass=-1, time=4, current=2. Matches `[-2,-1,4,2,0,0,0]`. Correct.
- Henry: H = Wb/A = V*s/A = kg*m^2/(A^2*s^2). Vector: length=2, mass=1, time=-2, current=-2. Matches `[2,1,-2,-2,0,0,0]`. Correct.

### 2.3 Prefixed Units -- Dimensional Correctness

All prefixed units share the same dimensional vector as their base unit. This is correct for dimensional analysis purposes because a prefix changes only the magnitude (scale factor), not the dimensions. km, cm, mm, um, nm all have vector `[1,0,0,0,0,0,0]` (length^1) -- dimensionally correct.

| Category | Units | Same vector as base? | Verdict |
|----------|-------|---------------------|---------|
| Length prefixes | km, cm, mm, um, nm | Same as m `[1,0,0,...]` | **PASS** |
| Mass prefixes | g, mg | Same as kg `[0,1,0,...]` | **PASS** |
| Time prefixes | ms, us, ns | Same as s `[0,0,1,...]` | **PASS** |
| Time aliases | min, hr | Same as s `[0,0,1,...]` | **PASS** |
| Energy prefixes | kJ, MJ | Same as J `[2,1,-2,...]` | **PASS** |
| Power prefixes | kW, MW | Same as W `[2,1,-3,...]` | **PASS** |
| Force prefixes | kN, MN | Same as N `[1,1,-2,...]` | **PASS** |
| Pressure prefixes | kPa, MPa, GPa | Same as Pa `[-1,1,-2,...]` | **PASS** |

### 2.4 Compound/Derived Registrations

| Registration | Vector | Physically Correct? | Verdict |
|-------------|--------|---------------------|---------|
| m/s (velocity) | `[1,0,-1,0,0,0,0]` | length/time | **PASS** |
| m/s^2 (acceleration) | `[1,0,-2,0,0,0,0]` | length/time^2 | **PASS** |
| km/h (velocity) | `[1,0,-1,0,0,0,0]` | length/time (same dimensions as m/s) | **PASS** |
| kg/m^3 (density) | `[-3,1,0,0,0,0,0]` | mass/length^3 | **PASS** |
| N*s (impulse/momentum) | `[1,1,-1,0,0,0,0]` | force*time = mass*length/time | **PASS** |
| kg*m/s (momentum) | `[1,1,-1,0,0,0,0]` | mass*velocity = mass*length/time | **PASS** |
| lbf*s (impulse) | `[1,1,-1,0,0,0,0]` | Same dimensions as N*s | **PASS** |
| m^2 (area) | `[2,0,0,0,0,0,0]` | length^2 | **PASS** |
| m^3 (volume) | `[3,0,0,0,0,0,0]` | length^3 | **PASS** |
| L (liter) | `[3,0,0,0,0,0,0]` | volume (length^3 dimensionally) | **PASS** |
| dimensionless | all zeros | No dimensions | **PASS** |

### 2.5 Dimensionless Aliases

`rad`, `radian`, `radians`, `sr`, `steradian` are registered as dimensionless. This is physically correct -- radians and steradians are dimensionless SI derived units (they are length/length and area/area respectively). The CLAUDE.md correctly identifies that dimensionless quantities like radians may need "kind" tags to prevent their misuse, but the current flat dimensionless treatment is standard for an MVP.

### 2.6 Unit String Parser

**PASS.** The tokenizer and parser correctly handle:
- Single units: `m`, `kg`, `s`
- Compound units: `kg*m/s^2`
- Multiple divisions: `kg/m/s^2` (parsed left-to-right, which is correct: kg/(m) / (s^2) = kg * m^-1 * s^-2 = Pa)
- Exponents: `m^2`, `s^-1`, `m^(1/2)`
- Dimensionless: `1`, `dimensionless`, `""`

---

## 3. Constraint Builder (`inference/constraint_builder.py`)

### 3.1 Constraint Generation Rules

| Source Pattern | Generated Constraint | Physically Correct? | Verdict |
|---------------|---------------------|---------------------|---------|
| `c = a` | EqualityConstraint(c, a) | [c] = [a] | **PASS** |
| `c = a + b` | AdditionConstraint(c, a, b) | [c] = [a] = [b] | **PASS** |
| `c = a - b` | AdditionConstraint(c, a, b) | [c] = [a] = [b] | **PASS** |
| `c = a * b` | ProductConstraint(c, a, b) | [c] = [a] + [b] | **PASS** |
| `c = a / b` | QuotientConstraint(c, a, b) | [c] = [a] - [b] | **PASS** |
| `c = a ** n` (n constant) | PowerConstraint(c, a, n) | [c] = n * [a] | **PASS** |
| `c = a ** x` (x variable) | KnownUnit(a, dimensionless) + KnownUnit(c, dimensionless) | Base must be dimensionless for non-constant exponent | **PASS** |
| `c += a` | AdditionConstraint(c, c, a) | [c] = [c] = [a] | **PASS** |
| `c *= a` | ProductConstraint(temp, c, a) + Equality(c, temp) | [c_new] = [c_old] + [a] | **PASS** |
| `c /= a` | QuotientConstraint(temp, c, a) + Equality(c, temp) | [c_new] = [c_old] - [a] | **PASS** |
| `return expr` (in func f) | EqualityConstraint(__return_f__, expr) | Return value gets expr's unit | **PASS** |
| `f(x)` calling `def f(a)` | EqualityConstraint(x, a) per param | Arg units = param units | **PASS** |
| Annotation `# unit: m/s` | KnownUnitConstraint(var, m/s) | User-specified unit | **PASS** |

### 3.2 Addition/Subtraction Rule

**PASS.** Both addition and subtraction generate `AdditionConstraint`, which requires all three variables (result, left, right) to have the same dimensions. This is the fundamental dimensional analysis rule: you can only add or subtract quantities with the same dimensions.

### 3.3 Multiplication Rule

**PASS.** Multiplication generates `ProductConstraint` where `[result] = [operand_a] + [operand_b]` (dimension vector addition). This correctly models how units combine in multiplication: m * s = m*s, kg * m/s^2 = kg*m/s^2 = N.

### 3.4 Division Rule

**PASS.** Division generates `QuotientConstraint` where `[result] = [numerator] - [denominator]` (dimension vector subtraction). This correctly models: m / s = m/s, kg*m/s^2 / m = kg/s^2.

### 3.5 Exponentiation Rule

**PASS.** For constant exponents: `[result] = n * [base]`. This correctly models: m^2 = [2,0,0,...], (m/s)^2 = [2,0,-2,...]. For non-constant exponents (variable powers), the requirement that the base must be dimensionless is physically correct -- `2^x` makes physical sense only if 2 is dimensionless.

### 3.6 Modulo Rule

**PASS.** Modulo is treated with AdditionConstraint semantics (all operands and result must have the same dimensions). This is correct: `distance % step_length` only makes sense if both have the same units, and the result has the same units.

### 3.7 Numeric Literals in Expressions

**PASS.** Numeric literals appearing as operands in multiplication or division are marked as dimensionless. This correctly handles the common physics pattern `F = 0.5 * m * v^2` where 0.5 is a dimensionless scaling factor. Literals in standalone assignments (`x = 10.0`) are left unconstrained, allowing annotations to assign them units.

### 3.8 Built-in Function Handling

| Function | Rule | Physically Correct? | Verdict |
|----------|------|---------------------|---------|
| `sqrt(x)` | result = x^(1/2) | **PASS** -- sqrt is exponentiation by 1/2 |
| `abs(x)` | result has same unit as x | **PASS** -- absolute value preserves dimensions |
| `sin/cos/tan(x)` | arg must be dimensionless, result dimensionless | **PASS** -- trig functions take angles (dimensionless) |
| `asin/acos/atan(x)` | arg must be dimensionless, result dimensionless | **PASS** -- inverse trig: dimensionless in, radians (dimensionless) out |
| `exp(x)` | arg must be dimensionless, result dimensionless | **PASS** -- exponential of a dimensioned quantity is meaningless |
| `log/log10/log2(x)` | arg must be dimensionless, result dimensionless | **PASS** -- logarithm of a dimensioned quantity is meaningless |

### 3.9 Comparison Operators

**PASS.** Comparisons require both sides to have the same unit (you can only compare quantities with the same dimensions), and the result is boolean (dimensionless).

### 3.10 Floor Division

**PASS.** Floor division (`//`) is handled identically to true division (`/`) for dimensional analysis. This is correct: `10m // 3s` has the same dimensional result as `10m / 3s` = m/s. The floor operation affects only the magnitude, not the dimensions.

---

## 4. Constraint Propagator (`inference/propagator.py`)

### 4.1 Worklist Algorithm

**PASS.** The algorithm is a standard worklist-based forward/backward constraint propagation:
1. Initialize worklist with all variables having known units.
2. Pop variable from worklist.
3. For each constraint involving that variable, try to infer new units.
4. If a new inference is made, add the inferred variable to the worklist.
5. If an inference conflicts with an existing unit, record a violation.
6. Repeat until worklist is empty or max iterations reached.

This is a well-known algorithm that is correct for this class of problems.

### 4.2 Termination Guarantee

**PASS with caveat.** The algorithm terminates because:
- Each variable's unit is set at most once (once set, it never changes).
- A variable is added to the worklist only when its unit is first set.
- Therefore, each variable enters the worklist at most once.
- Max iterations (10,000) provides an absolute safety bound.

The caveat is that the max_iterations bound is hard-coded. For extremely large codebases, 10,000 might be insufficient, but this is configurable via the constructor parameter.

### 4.3 Conflict Detection Soundness

**PASS.** Conflicts are detected when a constraint would infer a unit for a variable that already has a different unit. The comparison uses `dimensions_equal()`, which checks all 7 exponents exactly (using Fraction arithmetic, no floating-point). This means:
- No false positives from floating-point comparison errors.
- No false positives from the algorithm itself (conflicts are only reported when dimension vectors genuinely differ).

### 4.4 Propagation Directions

Each constraint type supports bi-directional (or tri-directional) propagation. Verified:

| Constraint | Forward | Backward(s) | Verdict |
|-----------|---------|-------------|---------|
| Equality: [a] = [b] | a known -> infer b | b known -> infer a | **PASS** |
| Addition: [r] = [l] = [r'] | Any known -> infer others | (all three directions) | **PASS** |
| Product: [r] = [a] + [b] | a,b known -> r = a+b | r,b known -> a = r-b; r,a known -> b = r-a | **PASS** |
| Quotient: [r] = [n] - [d] | n,d known -> r = n-d | r,d known -> n = r+d; r,n known -> d = n-r | **PASS** |
| Power: [r] = e*[b] | b known -> r = e*b | r known, e!=0 -> b = r/e | **PASS** |

### 4.5 Quotient Backward Propagation -- Detailed Verification

This is the most error-prone direction because the algebra is easy to get backwards. Given `result = numerator / denominator`:
- Forward: `[result] = [num] - [den]` -- correct.
- Backward (infer numerator): `[num] = [result] + [den]` -- the code calls `result_unit.multiply(den_unit)`, which adds dimension vectors. Correct.
- Backward (infer denominator): `[den] = [num] - [result]` -- the code calls `num_unit.divide(result_unit)`, which subtracts result from numerator. Correct.

### 4.6 Power Backward Propagation

Given `result = base^exponent`:
- Forward: `[result] = e * [base]` -- correct.
- Backward: `[base] = [result] / e` -- the code computes `inv_exp = 1/e` then `result.power(inv_exp)`. Since `power()` multiplies all exponents by the argument: `[result] * (1/e) = (e * [base]) * (1/e) = [base]`. Correct.
- Guard: only when `exponent != 0` (division by zero prevention). Correct.

### 4.7 Violation Deduplication

**PASS.** Violations are deduplicated by (file, line, column, expected_unit_vector, actual_unit_vector). This prevents the same physical error from being reported multiple times due to constraints being evaluated from different directions.

### 4.8 Violation Message Quality

**PASS.** Messages use physics language:
- Addition mismatch: "cannot combine [m/s] with [m/s^2]"
- Assignment mismatch: "expected [kg*m/s^2], got [kg*m/s]"
- These speak the language of the physicist/engineer, not the compiler.

---

## 5. Conflict Resolver (`inference/conflict_resolver.py`)

### 5.1 Named Unit Enrichment

**PASS.** The `enrich_violation()` function adds named unit equivalents (e.g., "N = kg*m/s^2") to violation messages when a named unit matches the dimension vector. This aids comprehension.

### 5.2 Source Line Context

**PASS.** Violations can include the actual source code line, helping the user locate the error.

---

## 6. Python Parser (`parsers/python_parser/parser.py`)

### 6.1 Operator Mapping

**PASS.** All Python arithmetic operators map correctly to IR binary operators:
- `+` -> ADD, `-` -> SUB, `*` -> MUL, `/` -> DIV, `**` -> POW, `//` -> FLOOR_DIV, `%` -> MOD

### 6.2 Unary Operator Handling

**PASS.** Unary `-` and `+` are correctly handled as unit-preserving operations. `-velocity` has the same unit as `velocity`.

### 6.3 Annotation Extraction

**PASS.** The regex `#\s*unit:\s*(.+?)$` correctly extracts unit annotations from inline comments and standalone comments.

### 6.4 Function Call Resolution

**PASS.** Qualified function names (e.g., `math.sqrt`) are correctly reconstructed by walking the AST Attribute chain.

### 6.5 Subscript Handling

**PASS.** `array[i]` is treated as having the same unit as `array`. This is the correct default for physics code where arrays store homogeneous quantities.

---

## 7. Benchmark Test Verification

### 7.1 Mars Climate Orbiter (Benchmark 1.1)

**PASS.** The test correctly models the MCO scenario: impulse (`kg*m/s`) vs force (`N = kg*m/s^2`) are recognized as dimensionally different. Adding them produces a violation. The dimension vectors:
- `kg*m/s` = `[1,1,-1,0,0,0,0]` (momentum/impulse)
- `N` = `[1,1,-2,0,0,0,0]` (force)
These differ in the time exponent (-1 vs -2), so the mismatch is correctly detected.

**Note:** The real MCO error was between lbf*s and N*s (both are impulse, but in different unit systems with a factor-of-~4.45 conversion). The test simplifies this to an impulse-vs-force mismatch, which is a valid dimensional analysis error to detect. The comment in the test correctly explains this simplification.

### 7.2 Velocity + Acceleration (Benchmark 1.2)

**PASS.** `m/s` + `m/s^2` is correctly flagged. Vectors `[1,0,-1,...]` and `[1,0,-2,...]` differ in time exponent.

### 7.3 Force Computation Error (Benchmark 1.3)

**PASS.** `mass * velocity` = momentum (`[1,1,-1,...]`), which differs from force/Newton (`[1,1,-2,...]`). Adding momentum to drag (in Newtons) is correctly flagged.

### 7.4 Energy Conservation (Benchmark 1.4)

**PASS.** `mass * velocity` (wrong kinetic energy) gives momentum `[1,1,-1,...]`, while `mass * gravity * height` gives Joules `[2,1,-2,...]`. Adding them is correctly flagged.

### 7.5 Correct Physics (Benchmark 1.5)

**PASS.** `distance/time` = m/s (velocity), `velocity/time` = m/s^2 (acceleration). Zero violations -- correct.

### 7.6 Function Call Propagation (Benchmark 1.6)

**PASS.** Units correctly propagate through `compute_velocity(distance, time)` and the result is used in `momentum = mass * v`.

### 7.7 Exponentiation and Square Root (Benchmark 1.7)

**PASS.** `length^2` = area (m^2), `area * length` = volume (m^3), `area^0.5` = length (m). `area + length` correctly flagged as mismatch.

### 7.8 Dimensionless Result (Benchmark 1.8)

**PASS.** `velocity / velocity` = dimensionless. No violations.

### 7.9 Chain Propagation (Benchmark 1.9)

**PASS.** Units propagate through `x -> y -> z -> w` chain. Multiplication by a constant preserves units.

### 7.10 Multi-Operation Expression (Benchmark 1.10)

**PASS.** `0.5 * mass * velocity^2` = Joules (kg*m^2/s^2). `mass * g * height` = Joules. Their sum is valid. `kinetic + mass` is correctly flagged.

---

## 8. Issues Found

### ISSUE 1: `to_unit_string()` denominator rendering ambiguity (LOW severity)

**File:** `core/unit_algebra.py`, lines 254-256

The rendering logic joins denominator parts with `/`:
```python
return "*".join(numerator_parts) + "/" + "/".join(denominator_parts)
```

For a unit like `kg/(m*s^2)` (Pascal), this renders as `kg/m/s^2`. While this is parseable by the unit string parser (which processes left-to-right, making `kg / m / s^2` = `kg * m^-1 * s^-2`), it is **potentially ambiguous** to human readers. A physicist might read `kg/m/s^2` as `kg / (m/s^2)` = `kg * s^2 / m`, which has a completely different meaning.

**Recommendation:** Use parentheses in the denominator when there are multiple terms: `kg/(m*s^2)`.

**Impact on correctness:** LOW -- this is a display issue only. The internal vector representation and all calculations are correct. However, since this tool generates error messages for physicists, an ambiguous unit rendering in an error message could cause confusion.

### ISSUE 2: MCO benchmark does not test the actual lbf*s vs N*s scenario (INFORMATIONAL)

**File:** `tests/integration_tests/test_benchmarks.py`, TestBenchmark1_1

The Mars Climate Orbiter test uses `kg*m/s` (impulse) vs `N` (force) as a mismatch. The real MCO error was between `lbf*s` and `N*s` -- both are impulse, but `lbf*s` and `N*s` have the **same dimensions** (`[1,1,-1,0,0,0,0]`). The real MCO error was a **unit system conversion** error (Imperial vs SI), not a **dimensional** error.

The registry correctly registers `lbf*s` with vector `[1,1,-1,0,0,0,0]` (same as `N*s`), meaning the tool would **not** detect the real MCO error because it only checks dimensions, not magnitude/scale.

**Impact:** This is a known limitation documented in CLAUDE.md (the tool does dimensional analysis, not unit system tracking for MVP). The benchmark test is valid for what it claims to test (impulse vs force mismatch), but the test description could be clearer that it is a **simplified** MCO scenario testing dimensional mismatch, not the actual unit-system conversion error.

### ISSUE 3: Augmented assignment `*=` changes variable dimensions in-place (MEDIUM severity)

**File:** `inference/constraint_builder.py`, lines 222-237

For `target *= expr`, the code generates:
1. `ProductConstraint(temp, target, expr)` -- temp = target * expr
2. `EqualityConstraint(target, temp)` -- target = temp

This means after `velocity *= time`, the variable `velocity` would be assigned the dimensions of `velocity * time = distance`. But the propagator sets each variable's unit only once. If `velocity` already had a known unit `[m/s]`, the EqualityConstraint would try to set it to `[m]` (distance), causing a **correct conflict detection**.

However, if `velocity` does NOT yet have a known unit when `*=` is processed, the propagator would set velocity's unit to whatever `temp` resolves to, which could be wrong if velocity gets its unit from a later constraint. This is a general limitation of single-assignment unit inference, not a bug per se, but it means augmented assignments on variables that are also annotated could produce unexpected propagation behavior.

**Impact:** MEDIUM -- could lead to confusing error messages in specific augmented assignment patterns. Does not cause incorrect pass (false negative) because any dimensional inconsistency will still be detected.

### ISSUE 4: Literal handling in addition could mask errors (LOW severity)

**File:** `inference/constraint_builder.py`, lines 296-306

In multiplication/division, literals are explicitly marked as dimensionless. But in addition (`c = a + b`), if `b` is a literal like `10`, no special handling occurs. The AdditionConstraint will propagate `a`'s unit to `b` (the literal), making `b` appear to have that unit.

This is actually **correct** behavior for physics code like `total_distance = distance + 10` where 10 implicitly has the same unit as `distance`. However, it means the tool will never flag `distance + 10` as a potential error, even though adding a "bare number" to a dimensioned quantity is a common source of bugs (the 10 might be in different units).

**Impact:** LOW for MVP. This is a design choice, not a bug. Flagging bare-number additions would require a "strict mode" feature.

### ISSUE 5: No scale-factor tracking limits unit-system detection (KNOWN LIMITATION, INFORMATIONAL)

The entire system tracks only dimensional exponents, not scale factors. This means:
- `km` and `m` have the same vector -- the tool cannot detect `distance_km + distance_m` as an error.
- `lbf*s` and `N*s` have the same vector -- the real MCO error is undetectable.
- `deg` and `rad` would need kind tags to distinguish them.

This is explicitly documented as a design decision in CLAUDE.md and PLANNING.md. The MVP deliberately omits scale tracking. This is noted here for completeness.

### ISSUE 6: `_to_fraction` float conversion with `limit_denominator` could silently corrupt unusual exponents (VERY LOW severity)

**File:** `core/unit_algebra.py`, line 45

```python
return Fraction(val).limit_denominator(1000)
```

For typical physics exponents (integers, 1/2, 1/3), this is fine. But `Fraction(0.3)` yields `Fraction(5404319552844595, 18014398509481984)`, and `limit_denominator(1000)` rounds to `Fraction(3, 10)` -- which is correct. However, if someone passed a float like `0.142857` (meaning 1/7), `limit_denominator(1000)` would yield `Fraction(1, 7)` -- correct. The function is safe for all physically meaningful exponents.

**Impact:** VERY LOW. No real physics scenario uses dimension exponents that would be corrupted.

---

## 9. Cross-Verification: Dimensional Consistency Spot Checks

I performed independent dimensional calculations for key physics formulas tested in the benchmark suite:

### Kinetic Energy: KE = 0.5 * m * v^2
- 0.5: dimensionless
- m: [0,1,0,0,0,0,0] (kg)
- v^2: [1,0,-1,0,0,0,0]^2 = [2,0,-2,0,0,0,0] (m^2/s^2)
- m * v^2: [0,1,0,...] + [2,0,-2,...] = [2,1,-2,0,0,0,0] = kg*m^2/s^2 = J
- **Matches test expectation. CORRECT.**

### Potential Energy: PE = m * g * h
- m: [0,1,0,0,0,0,0] (kg)
- g: [1,0,-2,0,0,0,0] (m/s^2)
- h: [1,0,0,0,0,0,0] (m)
- m * g * h: [0,1,0,...] + [1,0,-2,...] + [1,0,0,...] = [2,1,-2,0,0,0,0] = J
- **Matches test expectation. CORRECT.**

### Momentum: p = m * v
- m: [0,1,0,0,0,0,0] (kg)
- v: [1,0,-1,0,0,0,0] (m/s)
- m * v: [0,1,0,...] + [1,0,-1,...] = [1,1,-1,0,0,0,0] = kg*m/s
- **Matches test expectation. CORRECT.**

### Force: F = m * a
- m: [0,1,0,0,0,0,0] (kg)
- a: [1,0,-2,0,0,0,0] (m/s^2)
- m * a: [0,1,0,...] + [1,0,-2,...] = [1,1,-2,0,0,0,0] = kg*m/s^2 = N
- **Matches test expectation. CORRECT.**

---

## 10. Summary Scorecard

| Component | Verdict | Notes |
|-----------|---------|-------|
| SI base dimension ordering | PASS | Correct 7D vector, consistent throughout |
| Fraction arithmetic | PASS | Exact rational, no float comparison issues |
| Multiply operation | PASS | Vector addition, verified |
| Divide operation | PASS | Vector subtraction, verified |
| Power operation | PASS | Scalar multiplication, verified |
| Equality comparison | PASS | Exact fraction comparison |
| Newton (N) definition | PASS | [1,1,-2,0,0,0,0] = kg*m/s^2 |
| Joule (J) definition | PASS | [2,1,-2,0,0,0,0] = kg*m^2/s^2 |
| Watt (W) definition | PASS | [2,1,-3,0,0,0,0] = kg*m^2/s^3 |
| Pascal (Pa) definition | PASS | [-1,1,-2,0,0,0,0] = kg/(m*s^2) |
| Hertz (Hz) definition | PASS | [0,0,-1,0,0,0,0] = 1/s |
| Coulomb (C) definition | PASS | [0,0,1,1,0,0,0] = A*s |
| Volt (V) definition | PASS | [2,1,-3,-1,0,0,0] = kg*m^2/(A*s^3) |
| Ohm definition | PASS | [2,1,-3,-2,0,0,0] = kg*m^2/(A^2*s^3) |
| Farad (F) definition | PASS | [-2,-1,4,2,0,0,0] = A^2*s^4/(kg*m^2) |
| Weber (Wb) definition | PASS | [2,1,-2,-1,0,0,0] = kg*m^2/(A*s^2) |
| Tesla (T) definition | PASS | [0,1,-2,-1,0,0,0] = kg/(A*s^2) |
| Henry (H) definition | PASS | [2,1,-2,-2,0,0,0] = kg*m^2/(A^2*s^2) |
| All prefixed units | PASS | Same dimensions as base units |
| Addition constraint rule | PASS | Requires same dimensions |
| Multiplication constraint rule | PASS | Dimension vectors add |
| Division constraint rule | PASS | Dimension vectors subtract |
| Power constraint rule | PASS | Dimension vector scales |
| Assignment propagation | PASS | Equality constraint |
| Worklist algorithm correctness | PASS | Terminates, no false positives |
| Backward propagation | PASS | All constraint types support it |
| sqrt() handling | PASS | Exponent 1/2 |
| Trig function handling | PASS | Dimensionless in/out |
| exp/log handling | PASS | Dimensionless in/out |
| MCO benchmark | PASS | Detects impulse vs force mismatch |
| Velocity+acceleration benchmark | PASS | Detects m/s vs m/s^2 |
| Energy conservation benchmark | PASS | Correct KE and PE are Joules |
| Unit string rendering | PASS (with Issue 1) | Denominator format could be ambiguous |

**Final assessment: The physics and dimensional analysis in this codebase is correct. No unit definition errors. No constraint rule errors. No false positives from the algorithm. The 6 issues identified are low-to-medium severity and do not compromise the core correctness of the tool.**
