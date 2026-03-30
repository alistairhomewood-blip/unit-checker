# Physics Adversarial Audit Report

**Auditor Role:** Hostile physics auditor -- assume every formula is wrong until proven otherwise.

**Date:** 2026-03-29

**Scope:** Full codebase read of all physics-relevant source, test, and fixture files. Adversarial testing of unit algebra, unit registry, constraint builder, propagator, Python parser, C++ parser, and all integration benchmarks.

**Test Suite Baseline:** 177/177 tests passing before audit.

---

## CRITICAL Findings

### CRIT-1: Mars Climate Orbiter benchmark passes for the WRONG reason

**Severity:** CRITICAL

**Location:** `tests/unit_tests/test_cpp_parser.py` (TestIntegrationMarsClimateOrbiter, line 736), `tests/fixtures/cpp/mars_climate_orbiter.cpp`, `src/unit_checker/core/unit_registry.py` (line 263)

**Description:** The MCO test (5.22) asserts that adding `lbf*s` to `N*s` produces zero violations because "both are momentum (kg*m/s) so dimensionally consistent." This claim is factually wrong about what the test actually exercises. The annotation `// unit: lbf*s` **silently fails to parse** because `lbf` is not registered as a standalone unit. Only the compound key `lbf*s` exists in the registry's lookup table (line 263), but `parse_unit_string("lbf*s")` tokenizes it as `['lbf', '*', 's']` and fails on `lbf` (unknown unit). The constraint builder catches the ValueError and silently skips the annotation (line 117: `except ValueError: continue`). This means `sm_forces_impulse` is **completely unconstrained**, and the addition trivially passes with no violation -- not because the dimensions match, but because one operand has no unit at all.

**Reproduction:**

```python
from unit_checker.core.unit_registry import default_registry

# This succeeds (direct dict lookup):
print(default_registry.lookup("lbf*s"))  # UnitVector(length=1, mass=1, time=-1)

# This FAILS (tokenizes and looks up 'lbf' which does not exist):
default_registry.parse_unit_string("lbf*s")  # ValueError: Unknown unit: 'lbf'
```

**Impact:** The MCO benchmark test is vacuous -- it does not test what it claims to test. The test passes by accident due to a silent annotation parse failure.

**Fix Required:**
1. Register `lbf` as a standalone unit: `reg.register("lbf", UnitVector.from_list([1, 1, -2, 0, 0, 0, 0]))` (pound-force has dimensions of force, same as Newton).
2. Update the test comment to accurately describe the limitation.
3. Add a test that verifies the `lbf*s` annotation actually resolves.

---

### CRIT-2: Unit string parser cannot round-trip its own output

**Severity:** CRITICAL

**Location:** `src/unit_checker/core/unit_algebra.py` (to_unit_string, lines 228-266), `src/unit_checker/core/unit_registry.py` (parse_unit_string / _tokenize_unit_string)

**Description:** The `to_unit_string()` method produces parenthesized output for multiple-denominator units (e.g., `kg/(m*s^2)`, `1/(m*s)`, `m^2*kg/(s^3*A)`). But `parse_unit_string()` cannot parse parenthesized unit strings because the tokenizer does not handle `(` or `)` characters. The token `(m` is treated as a unit name and fails lookup.

**Reproduction:**

```python
from unit_checker.core.unit_algebra import UnitVector
from unit_checker.core.unit_registry import default_registry

pa = UnitVector.from_list([-1, 1, -2, 0, 0, 0, 0])
rendered = pa.to_unit_string()         # "kg/(m*s^2)"
default_registry.parse_unit_string(rendered)  # ValueError: Unknown unit: '(m'
```

**Failing round-trip cases:**
- `kg/(m*s^2)` (Pascal) -- FAILS
- `m^2*kg/(s^3*A)` (Volt) -- FAILS
- `1/(m*s)` -- FAILS

**Non-failing cases (single denominator, no parens produced):**
- `m/s` -- OK
- `m^2/s` -- OK
- `1/s` -- OK
- `m*kg/s^2` -- OK

**Impact:** Any user annotation written in the parenthesized form that `to_unit_string()` produces will silently fail. Error messages that display the unit string in parenthesized form cannot be copied back as annotations. This breaks the user workflow of "see error message, copy unit, add annotation."

**Fix Required:** Either (a) teach `_tokenize_unit_string` to handle parentheses, or (b) change `to_unit_string()` to never produce parenthesized output (use `kg/m/s^2` form instead, which parses correctly via left-to-right evaluation).

