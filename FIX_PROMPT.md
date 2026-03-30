You are implementing fixes for unit-checker based on TWO comprehensive external audits (FULL_AUDIT_REPORT.md and CODEX_AUDIT_REPORT.md). Findings present in BOTH audits are elevated to CRITICAL. Fix everything listed below. Run the full test suite after each logical group of fixes to ensure zero regressions. Do not proceed to the next group if tests are failing.

## CRITICAL Fixes (confirmed by both audits)

- **CRIT-1: SI prefixed units have identical dimension vectors -- scale factors silently discarded at `src/unit_checker/core/unit_registry.py:276-306`.** All prefixed units (km, cm, mm, mg, ms, kJ, MJ, kW, MW, etc.) are registered with the same UnitVector as their base unit. This means mixing km and m without conversion is not flagged. Codex CONFIRMED at runtime that `km == m`, `cm == m`. Fix by adding a `scale_factor` field to `UnitVector` that tracks the multiplier relative to the base SI unit. When two units of the same dimension but different scale factors are combined in addition/subtraction, flag a warning: "Adding km [1000 m] to m [1 m] -- possible unit scale mismatch." At minimum, ensure `get_name()` returns the registered name (e.g., `km`) rather than the base unit name (e.g., `m`) for annotated variables. Also fix `min` (minute) and `hr` (hour) which are dimensionally identical to `s` but represent different scales.

- **CRIT-2: Liter registered as dimensionally identical to m^3 at `src/unit_checker/core/unit_registry.py:272`.** Codex CONFIRMED at runtime that `L == m^3`. A liter is 0.001 m^3. Apply the same scale-factor mechanism from CRIT-1 to distinguish L from m^3. Flag additions of L and m^3 without conversion as a potential mismatch.

- **CRIT-3: Temperature offset operations not handled in `src/unit_checker/core/unit_algebra.py`.** The tool treats temperature (K) as a standard base dimension with normal algebraic rules, which is incorrect for absolute temperatures. Add a `kind` tag (e.g., `"absolute_temperature"` vs `"temperature_difference"`) to temperature unit vectors. Flag addition of two absolute temperatures as physically meaningless. Allow multiplication of temperature difference by a scalar. Document clearly in the output which temperature operations are checked and which are not.

- **CRIT-4: Radian/steradian registered as dimensionless at `src/unit_checker/core/unit_registry.py:327`.** Codex CONFIRMED at runtime that `rad == 1` and `sr == 1`. The `kind` tag mechanism in `UnitVector` exists for this purpose (mentioned in CLAUDE.md). Implement it: register `rad` as dimensionless with `kind="angle"` and `sr` as dimensionless with `kind="solid_angle"`. Update the addition constraint to require matching `kind` tags when both operands are dimensionless but have different kinds. This catches `angle + pure_ratio` mismatches.

- **CRIT-5: Logarithmic units (dB, Neper) not supported.** Add documentation that logarithmic units are currently unsupported and flag any annotation containing `dB`, `dBm`, `dBW`, `Np`, or `neper` with a clear message: "Logarithmic units (dB, Np) follow different algebraic rules and are not yet supported. Results involving these units may be incorrect." This is a documentation/warning fix rather than a full implementation, but it prevents users from getting silent false negatives.

## CRITICAL Fixes (new from Codex audit)

- **CRIT-6: mypy reports 4 errors including `UnitVector` undefined at `terminal.py:193` and `any` used as type at `commands.py:78`.** These are real type errors that can cause runtime `NameError`. Both audits flagged linting failures; Codex identified 7 mypy errors (4 after deduplication). Fix all:
  - `src/unit_checker/output/terminal.py:193`: Add `from unit_checker.core.unit_algebra import UnitVector` (or use `TYPE_CHECKING` guard). This is also the F821 undefined name from ruff.
  - `src/unit_checker/cli/commands.py:78`: Change return annotation from `any` to `Any` (from `typing`) or the actual return type `IRModule`.
  - `src/unit_checker/parsers/python_parser/parser.py:465`: Fix incompatible type assignment.
  - `src/unit_checker/parsers/python_parser/parser.py:525`: Fix function that does not return a value being used as if it does.

- **CRIT-7: ruff reports 60 errors across src and tests.** Breakdown: 11 F541 (f-string no placeholders), ~35 F401 (unused imports), 4 F841 (unused variables), 1 F821 (undefined name, covered by CRIT-6). The volume indicates no CI lint enforcement. Fix all 60 errors. 55 are auto-fixable.

## HIGH Fixes

- **HIGH-1: `_expand_parenthesized_denominators` does not handle nested parentheses correctly at `src/unit_checker/core/unit_registry.py:143-193`.** The single-pass left-to-right character processing fails on nested patterns like `W/(m^2*(K^4))`. Rewrite the function using recursive descent or repeated application until the string stabilises. Add test cases for: `kg/(m*s^2)`, `W/(m^2*K^4)`, `kg/((m*s)*A)`, `Pa/(kg/(m*s^2))`.

- **HIGH-2: `_to_fraction` uses `limit_denominator(1000)` at `src/unit_checker/core/unit_algebra.py:45`.** This approximation can cause round-trip failures for unusual fractional exponents. Increase the limit to `limit_denominator(10000)` for better precision, and add a validation step: after conversion, check that `abs(float(fraction) - original_float) < 1e-10`. If the approximation is too lossy, fall back to keeping the float and flagging it as "approximate exponent."

