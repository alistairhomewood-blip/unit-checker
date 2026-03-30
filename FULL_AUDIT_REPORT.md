# Full Audit Report: unit-checker
## Date: 2026-03-29
## Stack: Python CLI (static analysis tool)
## Scope: 32 Python source files, 10 test files

---

### 1. CRITICAL Issues (scientific correctness)

- **C-1: SI Prefixed Units Have Identical Dimension Vectors — Scale Factors Silently Discarded.**
  File: `src/unit_checker/core/unit_registry.py`, lines 276-306. All SI-prefixed units (km, cm, mm, mg, ms, kJ, MW, etc.) share the same UnitVector as their base unit. `km` and `m` are indistinguishable. Code mixing `km` and `m` without conversion (factor of 1000 error) will never be flagged. This defeats the tool's core purpose.

- **C-2: Liter Registered as Dimensionally Identical to m^3.**
  File: `src/unit_checker/core/unit_registry.py`, line 272. `L` has the same UnitVector as `m^3`, but 1 L = 0.001 m^3. Undetectable factor-of-1000 mismatch.

- **C-3: Temperature Offset Operations Not Handled.**
  File: `src/unit_checker/core/unit_algebra.py`. No distinction between absolute temperature and temperature difference. Adding absolute temperatures (physically meaningless) passes without violation.

- **C-4: Radian/Steradian Registered as Pure Dimensionless.**
  File: `src/unit_checker/core/unit_registry.py`, line 327. Angular unit misuse undetectable. The `kind` tag mechanism exists but is not applied to these units.

- **C-5: No Logarithmic Unit Support (dB, Neper).**
  Logarithmic units follow different algebra (addition = multiplication of underlying values). Code using dB as linear units will not be flagged.

- **C-6: F821 Undefined Name — Runtime Crash.**
  Ruff found 1 undefined variable. This code path raises `NameError` at runtime.

---

### 2. HIGH Issues

- **H-1: 4 B904 raise-without-from-inside-except.**
  Four locations raise new exceptions inside `except` blocks without preserving the original exception chain (`raise ... from err`). For a developer-facing CLI tool, losing the original traceback makes debugging reported issues much harder.

- **H-2: 3 B905 zip-without-strict.**
  Three `zip()` calls do not use `strict=True`. If the iterables have different lengths, the extra elements are silently dropped. In a unit analysis tool, this could mean some variables or constraints are silently ignored, leading to missed violations (false negatives).

- **H-3: 3 unused variables in parsers need review.**
  Three unused variables were flagged. In parser code, an unused variable often means a parsed value is being discarded rather than processed. This needs case-by-case investigation to determine if the variable was supposed to be used for constraint generation.

- **H-4: Radon complexity D for `check_command`.**
  The main CLI command handler is at complexity D. As the entry point for all analysis, this function orchestrates parsing, inference, and output. High complexity here risks incorrect behavior for certain flag combinations or input types.

- **H-5: Unused imports in config/loader.py (`os`) and output/terminal.py (`Panel`, `Text`, `Table`).**
  The unused `rich` imports in terminal.py suggest the terminal output formatting is incomplete -- these are common `rich` components for structured output that were imported but never used.

---

### 3. MEDIUM Issues

- **M-1: 128 E501 line-too-long errors.**
  High volume of long lines reduces readability, especially in parser code where expressions can be complex.

- **M-2: 69 UP045 non-PEP604 annotation issues.**
  Type annotations use the old `Optional[X]` and `Union[X, Y]` syntax instead of `X | Y`.

- **M-3: 22 unused imports across the codebase.**
  Dead imports that should be cleaned up.

- **M-4: 11 F541 f-string-missing-placeholders.**
  F-strings with no interpolation variables -- likely copy-paste artifacts.

- **M-5: Parser complexity is high but manageable (all C).**
  The `_visit_expression` functions in all three language parsers (Python, C++, Fortran) are rated complexity C. These are the core parsing functions and should be monitored for growth.

---

### 4. LOW Issues