---

### CRIT-3: Conflicting annotations on the same variable are silently ignored

**Severity:** CRITICAL

**Location:** `src/unit_checker/inference/constraint_builder.py` (lines 126-134), `src/unit_checker/inference/propagator.py` (_eval_known, lines 212-219)

**Description:** When a variable has two conflicting unit annotations (e.g., first annotated as `m/s`, then re-annotated as `m/s^2`), the system silently picks the last one with no warning or violation. Two bugs compound:

1. In `ConstraintBuilder._process_annotations()`, `self._var_units[qualified_name] = unit` overwrites the previous entry. The last annotation wins in the dict.
2. In `ConstraintPropagator._eval_known()`, the method returns `[]` when the variable is already in `known_units`, so the second `KnownUnitConstraint` never triggers a conflict check.

**Reproduction:**

```python
source = """
x = 5.0   # unit: m/s
x = 10.0  # unit: m/s^2
"""
result = analyze(source)
assert len(result.violations) == 0  # BUG: should be >= 1
# x silently gets m/s^2 (the last annotation), m/s is discarded
```

**Impact:** Users who accidentally give conflicting annotations to the same variable get no warning. This is especially dangerous in long files where the same variable name is used in different contexts, or when annotations are copy-pasted with errors.

**Fix Required:** In `_eval_known`, when the variable IS already in `known_units`, check if the existing unit matches. If not, return an inference that will trigger a conflict. Alternatively, detect duplicates in `_process_annotations`.

---

## HIGH Findings

### HIGH-1: C++ std:: math functions not recognized by constraint builder

**Severity:** HIGH

**Location:** `src/unit_checker/inference/constraint_builder.py` (_handle_builtin_call, lines 437-523)

**Description:** The constraint builder recognizes `sqrt`, `math.sqrt`, `np.sqrt`, `numpy.sqrt` for the sqrt builtin, and similar patterns for trig, exp/log, and abs functions. However, the C++ standard library equivalents using the `std::` namespace prefix are completely unrecognized:

**Missing functions:**
- `std::sqrt`, `std::cbrt`, `sqrtf`, `sqrtl`
- `std::sin`, `std::cos`, `std::tan`, `sinf`, `cosf`, `tanf`
- `std::asin`, `std::acos`, `std::atan`, `std::atan2`
- `std::exp`, `std::log`, `std::log10`, `std::log2`
- `std::abs`, `std::fabs`, `fabsf`

**Reproduction:**

```cpp
double area = 9.0; // unit: m^2
double side = std::sqrt(area);  // side should be m, but is unconstrained
```

Result: `side` gets no inferred unit (None), instead of the correct `m`.

**Impact:** Any C++ code using standard library math functions (which is virtually all scientific C++ code) will lose unit inference at every `std::` math call boundary. This makes the C++ parser significantly less useful than the Python parser for real-world code.

**Fix Required:** Add `std::sqrt`, `std::sin`, `std::cos`, etc. to the appropriate name sets in `_handle_builtin_call`. Also add C-standard variants (`sqrtf`, `sinf`, `fabsf`, etc.).

---

### HIGH-2: C++ annotation parser captures trailing comments as part of unit string

**Severity:** HIGH

**Location:** `src/unit_checker/parsers/cpp_parser/parser.py` (line 60: `_SINGLE_LINE_UNIT_RE`)

**Description:** The regex `r"//\s*unit:\s*(.+?)$"` uses `(.+?)$` which, while non-greedy, still matches to end-of-string since `$` is the only thing stopping it. For a C++ comment like `// unit: m/s // velocity in meters per second`, the captured group is `m/s // velocity in meters per second`, which then fails to parse as a unit string (silently dropped).

**Reproduction:**

```cpp
double velocity = 10.0; // unit: m/s // velocity in meters per second
```

Annotation captured: `"m/s // velocity in meters per second"` -- FAILS to parse.

**Impact:** Any C++ code with additional comments after the unit annotation will have the annotation silently dropped. This is a common coding style.

**Fix Required:** Modify the regex to stop at whitespace-then-`//` or use a more precise pattern:
```python
_SINGLE_LINE_UNIT_RE = re.compile(r"//\s*unit:\s*([^\s/]+(?:/[^\s/]+)*)")
```
Or more simply: capture until the next `//` or end of string.

---

### HIGH-3: Python annotation parser has the same trailing-comment issue

