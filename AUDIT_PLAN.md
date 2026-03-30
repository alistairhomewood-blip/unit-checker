# AUDIT_PLAN.md -- unit-checker

## Guiding Principle

**Correctness is everything.** A false negative (missed unit violation) is worse than a false positive (spurious warning). In aerospace and simulation contexts, a missed violation can cause mission failure, structural collapse, or incorrect scientific results. A false positive only costs the user a few seconds of investigation.

The audit plan reflects this asymmetry: every test case is designed to verify that real violations are caught, and false-negative scenarios are tested more heavily than false-positive scenarios.

---

## 1. Benchmark Suite of Known-Buggy Simulation Codes

### 1.1 Mars Climate Orbiter Reconstruction

**Source:** NASA MCO Mishap Investigation Board Phase I Report. Lockheed Martin's SM_FORCES software output thrust impulse in pound-force-seconds; NASA's trajectory software expected newton-seconds.

**Test case:** A simplified Python reconstruction of the MCO error pattern:
```
# Pseudocode (not implementation -- this describes the test fixture to be created)
# File: mco_lockheed.py
thrust_impulse = compute_thrust(...)  # unit: lbf*s (pound-force-seconds)

# File: mco_nasa.py
trajectory_correction = thrust_impulse * direction  # expects: N*s (newton-seconds)
```

**Expected result:** unit-checker flags the mismatch between lbf*s and N*s at the interface boundary.

**Note:** This test case requires supporting pound-force as a unit. For MVP (SI only), create a simplified version where one module uses CGS and another uses SI, producing the same pattern of interface mismatch.

### 1.2 Velocity-Acceleration Addition

The most common unit error in physics code: accidentally adding quantities with different dimensions.

**Test case:**
```
velocity = 10.0     # unit: m/s
acceleration = 9.8  # unit: m/s^2
result = velocity + acceleration  # BUG: dimensions do not match
```

**Expected result:** Error flagged at the addition, with message explaining that m/s cannot be added to m/s^2.

### 1.3 Force Computation with Wrong Formula

**Test case:**
```
mass = 5.0          # unit: kg
velocity = 10.0     # unit: m/s
force = mass * velocity  # BUG: this is momentum (kg*m/s), not force (kg*m/s^2)
thrust = force + drag    # where drag is annotated as N
```

**Expected result:** Error at the addition of force (which is actually momentum) and drag (which is force). The message should explain that kg*m/s (momentum) cannot be added to kg*m/s^2 (force).

### 1.4 Energy Conservation Check

**Test case:**
```
mass = 2.0                   # unit: kg
height = 10.0                # unit: m
gravity = 9.81               # unit: m/s^2
velocity = 5.0               # unit: m/s
potential_energy = mass * gravity * height      # correct: kg*m/s^2*m = J
kinetic_energy = mass * velocity               # BUG: should be 0.5*mass*velocity^2
total_energy = potential_energy + kinetic_energy  # will flag: J != kg*m/s
```

**Expected result:** Error at the addition, explaining that J (kg*m^2/s^2) cannot be added to kg*m/s.

### 1.5 Correct Code (No Violations)

Equally important: verify the tool does NOT flag correct code.

**Test case:**
```
distance = 100.0    # unit: m
time = 10.0         # unit: s
velocity = distance / time              # inferred: m/s (correct)
acceleration = velocity / time          # inferred: m/s^2 (correct)
force = mass * acceleration             # inferred: N (correct)
work = force * distance                 # inferred: J (correct)
power = work / time                     # inferred: W (correct)
```

**Expected result:** Zero violations. All units correctly inferred and consistent.

### 1.6 Function Call Unit Propagation

**Test case:**
```
def compute_velocity(distance, time):  # distance: m, time: s
    return distance / time

v = compute_velocity(100.0, 10.0)  # v should be inferred as m/s
a = v + 5.0  # BUG if 5.0 is not m/s; or OK if dimensionless addition is allowed
momentum = mass * v  # should be kg*m/s
force_wrong = momentum + drag  # BUG: momentum != force
```

