# PLANNING.md -- unit-checker

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [MVP Definition](#2-mvp-definition)
3. [Phase Breakdown](#3-phase-breakdown)
4. [Core Algorithm: Unit Inference via Constraint Propagation](#4-core-algorithm-unit-inference-via-constraint-propagation)
5. [Type Inference vs Constraint Propagation: Evaluation](#5-type-inference-vs-constraint-propagation-evaluation)
6. [User Annotation Model](#6-user-annotation-model)
7. [Handling Dimensionless Numbers and Ratios](#7-handling-dimensionless-numbers-and-ratios)
8. [Output Format: Violation Reports](#8-output-format-violation-reports)
9. [Multi-Language Support and Abstraction Layer](#9-multi-language-support-and-abstraction-layer)
10. [Data Models](#10-data-models)
11. [API Surface](#11-api-surface)
12. [Competitive Differentiation](#12-competitive-differentiation)
13. [Risks and Mitigations](#13-risks-and-mitigations)
14. [Parallelisation Map](#14-parallelisation-map)
15. [Open Questions for Review](#15-open-questions-for-review)

---

## 1. Executive Summary

unit-checker is a static analysis tool that infers physical units in scientific code (Python, C++, Fortran) and flags every inconsistency. It uses constraint propagation over 7-dimensional SI base dimension vectors. The user annotates a few entry-point variables; the tool infers everything else.

The MVP is a Python CLI that can analyze a single Python file with annotated entry points and produce a terminal report of unit violations. One developer can build it in 8-10 weeks.

---

## 2. MVP Definition

### What the MVP Does

The MVP (`v0.1.0`) is a command-line tool that:

1. Accepts a single Python file as input.
2. Reads unit annotations from comments or type-hint-style annotations.
3. Parses the file into an IR using Python's `ast` module.
4. Builds a constraint graph from the IR.
5. Propagates constraints from annotated variables.
6. Reports violations to the terminal in physics language.

### What the MVP Does NOT Do

- C++ or Fortran support (planned for Phase 2 and 3).
- Multi-file / cross-module analysis (planned for Phase 4).
- VSCode extension or API server (planned for Phase 5+).
- Detection of implicit unit conversions.
- Recognition of numeric constants (e.g., 9.81 = g).
- Configuration files (hardcoded to SI for MVP).

### MVP Success Criteria

1. Correctly flags unit violations in 10 benchmark test cases (see Audit Plan).
2. Zero false negatives on the benchmark suite (false positives are acceptable in MVP).
3. All violations include physics-language messages with source locations.
4. Runs in under 5 seconds on a 1000-line Python file.
5. User can install with `pip install unit-checker` and run `unit-checker check file.py`.

### MVP Estimated Effort (One Developer)

| Component | Estimated Days |
|-----------|---------------|
| Unit algebra engine | 3 |
| Unit registry (SI definitions) | 2 |
| Python parser (ast to IR) | 5 |
| IR data model | 2 |
| Constraint builder | 5 |
| Constraint propagator | 8 |
| Conflict resolver and violation reporter | 5 |
| Terminal output formatter | 3 |
| CLI entry point | 2 |
| Annotation parser | 3 |
| Test suite (unit + integration) | 7 |
| Benchmark suite | 3 |
| Packaging and docs | 2 |
| **Total** | **50 days (~10 weeks)** |

---

## 3. Phase Breakdown

### Phase 1: Core Engine (Weeks 1-4)
- Unit algebra engine (vector representation, operations)
- Unit registry with SI base and derived units
- IR data model
- Python parser (ast to IR)
- Constraint builder (IR to constraints)
- Constraint propagator (fixed-point iteration)
- Conflict resolver (minimal violation explanation)

### Phase 2: CLI and Output (Weeks 5-6)
- Annotation parser (comment and type-hint formats)
- Terminal output formatter (rich)
- JSON output formatter
- CLI entry point (click/typer)
- End-to-end integration

### Phase 3: Testing and Validation (Weeks 7-8)
- Unit test suite for each module
- Property-based tests for unit algebra (hypothesis)
- Benchmark suite of known-buggy codes
- Integration tests (end-to-end on fixture files)
- Performance benchmarking

### Phase 4: C++ Support (Weeks 9-12)
- tree-sitter C++ parser integration
- C++ to IR translation
- C++ annotation format (comments)
- C++ test fixtures and benchmarks

### Phase 5: Fortran Support (Weeks 13-16)
- tree-sitter Fortran parser integration (free-form and fixed-form)
- Fortran to IR translation
- Fortran annotation format (comments)
- Fortran test fixtures and benchmarks
- CamFort comparison benchmarks

### Phase 6: Multi-File Analysis (Weeks 17-20)
- Cross-module import resolution (Python)
- Header/include resolution (C++)
- Module/use resolution (Fortran)
- Inter-procedural constraint propagation

### Phase 7: IDE and CI/CD Integration (Weeks 21-28)
- Language Server Protocol implementation
- VSCode extension
- SARIF output format
- GitHub Action template
- REST API server for CI/CD

### Phase 8: Commercialisation (Weeks 29+)
- Paid tier feature gates
- User management and API keys
- Documentation and onboarding
- Marketing to aerospace and national lab communities

---

## 4. Core Algorithm: Unit Inference via Constraint Propagation

This is the core technical IP of the project. The algorithm has four stages.

### Stage 1: Parse to IR

The parser converts source code into a language-independent intermediate representation. The IR is a directed acyclic graph (DAG) of statements, where each statement is one of:

- **Assignment:** `variable = expression`
- **Expression:** arithmetic tree with operators (+, -, *, /, **) and operands (variables, literals)
- **FunctionDef:** `function_name(param1, param2, ...) -> return_var`
- **FunctionCall:** `result = function_name(arg1, arg2, ...)`
- **Return:** `return expression`
- **Annotation:** `variable has unit U` (from user annotation)

Each IR node carries source location (file, line, column) for error reporting.

### Stage 2: Build Constraints

Walk the IR and generate constraints. Each constraint relates the unit of one variable to the units of other variables.

**Constraint types and their generation rules:**

| Source Pattern | Constraint Generated | Explanation |
|---------------|---------------------|-------------|
| `c = a + b` | unit(c) = unit(a); unit(a) = unit(b) | Addition requires same dimensions |
| `c = a - b` | unit(c) = unit(a); unit(a) = unit(b) | Subtraction requires same dimensions |
| `c = a * b` | unit(c) = unit(a) + unit(b) | Product dimensions add (vector addition) |
| `c = a / b` | unit(c) = unit(a) - unit(b) | Quotient dimensions subtract |
| `c = a ** n` | unit(c) = n * unit(a) | Power scales dimension vector |
| `c = a` | unit(c) = unit(a) | Assignment preserves unit |
| `f(x)` called with `f(a)` | unit(x) = unit(a) | Argument unit matches parameter unit |
| `return expr` in `f` | unit(f_return) = unit(expr) | Return value carries expression's unit |
| Annotation: `a: m/s` | unit(a) = [1,0,-1,0,0,0,0] | Known unit from annotation |

**Handling numeric literals:**

- A numeric literal by itself is dimensionless: unit = [0,0,0,0,0,0,0].
- Exception: in `a * 2.0`, the literal `2.0` is dimensionless, so unit(result) = unit(a). This is correct.
- Exception: in `a + 2.0`, this forces unit(a) to be dimensionless. If a has a known unit, this is a violation.

**Handling comparison operators:**

- `a < b`, `a == b`, etc.: generate constraint unit(a) = unit(b). The result is boolean (no unit).

### Stage 3: Propagate Constraints

The propagator is a worklist algorithm:

```
ALGORITHM: UnitPropagation

Input:
  - variables: set of Variable, each with unit = None or a known UnitVector
  - constraints: set of Constraint

Output:
  - variables: each with unit = inferred UnitVector or None (unknown)
  - violations: set of Violation

Procedure:
  1. Initialize worklist W with all variables that have known units (from annotations).
  2. For each variable v in W:
     a. For each constraint C involving v:
        i.   Evaluate C given current known units.
        ii.  If C allows inferring a new variable's unit:
             - If that variable's unit was None: set it, add variable to W.
             - If that variable's unit was already set and MATCHES: no-op.
             - If that variable's unit was already set and CONFLICTS: record Violation.
        iii. If C cannot be evaluated yet (other variables unknown): skip, revisit later.
  3. Repeat until W is empty.
  4. Return (variables, violations).
```

**Propagation rules for each constraint type:**

For an EqualityConstraint `unit(a) = unit(b)`:
- If unit(a) is known and unit(b) is unknown: set unit(b) = unit(a).
- If unit(b) is known and unit(a) is unknown: set unit(a) = unit(b).
- If both known and equal: no-op.
- If both known and not equal: VIOLATION.

For a ProductConstraint `unit(c) = unit(a) + unit(b)`:
- If unit(a) and unit(b) known: infer unit(c) = unit(a) + unit(b).
- If unit(a) and unit(c) known: infer unit(b) = unit(c) - unit(a).
- If unit(b) and unit(c) known: infer unit(a) = unit(c) - unit(b).
- If all three known: check unit(c) == unit(a) + unit(b), else VIOLATION.

For a PowerConstraint `unit(c) = n * unit(a)`:
- If unit(a) known: infer unit(c) = n * unit(a).
- If unit(c) known and n != 0: infer unit(a) = unit(c) / n.
- If both known: check unit(c) == n * unit(a), else VIOLATION.

**Provenance tracking:**

Every time a unit is inferred, the propagator records:
- Which constraint caused the inference.
- Which previously-known variable(s) were used.
- The source location of the constraint.

This chain is used by the conflict resolver to explain violations.

### Stage 4: Report Violations

For each violation, the conflict resolver:

1. Takes the two conflicting unit vectors (expected vs actual).
2. Converts them to human-readable unit strings (e.g., [1,0,-1,0,0,0,0] -> "m/s").
3. Traces back the provenance chain for each to show HOW the units were inferred.
4. Formats a physics-language message:

```
ERROR: Unit mismatch at example.py:42:5

  total_force = mass * velocity
                       ^^^^^^^^
  Expected: force [kg*m/s^2]
  Got:      momentum [kg*m/s]

  Reason: 'total_force' was inferred as force [kg*m/s^2] from:
    Line 38: total_force = thrust + drag  (addition requires same units)
    Line 35: thrust annotated as force [N = kg*m/s^2]

  But 'mass * velocity' has units:
    Line 40: mass annotated as mass [kg]
    Line 41: velocity annotated as velocity [m/s]
    mass * velocity = kg * m/s = kg*m/s = momentum [kg*m/s]

  Suggestion: Did you mean 'mass * acceleration' instead of 'mass * velocity'?
```

---

## 5. Type Inference vs Constraint Propagation: Evaluation

### Approach A: Hindley-Milner Type Inference

**How it would work:** Encode units as types. Each variable has a type `Unit<L, M, T, I, Th, N, J>` where the parameters are integer exponents. Multiplication is `Unit<L1+L2, M1+M2, ...>`. Type inference unifies types across the program.

**Pros:**
- Well-studied algorithm with proven correctness guarantees.
- Handles polymorphism naturally (a function `scale(x, factor)` gets type `forall U. (U, Dimensionless) -> U`).
- Mature implementations exist (e.g., in OCaml, Haskell).

**Cons:**
- Requires dependent types or type-level integers to express dimensional exponents. Standard Hindley-Milner cannot express `Unit<L1+L2, ...>` without extensions.
- Error messages from type unification are notoriously bad for end users. "Cannot unify Unit<1,0,-1,0,0,0,0> with Unit<1,0,-2,0,0,0,0>" is not helpful to a physicist.
- Building an HM inference engine from scratch is a large project in itself (estimated 20+ additional days).
- The type system approach is over-engineered for this problem: we do not need full type inference. We only need to solve linear equations over a 7D rational vector space.

### Approach B: Constraint Propagation (CHOSEN)

**How it would work:** As described in Section 4 above.

**Pros:**
- Directly models the physics: units ARE vectors, arithmetic IS vector operations. No encoding indirection.
- Partial annotation is first-class: propagation naturally handles missing information.
- Provenance tracking is built in: every inference records its reason, making error messages excellent.
- Implementation is simpler: ~800-1200 lines for the core propagator vs ~3000+ for an HM engine.
- Performance: linear in the number of constraints for acyclic programs (which most straight-line simulation code is).

**Cons:**
- Does not handle parametric polymorphism natively. A function `scale(x, factor)` needs special treatment (see Section 4, FunctionCall handling). Mitigation: for MVP, treat each call site independently (inline the function's constraints at each call). This is correct but may miss some cross-call-site consistency checks.
- Does not have the theoretical guarantees of HM (principality of types). Mitigation: we do not need principal types. We need sound violation detection, which constraint propagation provides: if a violation is reported, it is real (no false positives from the core algorithm -- false positives may come from annotation errors).

### Decision

**Constraint propagation.** The problem structure (linear constraints over rational vectors) is a perfect fit. The implementation is simpler, the error messages are better, and the theoretical limitations (parametric polymorphism) can be addressed incrementally. Starting with HM would be building a general-purpose tool to solve a specific problem.

If parametric polymorphism proves essential (after Phase 3 user feedback), we can layer a limited form on top by introducing "unit variables" that are solved at each call site. This is a targeted extension, not a rewrite.

---

## 6. User Annotation Model

### How Users Annotate Entry Points

The user must annotate the "boundary" variables -- the ones whose units cannot be inferred from context. Typically these are:

- Function parameters of top-level / entry-point functions
- Global constants
- Variables read from external data (files, user input)

Everything else (intermediate variables, return values, local computations) is inferred.

### Annotation Syntax (Python)

Three supported formats, in order of preference:

**Format 1: Type comment (recommended for existing code)**
```python
velocity = 0.0  # unit: m/s
mass = 10.0     # unit: kg
```

**Format 2: Type hint annotation (recommended for new code)**
```python
from unit_checker import Unit

def compute_force(mass: Unit["kg"], acceleration: Unit["m/s^2"]) -> Unit["N"]:
    return mass * acceleration
```

**Format 3: Decorator (for function-level annotation)**
```python
from unit_checker import units

@units(mass="kg", acceleration="m/s^2", _return="N")
def compute_force(mass, acceleration):
    return mass * acceleration
```

### Annotation Syntax (C++)
```cpp
double velocity = 0.0; // unit: m/s
double mass = 10.0;    // unit: kg
```

### Annotation Syntax (Fortran)
```fortran
real :: velocity  ! unit: m/s
real :: mass      ! unit: kg
```

### Unit String Grammar

Unit strings are parsed with a simple grammar:

```
unit_string := unit_term (('*' | '/') unit_term)*
unit_term   := unit_name ('^' exponent)?
unit_name   := 'kg' | 'm' | 's' | 'A' | 'K' | 'mol' | 'cd'
             | 'N' | 'J' | 'W' | 'Pa' | 'Hz' | ...  (derived units)
             | 'km' | 'cm' | 'mm' | ...  (prefixed units)
exponent    := integer | '-' integer | rational
```

Examples: `m/s`, `kg*m/s^2`, `J/mol/K`, `m^2`, `kg/m^3`, `1` (dimensionless).

### Configuration File (.unit-checker.toml)

For project-wide defaults:

```toml
[defaults]
unit_system = "SI"          # or "CGS", "natural", "custom"
annotation_format = "comment"  # or "type_hint", "decorator"

[aliases]
# Project-specific unit aliases
velocity_units = "m/s"
force_units = "N"

[ignore]
# Files or functions to skip
paths = ["tests/", "setup.py"]
functions = ["__repr__", "__str__"]
```

---

## 7. Handling Dimensionless Numbers and Ratios

### The Problem

Many important physical quantities are dimensionless but NOT interchangeable:
- **Angles:** radians and degrees are both dimensionless but 1 radian != 1 degree.
- **Reynolds number:** dimensionless but has specific physical meaning.
- **Mach number:** dimensionless (velocity / speed of sound).
- **Strain:** dimensionless (length change / original length).
- **Efficiency:** dimensionless (output energy / input energy).
- **Counts:** number of particles, number of events.

If we treat all dimensionless quantities as the same, we lose the ability to catch errors like adding a Reynolds number to a Mach number.

### Solution: Kind Tags

Extend the unit vector with an optional "kind" tag. The kind tag is a string label that distinguishes dimensionless quantities:

```
UnitVector = (L, M, T, I, Th, N, J, kind)
```

Rules:
- Two units are compatible if and only if their 7D vectors are equal AND their kind tags are compatible.
- Kind tag compatibility: both None (plain dimensionless), or both equal, or one is None (untagged dimensionless is compatible with any kind -- this prevents false positives when a generic dimensionless operation is used).
- Kind tags propagate through multiplication/division: `angle * angle = angle^2` (kind preserved for same-kind operations), but `velocity / speed_of_sound = mach_number` (kind assigned by annotation or convention).

### Built-in Kinds

| Kind Tag | Examples |
|----------|----------|
| `angle` | radians, degrees, steradians |
| `ratio` | generic ratios, percentages |
| `count` | particle count, event count |
| `reynolds` | Reynolds number |
| `mach` | Mach number |
| `strain` | mechanical strain |

Users can define custom kinds in `.unit-checker.toml`.

### MVP Scope

For the MVP, kind tags are implemented but optional. The default behavior treats all dimensionless quantities as compatible (no kind tag). Users can opt in to stricter checking by annotating kinds. This avoids false positives in the MVP while providing the infrastructure for stricter checking later.

---

## 8. Output Format: Violation Reports

### Terminal Output (default)

```
unit-checker v0.1.0 -- analyzing example.py

  ERROR  example.py:42:5
  Unit mismatch in addition

    40 |  thrust = engine_force + drag_force
    41 |  # ... some code ...
    42 |  total = thrust + velocity
                          ^^^^^^^^
  Expected: force [N = kg*m/s^2]
  Got:      velocity [m/s]

  Inference chain:
    'thrust' is force [N] because:
      Line 40: thrust = engine_force + drag_force
      Line 12: engine_force annotated as [N]
    'velocity' is [m/s] because:
      Line 8: velocity annotated as [m/s]

  -----------------------------------------------

  WARNING  example.py:55:3
  Unable to infer units for variable 'result'

    55 |  result = compute_something(x, y)
         ^^^^^^
  No unit annotations found for parameters of 'compute_something'.
  Add annotations: def compute_something(x: Unit["..."], y: Unit["..."]) -> Unit["..."]:

  ===============================================

  Summary: 1 error, 1 warning, 47 variables analyzed, 45 units inferred.
```

### JSON Output (for CI/CD)

```json
{
  "version": "0.1.0",
  "file": "example.py",
  "summary": {
    "errors": 1,
    "warnings": 1,
    "variables_analyzed": 47,
    "units_inferred": 45
  },
  "violations": [
    {
      "severity": "error",
      "type": "addition_mismatch",
      "file": "example.py",
      "line": 42,
      "column": 5,
      "message": "Unit mismatch in addition: expected force [N = kg*m/s^2], got velocity [m/s]",
      "expected_unit": {"L": 1, "M": 1, "T": -2, "I": 0, "Th": 0, "N": 0, "J": 0},
      "actual_unit": {"L": 1, "M": 0, "T": -1, "I": 0, "Th": 0, "N": 0, "J": 0},
      "inference_chain": [
        {"variable": "thrust", "unit": "N", "reason": "addition with engine_force", "line": 40},
        {"variable": "engine_force", "unit": "N", "reason": "annotation", "line": 12}
      ]
    }
  ]
}
```

### SARIF Output (for GitHub Code Scanning)

SARIF (Static Analysis Results Interchange Format) v2.1.0 for integration with GitHub Advanced Security, Azure DevOps, and other tools that consume SARIF.

Structure follows the SARIF specification with:
- `tool` section identifying unit-checker version
- `results` array with one entry per violation
- Each result includes `locations`, `message`, `level`, and `relatedLocations` (for inference chain)

---

## 9. Multi-Language Support and Abstraction Layer

### Architecture

```
Source Code (Python / C++ / Fortran)
        |
        v
  [Language-Specific Parser]  <-- one per language, outputs IR
        |
        v
  [Intermediate Representation (IR)]  <-- language-independent
        |
        v
  [Constraint Builder]  <-- walks IR, generates constraints
        |
        v
  [Constraint Propagator]  <-- solves constraints, finds violations
        |
        v
  [Violation Reporter]  <-- formats output (terminal / JSON / SARIF)
```

### The Parser Contract

Every language parser must implement this interface:

```
parse(source_code: str, file_path: str) -> IRModule

where IRModule contains:
  - functions: list of IRFunction
  - global_variables: list of IRVariable
  - global_assignments: list of IRAssignment
  - annotations: list of IRAnnotation (unit annotations found in comments/hints)
```

### Language-Specific Considerations

**Python:**
- Parser: `ast` stdlib module.
- Handles: assignments, expressions, function defs/calls, return statements, list comprehensions (basic), class methods (basic).
- Does NOT handle (MVP): decorators with side effects, metaclasses, dynamic attribute access, exec/eval.

**C++ (Phase 4):**
- Parser: tree-sitter with `tree-sitter-cpp` grammar.
- Additional handling needed: templates (map to polymorphic functions), header includes (resolve to find declarations), operator overloading (map to standard operators), namespaces.
- Challenge: C++ has much richer type syntax. Variable declarations may have complex types (`std::vector<double>`) that need to be recognized as "this is a numeric container" for unit inference.

**Fortran (Phase 5):**
- Parser: tree-sitter with `tree-sitter-fortran` (free-form) and `tree-sitter-fixed-form-fortran` (fixed-form).
- Additional handling needed: COMMON blocks (shared global variables), IMPLICIT typing (need to know default type rules), MODULE/USE statements (cross-module resolution), EQUIVALENCE (aliasing), array operations (Fortran's array syntax).
- Opportunity: Fortran code tends to have very explicit variable declarations (`REAL*8 :: velocity`), which makes the parser's job easier.
- Reference: CamFort's approach to Fortran unit analysis (https://github.com/camfort/camfort) -- study their annotation format and inference approach for compatibility or improvement.

### Adding a New Language

To add support for a new language:

1. Create a new directory `src/unit_checker/parsers/<language>_parser/`.
2. Implement the `parse()` function that converts source code to IR.
3. Define the annotation comment format for that language.
4. Add test fixtures in `tests/fixtures/<language>/`.
5. No changes needed to the inference engine, constraint builder, or output formatters.

---

## 10. Data Models

### UnitVector

```
UnitVector:
  length: Rational        # exponent of meters (L)
  mass: Rational          # exponent of kilograms (M)
  time: Rational          # exponent of seconds (T)
  current: Rational       # exponent of amperes (I)
  temperature: Rational   # exponent of kelvin (Th)
  amount: Rational        # exponent of moles (N)
  luminosity: Rational    # exponent of candela (J)
  kind: Optional[str]     # dimensionless kind tag (e.g., "angle", "reynolds")
  scale: Optional[Rational]  # scale factor relative to SI base (e.g., km = 1000 * m)
```

Using `Rational` (from Python's `fractions.Fraction`) for exponents because:
- Square root of area has exponent L^(1/2) -- need non-integer exponents.
- Exact arithmetic avoids floating-point comparison issues.

### IRNode (Intermediate Representation)

```
IRModule:
  file_path: str
  functions: list[IRFunction]
  global_variables: list[IRVariable]
  global_statements: list[IRStatement]
  annotations: list[IRAnnotation]

IRFunction:
  name: str
  parameters: list[IRVariable]
  body: list[IRStatement]
  return_variable: Optional[IRVariable]  # synthetic variable for return value
  location: SourceLocation

IRVariable:
  name: str
  scope: str  # "global", "local:<function_name>", "param:<function_name>"
  location: SourceLocation
  annotation: Optional[UnitVector]  # if user-annotated

IRStatement: one of
  IRAssignment(target: IRVariable, expression: IRExpression, location: SourceLocation)
  IRReturn(expression: IRExpression, location: SourceLocation)
  IRFunctionCall(result: Optional[IRVariable], function: str, arguments: list[IRExpression], location: SourceLocation)

IRExpression: one of
  IRVariableRef(variable: IRVariable)
  IRLiteral(value: float)
  IRBinaryOp(operator: +|-|*|/|**, left: IRExpression, right: IRExpression)
  IRUnaryOp(operator: -|+, operand: IRExpression)
  IRFunctionCallExpr(function: str, arguments: list[IRExpression])

IRAnnotation:
  variable_name: str
  scope: str
  unit_string: str  # unparsed, e.g., "m/s"
  location: SourceLocation

SourceLocation:
  file: str
  line: int
  column: int
```

### Constraint

```
Constraint: one of
  EqualityConstraint(var_a: IRVariable, var_b: IRVariable, location: SourceLocation)
  ProductConstraint(result: IRVariable, operand_a: IRVariable, operand_b: IRVariable, location: SourceLocation)
  QuotientConstraint(result: IRVariable, numerator: IRVariable, denominator: IRVariable, location: SourceLocation)
  PowerConstraint(result: IRVariable, base: IRVariable, exponent: Rational, location: SourceLocation)
  KnownUnitConstraint(variable: IRVariable, unit: UnitVector, location: SourceLocation)
```

### Violation

```
Violation:
  severity: "error" | "warning" | "info"
  type: str  # "addition_mismatch", "assignment_mismatch", "function_argument_mismatch", "return_mismatch"
  location: SourceLocation
  expected_unit: UnitVector
  actual_unit: UnitVector
  message: str  # human-readable physics-language message
  inference_chain_expected: list[InferenceStep]  # how expected_unit was derived
  inference_chain_actual: list[InferenceStep]     # how actual_unit was derived

InferenceStep:
  variable: str
  unit: UnitVector
  reason: str  # "annotation", "addition with <var>", "product of <var_a> and <var_b>", etc.
  location: SourceLocation
```

---

## 11. API Surface

### CLI Interface (MVP)

```
unit-checker check <file> [options]

Options:
  --format <terminal|json|sarif>   Output format (default: terminal)
  --unit-system <SI|CGS|natural>   Default unit system (default: SI)
  --strict                         Treat warnings as errors
  --verbose                        Show full inference chains
  --quiet                          Only show errors, no warnings
  --config <path>                  Path to config file
  --output <path>                  Write output to file instead of stdout
```

### Future: Python Library API

```python
from unit_checker import check_file, check_source

# Check a file
result = check_file("simulation.py", unit_system="SI")
print(result.violations)
print(result.inferred_units)

# Check source code string
result = check_source(source_code, language="python")
```

### Future: REST API (CI/CD)

```
POST /api/v1/check
  Body: { "source": "...", "language": "python", "annotations": {...} }
  Response: { "violations": [...], "summary": {...} }

POST /api/v1/check-pr
  Body: { "repo": "...", "pr_number": 42, "github_token": "..." }
  Response: { "violations": [...], "annotations": [...] }
```

---

## 12. Competitive Differentiation

### vs. pint / astropy.units / unyt

| Feature | pint/astropy/unyt | unit-checker |
|---------|-------------------|--------------|
| Approach | Runtime unit tracking | Static analysis |
| Requires code changes? | Yes (use Quantity types) | No (works on existing code) |
| Catches errors when? | At runtime | Before running |
| Works on C++/Fortran? | No (Python only) | Yes |
| Performance overhead? | Yes (wraps every number) | None (analysis tool) |
| CI/CD integration? | No | Yes (planned) |

**Key differentiator:** pint et al. are runtime libraries that require rewriting code to use special types. unit-checker is a static analysis tool that works on existing, unmodified code with minimal annotations.

### vs. CamFort

| Feature | CamFort | unit-checker |
|---------|---------|--------------|
| Languages | Fortran only | Python, C++, Fortran |
| Implementation language | Haskell | Python |
| Installation | Complex (Haskell toolchain) | pip install |
| Active development | Academic, sporadic | Planned commercial |
| CI/CD integration | No | Yes (planned) |
| Annotation format | CamFort-specific comments | Multiple formats (comments, type hints, decorators) |

**Key differentiator:** CamFort is Fortran-only and requires a Haskell toolchain. unit-checker is Python-native (trivial to install for the target audience), supports three languages, and targets commercial CI/CD workflows.

### vs. njoy/DimensionalAnalysis (C++)

| Feature | njoy/DimensionalAnalysis | unit-checker |
|---------|-------------------------|--------------|
| Approach | Compile-time C++ types | Static analysis |
| Requires code changes? | Yes (use special types) | No |
| Languages | C++ only | Python, C++, Fortran |

**Key differentiator:** njoy requires rewriting C++ code to use special templated types. unit-checker works on existing code.

### vs. mypy / pyright

These are Python type checkers, not unit checkers. They are complementary. However, there is a potential future integration: a mypy plugin that uses unit-checker's engine to check units expressed as Python types.

---

## 13. Risks and Mitigations

### Risk 1: Insufficient annotation coverage
**Risk:** Users do not annotate enough variables, leading to large "unknown" regions where no checking is possible.
**Likelihood:** High.
**Impact:** Medium (tool is less useful but not wrong).
**Mitigation:**
- Provide a "suggest annotations" command that identifies which unannotated variables would unlock the most additional inferences.
- Support a database of common physics constants and their units.
- In verbose mode, report the percentage of variables with inferred units as a coverage metric.

### Risk 2: False positives from annotation errors
**Risk:** User annotates a variable with the wrong unit, causing cascading false violations.
**Likelihood:** Medium.
**Impact:** High (user loses trust in the tool).
**Mitigation:**
- When a violation is reported, always show the full inference chain back to the original annotation. This makes it easy to spot a wrong annotation.
- Support a "trust" mode where the tool cross-checks annotations against each other (if two annotations conflict, flag the annotations themselves).

### Risk 3: Polymorphic functions defeat inference
**Risk:** Scientific code uses generic helper functions (normalize, interpolate, scale) that preserve unit relationships in ways the constraint propagator cannot express.
**Likelihood:** High.
**Impact:** Medium (some variables remain "unknown", some violations missed).
**Mitigation:**
- MVP: inline function constraints at each call site. This handles most cases.
- Phase 6: introduce "unit variables" (analogous to type variables) for parametric unit relationships.
- Provide an escape hatch: `# unit-checker: ignore` comment to suppress checking on specific lines.

### Risk 4: tree-sitter grammars do not cover all language features
**Risk:** tree-sitter C++ or Fortran grammars fail on exotic syntax (e.g., Fortran 2008 coarrays, C++ fold expressions).
**Likelihood:** Medium.
**Impact:** Low (tool gracefully skips unparseable sections).
**Mitigation:**
- Graceful degradation: if a section cannot be parsed, emit a warning and skip it.
- Track tree-sitter grammar issues upstream and contribute fixes.
- For Fortran specifically, study CamFort's fortran-src for hard cases.

### Risk 5: Performance on large codebases
**Risk:** Constraint propagation is slow on codebases with 100K+ lines.
**Likelihood:** Low (the algorithm is linear in constraints for acyclic code).
**Impact:** Medium.
**Mitigation:**
- Profile before optimizing.
- Constraint propagation can be parallelised per-function for intra-procedural analysis.
- Inter-procedural analysis can use incremental propagation (only re-check changed functions).

### Risk 6: Adoption barrier
**Risk:** Scientists do not want to add annotations to their code.
**Likelihood:** High.
**Impact:** High (tool is useless without annotations).
**Mitigation:**
- Make annotations minimal (just entry points).
- Provide an "auto-annotate" command that uses heuristics (variable naming conventions, common patterns) to suggest annotations.
- Show ROI: "you annotated 5 variables and we checked 500 for free."
- Long term: use LLMs to suggest annotations based on variable names and context.

---

## 14. Parallelisation Map

### What Can Be Built in Parallel

Phase 1 has internal dependencies, but some work can be parallelised across agents:

**Independent streams:**
1. **Unit algebra engine** (core/unit_algebra.py, core/unit_registry.py) -- no dependencies on parsers or inference.
2. **IR data model** (models/, parsers/common/ir.py) -- no dependencies on implementation.
3. **Python parser** (parsers/python_parser/) -- depends on IR data model only.
4. **Constraint builder + propagator** (inference/) -- depends on IR data model and unit algebra.
5. **Output formatters** (output/) -- depends on violation data model only.
6. **Test fixtures** (tests/fixtures/) -- no dependencies.

**Dependency graph:**
```
IR data model  -->  Python parser  -->  Integration tests
      |                                       ^
      v                                       |
Unit algebra  -->  Constraint builder  -->  Constraint propagator  -->  Integration tests
                                                    |
                                                    v
                                        Conflict resolver  -->  Output formatters  -->  CLI
```

**Recommended parallelisation (2 agents):**
- Agent A: Unit algebra + IR data model + Constraint builder + Propagator
- Agent B: Python parser + Output formatters + CLI + Test fixtures

**Recommended parallelisation (3 agents):**
- Agent A: Unit algebra + Constraint builder + Propagator (core algorithm)
- Agent B: IR data model + Python parser (parsing pipeline)
- Agent C: Output formatters + CLI + Test fixtures + Benchmark suite (user-facing)

---

## 15. Open Questions for Review

These questions should be resolved before implementation begins. They are listed in priority order.

1. **Annotation syntax finalization.** The three proposed formats (comment, type hint, decorator) are all reasonable. Should we support all three from the start, or pick one for MVP? Recommendation: comment format only for MVP (works across all languages), add type hints and decorators in Phase 2.

2. **Inter-procedural analysis depth.** How many levels of function calls should we follow? Options: (a) single function only (MVP), (b) one level of callee expansion, (c) full call-graph analysis. Recommendation: (a) for MVP, (b) for Phase 2.

3. **Dimensionless kind tags.** Should kind tags be first-class in the MVP, or deferred? Recommendation: implement the data model with kind support, but default all dimensionless to kind=None (no strictness) for MVP.

4. **Error vs warning threshold.** What is an error vs a warning? Proposal: definite violations (two known conflicting units) are errors; uncertain situations (one known, one unknown suggesting a possible issue) are warnings; coverage gaps (unable to infer) are info.

5. **Scale factors and unit conversions.** Should the MVP track scale factors (e.g., distinguish km from m) or only dimensions? Recommendation: dimensions only for MVP. Scale factors in Phase 2. Rationale: dimensional analysis catches the most dangerous errors (the Mars Climate Orbiter error was a dimension-preserving scale error, but most errors in practice are dimensional).

6. **Handling of numpy/scipy operations.** Scientific Python code heavily uses numpy. `np.dot(a, b)` has specific unit semantics (inner product). How much numpy awareness do we need? Recommendation: a small allowlist of numpy functions with known unit semantics for MVP (dot, cross, sqrt, abs, sum, mean). Expand in later phases.

7. **Configuration file format.** TOML or YAML? Recommendation: TOML (it is the Python packaging standard, `.toml` is familiar to Python developers).