**Severity:** HIGH

**Location:** `src/unit_checker/parsers/python_parser/parser.py` (line 56: `_UNIT_COMMENT_RE`)

**Description:** The regex `r"#\s*unit:\s*(.+?)$"` with `re.MULTILINE` has the same problem as the C++ parser. A comment like `# unit: m/s # velocity` captures `m/s # velocity`.

**Reproduction:**

```python
velocity = 10.0  # unit: m/s # velocity in meters per second
```

Annotation captured: `"m/s # velocity in meters per second"` -- FAILS to parse.

**Fix Required:** Same as HIGH-2 -- modify regex to stop at `#` or trailing non-unit content.

---

## MEDIUM Findings

### MED-1: Annotation parse failures are completely silent

**Severity:** MEDIUM

**Location:** `src/unit_checker/inference/constraint_builder.py` (lines 114-118)

**Description:** When `registry.parse_unit_string(ann.unit_string)` raises `ValueError`, the constraint builder silently `continue`s. No warning is emitted, no diagnostic is recorded. The user has no way to know their annotation was not understood.

**Reproduction:** Any invalid unit string in an annotation (typo, unsupported unit, trailing garbage) is silently ignored.

**Impact:** This is the root cause enabling CRIT-1 (lbf*s silently dropped) and HIGH-2/HIGH-3 (trailing comments silently dropped). Users write annotations that they believe are active but are actually dead.

**Fix Required:** At minimum, record a warning-level violation for unparseable annotations. Ideally, emit a diagnostic that says "Could not parse unit annotation 'X' on line Y."

---

### MED-2: `to_unit_string()` does not preserve SI symbol ordering convention

**Severity:** MEDIUM (cosmetic, but affects readability)

**Location:** `src/unit_checker/core/unit_algebra.py` (to_unit_string, line 241)

**Description:** The output follows the order of `DIMENSION_SYMBOLS = ("m", "kg", "s", "A", "K", "mol", "cd")`. For force, this produces `m*kg/s^2` instead of the conventional `kg*m/s^2`. While dimensionally correct, this is unconventional and may confuse physicists who expect the mass term first for mechanical units.

**Impact:** Cosmetic. Error messages display `m*kg/s^2` instead of the more conventional `kg*m/s^2`.

---

### MED-3: Ternary expressions only check the true branch for unit inference

**Severity:** MEDIUM

**Location:** `src/unit_checker/parsers/python_parser/parser.py` (line 411), `src/unit_checker/parsers/cpp_parser/parser.py` (lines 635-637)

**Description:** For `x if cond else y` (Python) or `cond ? x : y` (C++), only the true branch is analyzed. If the branches have different units, no violation is reported.

**Reproduction:**

```python
distance = 10.0  # unit: m
time = 5.0       # unit: s
result = distance if True else time  # Should flag: m vs s
```

No violation is raised because only `distance` (the true branch) is analyzed.

**Impact:** Unit errors hidden in ternary false branches will be missed.

**Fix Required:** Generate an AdditionConstraint (equality) between both branches.

---

## LOW Findings

### LOW-1: Macro-defined constants in C++ appear as variable references

**Severity:** LOW

**Location:** `src/unit_checker/parsers/cpp_parser/parser.py`

**Description:** Tree-sitter parses pre-processed source, so `#define SPEED 10.0` followed by `double v = SPEED;` produces a variable reference to `SPEED` rather than a literal. Since `SPEED` has no annotation, `v` becomes unconstrained. This is expected behavior (documented), but worth noting.

**Impact:** C++ code that uses macros for physics constants will lose unit information at macro boundaries. Users must annotate the variable that receives the macro value.

---

### LOW-2: Lambda expressions in C++ are not analyzed

**Severity:** LOW

**Location:** `src/unit_checker/parsers/cpp_parser/parser.py`

**Description:** `auto f = [](double x) { return x * 2.0; };` is parsed as an assignment to `f` with the lambda as the expression, but the lambda body is not analyzed as a function. No `IRFunction` is created.

**Impact:** Unit constraints inside lambda bodies are lost. This is documented as out-of-scope for MVP.

---

## VERIFIED Items (Survived Adversarial Scrutiny)

### VERIFIED: SI base unit dimensions

All 7 SI base units (m, kg, s, A, K, mol, cd) are correctly represented as orthogonal unit vectors. Verified by inspection against BIPM definitions.

### VERIFIED: All 12 SI derived units