**Expected result:** Correctly infers v as m/s through function call. Flags momentum + drag mismatch.

### 1.7 Exponentiation and Square Root

**Test case:**
```
length = 4.0         # unit: m
area = length ** 2   # inferred: m^2
volume = area * length  # inferred: m^3
side = area ** 0.5   # inferred: m (square root of area)
bad_add = area + length  # BUG: m^2 != m
```

**Expected result:** Correct inference of m^2, m^3, m. Flags area + length mismatch.

### 1.8 Division Producing Dimensionless Result

**Test case:**
```
velocity1 = 10.0   # unit: m/s
velocity2 = 5.0    # unit: m/s
ratio = velocity1 / velocity2  # dimensionless (correct)
distance = ratio * 100.0       # should be dimensionless * dimensionless = dimensionless
bad = distance + velocity1     # BUG: dimensionless != m/s
```

**Expected result:** ratio correctly inferred as dimensionless. Flags distance + velocity1 mismatch.

### 1.9 Assignment Chain Propagation

**Test case:**
```
x = 10.0      # unit: m
y = x
z = y
w = z
result = w + 5.0  # unit: m + dimensionless -- should flag if strict
result2 = w * 2.0  # OK: m * dimensionless = m
result3 = result2 + x  # OK: m + m = m
```

**Expected result:** Units propagate through the assignment chain x -> y -> z -> w. All get unit m.

### 1.10 Multi-Operation Expression

**Test case:**
```
mass = 2.0          # unit: kg
velocity = 3.0      # unit: m/s
height = 10.0       # unit: m
g = 9.81            # unit: m/s^2

kinetic = 0.5 * mass * velocity ** 2   # should be: kg * (m/s)^2 = kg*m^2/s^2 = J
potential = mass * g * height           # should be: kg * m/s^2 * m = kg*m^2/s^2 = J
total = kinetic + potential             # should be: J + J = J (correct)
bad_total = kinetic + mass              # BUG: J != kg
```

**Expected result:** Correctly infers kinetic and potential as J (kg*m^2/s^2). Flags kinetic + mass.

---

## 2. Audit Criteria by Checkpoint

### Checkpoint 1: Unit Algebra Engine

| ID | Criterion | Pass Condition |
|----|-----------|---------------|
| 1.1 | Vector representation | All 7 SI dimensions stored as Rational, not float |
| 1.2 | Multiplication | velocity * time = distance: [1,0,-1] + [0,0,1] = [1,0,0] |
| 1.3 | Division | distance / time = velocity: [1,0,0] - [0,0,1] = [1,0,-1] |
| 1.4 | Exponentiation | length^2 = area: 2 * [1,0,0] = [2,0,0] |
| 1.5 | Square root | area^0.5 = length: 0.5 * [2,0,0] = [1,0,0] |
| 1.6 | Equality | m/s == m/s: [1,0,-1] == [1,0,-1] |
| 1.7 | Inequality | m/s != m/s^2: [1,0,-1] != [1,0,-2] |
| 1.8 | Dimensionless | m/m = dimensionless: [1,0,0] - [1,0,0] = [0,0,0] |
| 1.9 | Named unit lookup | "N" resolves to [1,1,-2,0,0,0,0] |
| 1.10 | Unit string parsing | "kg*m/s^2" parses to [1,1,-2,0,0,0,0] |
| 1.11 | Unit string rendering | [1,1,-2,0,0,0,0] renders as "kg*m/s^2" or "N" |
| 1.12 | Property-based: multiply then divide returns original | For random unit U, (U * V) / V == U |
| 1.13 | Property-based: add zero dimensions is identity | For random unit U, U + dimensionless_zero == U in multiplication |

### Checkpoint 2: Python Parser