- **L-1: Ruff reports 271 total errors.**
  Breakdown: 128 E501, 69 UP045, 22 unused imports, 11 F541, 1 F821, 4 B904, 3 B905, 3 unused variables. The volume suggests no CI lint enforcement.

- **L-2: Bandit clean.**
  No security findings, which is expected for a CLI tool that does not execute user code or handle network input.

- **L-3: Unused imports in config/loader.py (`os`).**
  Minor dead code.

---

### 5. VERIFIED CORRECT

- UnitVector representation correctly models all 7 SI base dimensions
- Unit algebra (multiplication, division, exponentiation) is mathematically correct
- Constraint propagation algorithm is sound for acyclic graphs
- Addition constraint correctly enforces same-dimension requirement
- SI derived unit definitions are correct (verified against NIST)
- Trig/exp/log function unit handling is correct (dimensionless in/out)
- SARIF output structure is valid
- Cross-language parity: Python, C++, and Fortran parsers produce equivalent analysis results
- Property-based tests verify algebraic invariants (multiply/divide identity, power-zero, power-one)
- All 263 existing tests pass with zero failures
- No security vulnerabilities (appropriate for CLI tool)

---

### 6. Test Coverage Report

- 10 test files covering 32 source files (31% test file ratio)
- Unit algebra has comprehensive tests including property-based (Hypothesis)
- All three language parsers have dedicated tests
- Constraint propagation tested
- SARIF output tested
- Config loading tested
- CLI integration tested
- Benchmarks tested
- **Gap:** No tests for `enrich_violation` in conflict_resolver.py
- **Gap:** No tests for terminal output formatting
- **Gap:** No tests for malformed unit string edge cases
- **Gap:** No property-based tests for constraint propagation (only for algebra)
- **Gap:** No tests for circular/cyclic constraint graphs
- **Gap:** No tests for `format_unit` and `compatible_with` methods on UnitRegistry

---

### 7. Scientific Correctness Summary

| Feature | Status | Notes |
|---------|--------|-------|
| SI base dimensions (7D vector) | Correct | All 7 properly represented |
| Unit multiplication/division | Correct | Verified algebraically and by tests |
| Exponentiation | Correct | Integer and fractional exponents |
| SI derived units | Correct | All verified against NIST |
| Constraint propagation | Correct | Sound for acyclic graphs |
| Trig/exp/log handling | Correct | Dimensionless in/out |
| Cross-language parity | Correct | Python, C++, Fortran equivalent |
| SI prefix handling | Limitation | All prefixes map to base dimensions (scale factors not tracked) |

---

### 8. Tool Output Summary

| Tool | Result |
|------|--------|
| Ruff | 271 errors (128 E501, 69 UP045, 22 unused imports, 1 F821, 4 B904, 3 B905, 11 F541, 3 unused variables) |
| Bandit | Clean -- no findings |
| Radon | Average complexity C (13.9). 1 D-rated function (`check_command`). Parsers all at C. |
| Vulture | Unused imports in config/loader.py (`os`), output/terminal.py (`Panel`, `Text`, `Table`) |
| Pytest | 263 passed, 0 failed, 1 deprecation warning |

---

### 9. Notes

- The 1 F821 undefined name is the highest-priority fix. For a static analysis tool, crashing on user input is unacceptable.
- The 3 unused variables in parsers (H-3) should be investigated before removal -- they may represent parsed values that should be feeding into constraint generation.
- The 3 B905 zip-without-strict findings (H-2) are particularly important for a static analysis tool. If zip silently truncates, the tool could miss violations, which is the worst possible failure mode for this kind of tool.
- The unused `rich` imports in terminal.py (H-5) suggest the output formatting was planned to be richer than what was implemented. This is a user experience gap rather than a correctness issue.
- The SI prefix limitation (all prefixes map to base dimensions without tracking scale factors) is a known design decision documented in PLANNING.md. It means the tool cannot detect scale-factor errors (e.g., mixing km and m), which is a significant limitation for real-world code.