Newton, Joule, Watt, Pascal, Hertz, Coulomb, Volt, Ohm, Farad, Weber, Tesla, Henry -- all verified against their SI definitions (e.g., N = kg*m/s^2 = [1,1,-2,0,0,0,0]). Zero errors found.

### VERIFIED: Unit algebra (multiply, divide, power)

- Velocity * time = distance: `[1,0,-1] + [0,0,1] = [1,0,0]` -- CORRECT
- Mass * acceleration = force: `[0,1,0] + [1,0,-2] = [1,1,-2]` -- CORRECT
- Length^2 = area: `2 * [1,0,0] = [2,0,0]` -- CORRECT
- sqrt(area) = length: `0.5 * [2,0,0] = [1,0,0]` -- CORRECT
- y^0 = dimensionless: verified by property-based test (200 random cases)
- (U * V) / V = U: verified by property-based test (200 random cases)
- Fraction arithmetic is exact (no floating-point comparison issues)

### VERIFIED: Denominator parenthesization in `to_unit_string()`

The parenthesization logic is **correct for all cases**:
- Multiple denominator parts: `kg/(m*s^2)` -- parenthesized (CORRECT)
- Single denominator: `m/s` -- no parentheses (CORRECT)
- Single denominator with exponent: `m*kg/s^2` -- no parentheses (CORRECT)
- Numerator-free with multiple denominator: `1/(m*s)` -- parenthesized (CORRECT)
- Numerator-free single: `1/s` -- no parentheses (CORRECT)
- Dimensionless: `dimensionless` (CORRECT)

### VERIFIED: Zero-exponent handling

`x = y ** 0` correctly produces dimensionless regardless of y's unit. Verified through both direct test and property-based testing.

### VERIFIED: Negative exponent handling

`x = y ** (-2)` with `y: m` correctly produces `1/m^2`. Verified.

### VERIFIED: Fractional exponent handling

`x = y ** 0.5` with `y: m^2` correctly produces `m`. The `Fraction(0.333...).limit_denominator(1000)` correctly approximates 1/3, so cube roots of perfect cubes resolve exactly.

### VERIFIED: Circular constraint handling

The propagator terminates correctly for circular constraints (`a = b * c; b = a / c`). With annotations, units propagate correctly around the cycle. Without annotations, variables remain in the unknown set. No infinite loops -- the worklist drains because already-known variables do not re-enqueue.

### VERIFIED: Forward and backward propagation

Forward propagation (annotation -> assignment chain) and backward propagation (known result -> infer operands) both work correctly. Verified through 25-step chains and multi-operation expressions (kinetic + potential energy).

### VERIFIED: Addition/subtraction dimensional checking

Adding `m/s` to `m/s^2` is correctly flagged. Adding `m` to `m` produces no violation. Modulo correctly requires same dimensions.

### VERIFIED: Cross-language parity (Python vs C++)

Equivalent Python and C++ code (velocity, energy conservation, addition violation) produce identical analysis results. Three parity tests all pass.

### VERIFIED: C++ pointer and reference handling

`const double& v = velocity` correctly inherits velocity's unit. `double* ptr = &velocity; double v = *ptr` correctly propagates units through pointer dereference.

### VERIFIED: Non-constant exponent handling

When the exponent is not a compile-time constant, the constraint builder correctly requires the base to be dimensionless and marks the result as dimensionless.

---

## Task 2: Mars Climate Orbiter Benchmark Assessment

### What the real MCO error was

Lockheed Martin's SM_FORCES software output thrust data in **pound-force-seconds** (lbf*s). NASA's trajectory software expected **newton-seconds** (N*s). Both lbf*s and N*s have identical SI dimensions: `[mass * length / time] = [1, 1, -1, 0, 0, 0, 0]`. The conversion factor is 1 lbf*s = 4.448 N*s.

### Can the tool detect the real MCO error?

**No.** The tool performs dimensional analysis, not unit-system analysis. Since lbf*s and N*s have the same dimensions, they are indistinguishable in the 7-dimensional SI vector space. Detecting this error would require a "unit system" or "scale" concept that goes beyond pure dimensional analysis.

### What does Benchmark 1.1 actually test?

Benchmark 1.1 (in `test_benchmarks.py`) tests **impulse (kg*m/s) + force (N = kg*m/s^2)**, which IS a valid dimensional mismatch (time exponent -1 vs -2). This is a fair dimensional analysis test, but it is NOT the real MCO error. The test description correctly calls it a "simplified" MCO test.