| ID | Criterion | Pass Condition |
|----|-----------|---------------|
| 2.1 | Simple assignment | `x = 5.0` produces IRAssignment with IRLiteral |
| 2.2 | Arithmetic expression | `y = a + b * c` produces correct IR tree with precedence |
| 2.3 | Function definition | `def f(x, y): return x + y` produces IRFunction with params and body |
| 2.4 | Function call | `z = f(a, b)` produces IRFunctionCall with correct argument mapping |
| 2.5 | Comment annotation | `# unit: m/s` on preceding line produces IRAnnotation |
| 2.6 | Nested expressions | `z = (a + b) * (c - d)` produces correct IR tree |
| 2.7 | Chained assignment | `a = b = c = 5.0` produces multiple IRAssignments |
| 2.8 | Return statement | `return x * y` produces IRReturn with correct expression |
| 2.9 | Source locations | All IR nodes have correct file/line/column |
| 2.10 | Multiple functions | File with 3 functions produces 3 IRFunction nodes |

### Checkpoint 3: Constraint Propagation MVP

| ID | Criterion | Pass Condition |
|----|-----------|---------------|
| 3.1 | Forward propagation | Annotated input propagates to output through assignment chain |
| 3.2 | Backward propagation | Known output unit propagates backward to infer input units |
| 3.3 | Addition constraint | `c = a + b` with known unit(a) infers unit(b) = unit(c) = unit(a) |
| 3.4 | Multiplication constraint | `c = a * b` with known unit(a) and unit(b) infers unit(c) |
| 3.5 | Division constraint | `c = a / b` with known unit(c) and unit(b) infers unit(a) |
| 3.6 | Violation detection | Conflicting constraints produce a Violation |
| 3.7 | Provenance tracking | Each inferred unit has a complete provenance chain |
| 3.8 | Fixed-point convergence | Propagation terminates for all acyclic IR |
| 3.9 | Benchmark 1.2 passes | Velocity-acceleration addition flagged |
| 3.10 | Benchmark 1.5 passes | Correct code produces zero violations |
| 3.11 | Benchmark 1.10 passes | Multi-operation expression correctly analyzed |

### Checkpoint 4: CLI MVP

| ID | Criterion | Pass Condition |
|----|-----------|---------------|
| 4.1 | Basic invocation | `unit-checker check file.py` runs without error |
| 4.2 | Terminal output | Violations displayed with file, line, message, inference chain |
| 4.3 | JSON output | `--format json` produces valid JSON |
| 4.4 | Exit codes | Exit 0 for no violations, exit 1 for errors |
| 4.5 | All 10 benchmarks pass | Complete benchmark suite produces correct results |
| 4.6 | Performance | 1000-line file analyzed in under 5 seconds |
| 4.7 | Error handling | Invalid file path produces helpful error message |
| 4.8 | Verbose mode | `--verbose` shows full inference chains |

### Checkpoint 5: C++ Parser

| ID | Criterion | Pass Condition |
|----|-----------|---------------|
| 5.1 | Variable declaration | `double velocity = 10.0;` produces IRVariable + IRAssignment |
| 5.2 | Arithmetic expression | `double force = mass * acceleration;` produces correct IR |
| 5.3 | Function definition | C++ function produces IRFunction |
| 5.4 | Comment annotation | `// unit: m/s` produces IRAnnotation |
| 5.5 | Same inference engine | C++ IR produces same violations as equivalent Python IR |

### Checkpoint 6: Fortran Parser

| ID | Criterion | Pass Condition |
|----|-----------|---------------|
| 6.1 | Variable declaration | `REAL :: velocity` produces IRVariable |
| 6.2 | Assignment | `velocity = distance / time` produces correct IR |
| 6.3 | Subroutine | Fortran subroutine produces IRFunction |
| 6.4 | Comment annotation | `! unit: m/s` produces IRAnnotation |
| 6.5 | Fixed-form support | Fixed-form Fortran 77 code parses correctly |
| 6.6 | Same inference engine | Fortran IR produces same violations as equivalent Python IR |