- **HIGH-3: Augmented assignment `*=` and `/=` creates self-referencing constraints at `src/unit_checker/inference/constraint_builder.py:241-291`.** For `target *= expr`, the tool creates an impossible constraint when `expr` is not dimensionless. Fix by recognising augmented assignments as creating a NEW effective unit for the variable from that point forward (SSA-like renaming). Create a fresh variable for the post-assignment target and set its unit to `old_target_unit * expr_unit`. Update all subsequent references to `target` to use the new variable.

- **HIGH-4: `enrich_violation` mutates violation objects at `src/unit_checker/inference/conflict_resolver.py:52-63`.** Refactor to return a new `Violation` object with the enriched fields rather than mutating in place. Use `dataclasses.replace(violation, message=new_message, source_line=new_source_line)` if Violation is a dataclass, or create a copy before modification.

- **HIGH-5: 4 B904 raise-without-from-inside-except.** Four locations raise new exceptions inside `except` blocks without preserving the original exception chain (`raise ... from err`). For a developer-facing CLI tool, losing the original traceback makes debugging reported issues much harder.

- **HIGH-6: 3 B905 zip-without-strict.** Three `zip()` calls do not use `strict=True`. If the iterables have different lengths, the extra elements are silently dropped. In a unit analysis tool, this could mean some variables or constraints are silently ignored, leading to missed violations (false negatives).

- **HIGH-7: `unit_definitions/` directory is empty.** The directory contains only `.gitkeep`. Implement at minimum the `si.toml` definitions file by extracting the hardcoded unit definitions from `_build_si_registry()` in `unit_registry.py` into a TOML file. Update the registry to load from the TOML file. Implement a `config.unit_system` check that selects the appropriate definitions file. Create stub files for `cgs.toml` and `natural.toml` with TODO comments for future implementation.

## MEDIUM Fixes

- **MED-1: Python parser does not handle `*args`, `**kwargs`, default arguments, or keyword arguments at `src/unit_checker/parsers/python_parser/parser.py`.** Extend the parser to process `node.args.vararg`, `node.args.kwarg`, `node.args.defaults`, and `node.args.kwonlyargs`. Also update the function call matching in `constraint_builder.py:454` to support keyword arguments in calls, not just positional.

- **MED-2: No support for tuple unpacking at `src/unit_checker/parsers/python_parser/parser.py:310-313`.** The `pass` statement for tuple unpacking skips common patterns like `a, b = f()`. Implement tuple unpacking: infer that each element of the left-hand side receives one component of the function's return type. For unknown functions, create fresh type variables for each element.

- **MED-3: `IfExp` (ternary) only analyzes true branch at `src/unit_checker/parsers/python_parser/parser.py:408-411`.** Analyze both branches and add an equality constraint between them. The ternary `x if cond else y` should have the same unit for both `x` and `y`, and the result should have that unit.

- **MED-4: No `math.atan2` support at `src/unit_checker/inference/constraint_builder.py:527-536`.** Add `math.atan2` (and `numpy.arctan2`) to the list of known functions. Both take two arguments that must have the same unit and produce a dimensionless result (angle).

- **MED-5: Fortran parser does not handle `return` statements at `src/unit_checker/parsers/fortran_parser/parser.py:471`.** Add handling for `return_statement` nodes in `_visit_subprogram_body`. Extract the return expression and create a constraint linking it to the function's result variable.

- **MED-6: `ignore_functions` and `ignore_paths` config are parsed but never used at `src/unit_checker/config/loader.py` and `src/unit_checker/cli/commands.py`.** Wire up the config values: in the parser, skip functions whose names match `config.ignore_functions`. In the CLI, skip files whose paths match any pattern in `config.ignore_paths` using `fnmatch.fnmatch()`.

- **MED-7: Custom units and aliases from config are never applied at `src/unit_checker/config/loader.py`.** Wire up `config.aliases` and `config.custom_units` to the unit registry. After building the default SI registry, iterate through custom units and register each one. For aliases, call `registry.add_alias(alias_name, target_name)`.

- **MED-8: C++ parser does not handle `for` loop initializers at `src/unit_checker/parsers/cpp_parser/parser.py:444`.** Extend `_visit_for_statement` to process the declaration or expression in the for-loop initializer. Variables declared in the for-init (e.g., `for (double dt = 0.01; ...)`) should be parsed and added to the scope with any unit annotations.

- **MED-9: Average cyclomatic complexity is C (13.9).** Refactor the `check_command` function (rated D) by extracting helper functions for distinct phases (config loading, file discovery, parsing, inference, reporting). Also refactor the long `_visit_expression` methods in all three parsers. Run `radon cc src/ -a -nc` to verify improvement.

## LOW Issues (informational)

- **LOW-1: Bandit is clean on the source tree.** No security findings. Both audits confirmed.
- **LOW-2: Unused imports in config/loader.py (`os`), output/terminal.py (`Panel`, `Text`, `Table`).** Covered by CRIT-7 ruff cleanup.
- **LOW-3: 3 unused variables in parsers need review.** Covered by CRIT-7 ruff cleanup (F841 errors).

## VERIFIED CORRECT (both audits agree)

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

After all fixes are implemented, run the complete test suite, confirm zero regressions, update all affected docstrings and README sections, and write new tests for every bug that was fixed. Write a FIXES_APPLIED.md summarising every change made.