### What does the C++ test (5.22) actually test?

Test 5.22 uses `lbf*s` and `N*s` annotations and claims both map to momentum. **But the test passes only because the `lbf*s` annotation silently fails** (see CRIT-1). The test is vacuous and should be rewritten.

### Is there any way to detect the real MCO error with the current architecture?

Not with pure dimensional analysis. However, the `kind` tag mechanism on `UnitVector` (field `kind: Optional[str]`, lines 67, 102-110) was designed for exactly this purpose. If lbf*s were tagged with `kind="imperial"` and N*s with `kind="SI"`, the `compatible_with()` method would reject the addition. This is not yet implemented in the constraint builder.

---

## Task 3: Five Unit Errors the Tool Would Miss

### 1. Unit system mixing (km + m)

```python
distance_km = 5.0      # unit: km
distance_m = 3000.0    # unit: m
total = distance_km + distance_m  # Wrong! 5 + 3000 = 3005, but 5km + 3000m = 8000m
```

**Result:** 0 violations. Both `km` and `m` have dimension `[1,0,0,0,0,0,0]` (length). The tool cannot distinguish scales. **By design** -- the registry stores dimensions, not scale factors.

### 2. Implicit conversion with wrong annotation

```python
speed_mph = 60.0   # unit: m/s  (BUG: actually mph, not m/s!)
speed_mps = speed_mph * 0.44704
```

**Result:** 0 violations. The tool trusts the user annotation. `0.44704` is treated as dimensionless. The tool infers `speed_mps = m/s * dimensionless = m/s`. Everything looks consistent despite the semantic error.

### 3. Trigonometric argument (degrees vs radians)

```python
angle_degrees = 45.0  # unit: dimensionless
result = math.sin(angle_degrees)
```

**Result:** 0 violations. Degrees are dimensionless, and `sin()` expects dimensionless. The tool correctly applies the constraint but cannot distinguish radians from degrees since both are dimensionless. Even with `# unit: rad`, this passes because `rad` is an alias for dimensionless.

### 4. Off-by-one power (E = mv instead of mv^2)

```python
m = 5.0  # unit: kg
v = 10.0  # unit: m/s
energy = m * v  # BUG: should be 0.5 * m * v ** 2
```

**Result:** 0 violations (without annotation on `energy`). The tool infers `energy = kg*m/s` (momentum), which is self-consistent. It has no expected type for `energy` to conflict with. **With `# unit: J` annotation**, the tool correctly detects the violation (1 violation found).

### 5. Constant misidentification (imperial g with metric h)

```python
m = 10.0    # unit: kg
g = 32.2    # unit: m/s^2  (BUG: 32.2 is ft/s^2, not m/s^2!)
h = 5.0     # unit: m
F = m * g * h
```

**Result:** 0 violations. The tool trusts the annotation `m/s^2` on `g`. It has no way to know that 32.2 is the imperial value. A "known constants database" could flag this (32.2 is a well-known constant for g in ft/s^2), but this is out of scope.

---

## Task 4: Denominator Parenthesization Verification

**Status: VERIFIED CORRECT** (but with the round-trip bug noted in CRIT-2)

The rendering logic correctly applies parentheses to multi-part denominators and omits them for single-part denominators. All test cases pass:

| Input dims | Rendered | Parens? | Correct? |
|-----------|----------|---------|----------|
| [-1,1,-2,0,0,0,0] (Pa) | `kg/(m*s^2)` | Yes | Yes |
| [1,0,-1,0,0,0,0] (m/s) | `m/s` | No | Yes |
| [2,0,-1,0,0,0,0] (m^2/s) | `m^2/s` | No | Yes |
| [0,0,-1,0,0,0,0] (Hz) | `1/s` | No | Yes |
| [-1,0,-1,0,0,0,0] | `1/(m*s)` | Yes | Yes |
| [1,1,-2,0,0,0,0] (N) | `m*kg/s^2` | No | Yes |
| [2,1,-3,-1,0,0,0] (V) | `m^2*kg/(s^3*A)` | Yes | Yes |

However, the parenthesized output cannot be parsed back (CRIT-2).

---

## Task 5: C++ Parser Adversarial Results