### Checkpoint 7: Full Benchmark Suite

| ID | Criterion | Pass Condition |
|----|-----------|---------------|
| 7.1 | All 10 core benchmarks pass | Zero false negatives across all benchmarks |
| 7.2 | False positive rate | Fewer than 10% false positives on the correct-code benchmark |
| 7.3 | Cross-language consistency | Same physics error in Python, C++, Fortran produces same violation |
| 7.4 | Performance | 10K-line file analyzed in under 30 seconds |
| 7.5 | Edge cases | Empty file, file with no annotations, file with syntax errors all handled gracefully |

---

## 3. False Negative Testing Strategy

Because false negatives are worse than false positives, we dedicate specific testing effort to ensuring violations are not missed.

### 3.1 Mutation Testing

For each benchmark test case that contains a known violation:
1. Confirm the violation is detected.
2. Mutate the code to introduce a DIFFERENT violation at the same location.
3. Confirm the new violation is also detected.
4. Mutate the code to REMOVE the violation (fix it).
5. Confirm no violation is reported (avoid sticky false positives).

### 3.2 Adversarial Test Cases

Design test cases that might trick the constraint propagator:

- **Long chains:** Unit propagates through 20+ assignments. Does it still work?
- **Diamond dependencies:** Variable's unit is constrained from two independent paths. Are both paths checked?
- **Self-referencing:** `x = x + delta` in a loop. Does the tool handle this without infinite propagation?
- **Unused variables:** Annotated variable is never used in an expression. Does the tool still validate its annotation?
- **Shadowed variables:** Same variable name in different scopes with different units. Are scopes handled correctly?

### 3.3 Regression Testing

Every bug found in production (reported by users) becomes a permanent regression test. The test must include:
- The minimal reproducing code.
- The expected violation (or lack thereof).
- The bug report ID for traceability.

---

## 4. Correctness Audit Protocol

### Before Every Release

1. Run the complete benchmark suite. All 10 core benchmarks must pass with zero false negatives.
2. Run the mutation test suite. All mutations must be detected.
3. Run the adversarial test suite. All adversarial cases must be handled correctly.
4. Run property-based tests (hypothesis). At least 10,000 random test cases for unit algebra.
5. Manual review: pick 5 random files from an open-source physics codebase (e.g., astropy, scipy, OpenFOAM) and verify that the tool's output is sensible.

### After Every Change to the Inference Engine

1. The full benchmark suite must be re-run.
2. Any new constraint type or propagation rule must come with at least 5 dedicated test cases.
3. Performance benchmarks must not regress by more than 20%.

---

## 5. Audit Schedule

| Checkpoint | Target Date | Auditor | Gate |
|------------|-------------|---------|------|
| 0 | Planning complete | Self-audit | All planning docs exist, no code |
| 1 | End of Week 2 | Peer review | Unit algebra correctness |
| 2 | End of Week 4 | Peer review | Parser completeness |
| 3 | End of Week 6 | Full audit | Core algorithm correctness |
| 4 | End of Week 8 | Full audit + user testing | MVP usability and correctness |
| 5 | End of Week 12 | Peer review | C++ parity |
| 6 | End of Week 16 | Peer review | Fortran parity |
| 7 | End of Week 18 | Full audit | Complete benchmark suite |
| 8 | Pre-release | External audit | Release readiness |

---

## 6. Metrics to Track

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| False negative rate | 0% on benchmark suite | Automated test suite |
| False positive rate | < 10% on correct-code benchmarks | Manual review + automated |
| Variables analyzed per second | > 1000 | Performance benchmark |
| Unit inference coverage | > 80% of variables in annotated code | Coverage report from tool |
| User annotation burden | < 5% of variables need annotation | Measure on real codebases |
| Benchmark suite size | 10+ core + 20+ adversarial | Count |