| Test | Input | Result | Severity |
|------|-------|--------|----------|
| Trailing `//` comment | `// unit: m/s // comment` | Unit string corrupted | HIGH-2 |
| Multiple `/* */` on same line | `/* unit: kg */ /* unit: m */` | Only first captured | OK (acceptable) |
| Template expressions | `std::vector<double>` | Parsed, no crash | OK |
| Lambda expressions | `auto f = [](double x){...}` | Parsed, body not analyzed | LOW-2 |
| auto with function call | `auto x = compute_velocity()` | IRCallExpr produced | OK |
| const double& | `const double& v = velocity` | v inherits unit | VERIFIED |
| Pointer dereference | `double* ptr = &x; double v = *ptr` | v inherits unit | VERIFIED |
| #define macro | `#define SPEED 10.0` | SPEED as variable ref | LOW-1 |
| std::sqrt | `std::sqrt(area)` | NOT recognized as sqrt | HIGH-1 |
| Operator overloading | `operator+` | Parsed, not analyzed | OK (expected) |
| Nested templates | `std::map<string, vector<double>>` | Parsed, no crash | OK |
| Ternary expression | `cond ? a : b` | Only true branch | MED-3 |
| C-style cast | `(int)x` | Parsed, no crash | OK |
| sizeof | `sizeof(double)` | Treated as literal | OK |
| For loop with accumulator | `for(...) total += dx;` | Correctly analyzed | VERIFIED |

---

## Task 6: Constraint Propagation Edge Cases

| Test | Behavior | Verdict |
|------|----------|---------|
| Circular: `a = b*c; b = a/c` | Terminates, propagates correctly with seed | VERIFIED |
| Conflicting annotations | Silently takes last, no violation | **CRIT-3** |
| `y ** 0` | Dimensionless (correct) | VERIFIED |
| `y ** (-2)` | `1/m^2` (correct) | VERIFIED |
| `y ** 0.5` with `m^2` | `m` (correct) | VERIFIED |
| `y ** 0.333...` with `m^3` | `m` (Fraction correctly approximates 1/3) | VERIFIED |
| Non-constant exponent | Base forced dimensionless (correct) | VERIFIED |
| Long chain (25 vars) | All propagate correctly, terminates | VERIFIED |
| Worklist max iterations | 10,000 limit prevents pathological cases | VERIFIED |

---

## Summary of All Findings

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| CRIT-1 | CRITICAL | MCO test passes for wrong reason (lbf*s annotation silently dropped) | REQUIRES FIX |
| CRIT-2 | CRITICAL | Unit string parser cannot round-trip parenthesized output | REQUIRES FIX |
| CRIT-3 | CRITICAL | Conflicting annotations silently ignored (last wins) | REQUIRES FIX |
| HIGH-1 | HIGH | C++ std:: math functions not recognized by constraint builder | REQUIRES FIX |
| HIGH-2 | HIGH | C++ annotation parser captures trailing comments | REQUIRES FIX |
| HIGH-3 | HIGH | Python annotation parser captures trailing comments | REQUIRES FIX |
| MED-1 | MEDIUM | Annotation parse failures completely silent | RECOMMENDED FIX |
| MED-2 | MEDIUM | to_unit_string() uses non-conventional symbol ordering | COSMETIC |
| MED-3 | MEDIUM | Ternary expressions only check true branch | RECOMMENDED FIX |
| LOW-1 | LOW | C++ macros become variable references | DOCUMENTED |
| LOW-2 | LOW | C++ lambdas not analyzed | DOCUMENTED |

---

## Final Verdict

### REQUIRES FIXES BEFORE PHASE 3

The codebase has a strong foundation: the unit algebra engine is correct, SI derived units are verified, constraint propagation is sound, and the Python parser works well for annotated code. The C++ parser correctly produces IR for all basic constructs and achieves cross-language parity with Python.

However, three CRITICAL bugs and three HIGH bugs must be fixed before proceeding:

1. **CRIT-1 (lbf registration):** Immediate fix -- register `lbf` as a standalone unit.
2. **CRIT-2 (round-trip failure):** Either teach the parser to handle parentheses or change the renderer to avoid them.
3. **CRIT-3 (conflicting annotations):** Add conflict detection in `_eval_known` or `_process_annotations`.
4. **HIGH-1 (std:: functions):** Add `std::sqrt`, `std::sin`, etc. to the constraint builder's builtin lists.
5. **HIGH-2 + HIGH-3 (trailing comments):** Fix both annotation regexes to stop at secondary comment markers.

The MEDIUM and LOW items can be addressed during Phase 3 or later, but MED-1 (silent annotation failures) is strongly recommended to prevent future instances of CRIT-1-like bugs.
