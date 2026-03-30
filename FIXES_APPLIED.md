# Fixes Applied: unit-checker

## Date: 2026-03-29
## Scope: CRITICAL and linting fixes from merged audit reports

---

## Phase 1: FIX_PROMPT.md Updated

Merged findings from FULL_AUDIT_REPORT.md and CODEX_AUDIT_REPORT.md into a single prioritized FIX_PROMPT.md. Findings confirmed by both audits were elevated to CRITICAL. New Codex findings (mypy errors, ruff errors) were added as CRITICAL items.

---

## Phase 2: Fixes Implemented

### CRIT-1: SI Prefix Scale Factors (scale collapse bug)

**Problem:** All SI-prefixed units (km, cm, mm, mg, ms, kJ, MW, etc.) were registered with the same UnitVector as their base unit. `km == m` at runtime, making the tool unable to detect factor-of-1000 errors.

**Fix:**
- Added `scale_factor: float = 1.0` field to the `UnitVector` frozen dataclass in `src/unit_checker/core/unit_algebra.py`.
- Updated `UnitVector.from_list()` and `UnitVector.dimensionless()` to accept and pass `scale_factor`.
- Updated `multiply()`, `divide()`, and `power()` to propagate scale factors through arithmetic.
- Updated `compatible_with()` to also check scale factor equality.
- Added `scale_compatible_with()` method for scale-only checks.
- Updated `__repr__()` to show scale when not 1.0.
- Rewrote all SI prefix registrations in `_build_si_registry()` at `src/unit_checker/core/unit_registry.py` to include correct scale factors:
  - Length: km=1e3, cm=1e-2, mm=1e-3, um=1e-6, nm=1e-9
  - Mass: g=1e-3, mg=1e-6 (relative to kg)
  - Time: ms=1e-3, us=1e-6, ns=1e-9, min=60, hr=3600
  - Energy: kJ=1e3, MJ=1e6
  - Power: kW=1e3, MW=1e6
  - Force: kN=1e3, MN=1e6, lbf=4.44822
  - Pressure: kPa=1e3, MPa=1e6, GPa=1e9
  - Velocity: km/h=1000/3600
  - Impulse: lbf*s=4.44822
- Updated `UnitRegistry._unit_key()` to use `(dimensions, scale_factor, kind)` tuple for proper name lookup.
- Updated `UnitRegistry.get_name()` to use the full key, so `km` and `m` resolve to different names.

**Files changed:** `src/unit_checker/core/unit_algebra.py`, `src/unit_checker/core/unit_registry.py`

### CRIT-2: Liter Scale Factor

**Problem:** Liter was registered as dimensionally identical to m^3 (`L == m^3`). 1 L = 0.001 m^3.

**Fix:** Registered `L` with `scale_factor=1e-3`. Now `L.dimensions_equal(m^3)` is True but `L.compatible_with(m^3)` is False.

**File changed:** `src/unit_checker/core/unit_registry.py`

### CRIT-3: Temperature Offset Handling

**Problem:** No distinction between absolute temperature and temperature difference. Adding two absolute temperatures is physically meaningless.

**Fix:**
- Registered `degC` and `degF` with `kind="absolute_temperature"`.
- Registered `deltaK` and `deltadegC` with `kind="temperature_difference"`.
- Base `K` (kelvin) retains `kind=None` for backward compatibility -- it can represent either absolute or difference.
- The existing `_kinds_compatible()` method enforces that `absolute_temperature` and `temperature_difference` are incompatible, while `None` is compatible with either.

**File changed:** `src/unit_checker/core/unit_registry.py`

### CRIT-4: Radian/Steradian Kind Tags

**Problem:** `rad`, `radian`, `sr`, `steradian` were aliases for `DIMENSIONLESS`, making angular unit misuse undetectable. Codex confirmed `rad == 1` at runtime.

**Fix:**
- Removed `rad`, `radian`, `radians`, `sr`, `steradian` from dimensionless aliases.
- Registered `rad` as `UnitVector.dimensionless(kind="angle")` with aliases `radian`, `radians`.
- Registered `sr` as `UnitVector.dimensionless(kind="solid_angle")` with aliases `steradian`, `steradians`.
- The propagator's addition evaluator now checks kind compatibility and emits warnings for mismatches.

**File changed:** `src/unit_checker/core/unit_registry.py`

### CRIT-5: Scale/Kind Mismatch Warnings in Propagator

**Problem:** The propagator only checked dimensional equality in addition constraints, ignoring scale factors and kind tags.

**Fix:**
- Added `_scale_warnings` list to `ConstraintPropagator.__init__()`.
- In `_eval_addition()`, after confirming dimensions match, added checks for:
  - Scale factor mismatch: emits WARNING with message about possible conversion needed.
  - Kind tag mismatch: emits WARNING about unit kind incompatibility.
- Scale warnings are appended to `result.violations` before returning.

**File changed:** `src/unit_checker/inference/propagator.py`

### CRIT-6: mypy Errors (4 errors fixed)

1. **`src/unit_checker/output/terminal.py:193`** -- `UnitVector` undefined (also F821 from ruff). Added `from unit_checker.core.unit_algebra import UnitVector` import.
2. **`src/unit_checker/cli/commands.py:78`** -- `any` used as return type. Changed to `IRModule` with proper import.
3. **`src/unit_checker/parsers/python_parser/parser.py:465`** -- Type narrowing issue. Changed `n` from implicit `Attribute` type to explicit `ast.expr` annotation.
4. **`src/unit_checker/parsers/python_parser/parser.py:525`** -- `_find_annotation` return type was `-> None` but used as value. Changed to `-> Optional[UnitVector]` with TYPE_CHECKING import.

**Files changed:** `src/unit_checker/output/terminal.py`, `src/unit_checker/cli/commands.py`, `src/unit_checker/parsers/python_parser/parser.py`

### CRIT-7: ruff Cleanup (61 errors fixed)

All 61 ruff errors resolved:
- 11 F541: Removed extraneous `f` prefix from f-strings with no placeholders.
- ~35 F401: Removed unused imports across `src/` and `tests/` (including `sys`, `os`, `re`, `Panel`, `Text`, `Table`, unused test imports, etc.).
- 4 F841: Removed unused variable assignments (`current_section`, `vel_key`, `param_scope`, `comment_line`).
- 1 F821: Fixed undefined name (covered by CRIT-6 terminal.py fix).

Used `ruff check --fix --unsafe-fixes` for auto-fixable errors.

**Files changed:** 15+ files across `src/` and `tests/`.

### Additional: B905 zip-without-strict

Fixed 2 `zip()` calls in `unit_algebra.py` to use `strict=True`:
- `__repr__()`: `zip(DIMENSION_NAMES, self.to_list(), strict=True)`
- `to_unit_string()`: `zip(DIMENSION_SYMBOLS, dims, strict=True)`

**File changed:** `src/unit_checker/core/unit_algebra.py`

---

## Phase 2: Tests Updated

### Updated Tests (2)
- `tests/unit_tests/test_cpp_parser.py::TestIntegrationMarsClimateOrbiter::test_mco_scale_mismatch_detected` -- Renamed from `test_mco_same_dimensions_no_violation`. Now correctly asserts that lbf*s + N*s produces a scale mismatch WARNING (the actual MCO bug).
- `tests/unit_tests/test_fortran_parser.py::TestIntegrationMarsClimateOrbiter::test_mco_scale_mismatch_detected` -- Same update for Fortran parser test.

### New Tests (29)

**Scale Factor tests (class `TestScaleFactor`, 16 tests):**
- `test_km_has_scale_1000`, `test_m_has_scale_1`
- `test_km_and_m_same_dimensions`, `test_km_and_m_not_compatible`
- `test_liter_has_scale_1e_minus_3`, `test_liter_and_m3_same_dimensions`, `test_liter_and_m3_not_compatible`
- `test_multiply_scales`, `test_divide_scales`, `test_power_scales`
- `test_minute_scale`, `test_hour_scale`, `test_ms_scale`
- `test_g_scale`, `test_mg_scale`, `test_kJ_scale`
- `test_get_name_distinguishes_km_from_m`, `test_get_name_distinguishes_L_from_m3`

**Kind Tag tests (class `TestKindTags`, 13 tests):**
- `test_rad_is_dimensionless_with_angle_kind`, `test_sr_is_dimensionless_with_solid_angle_kind`
- `test_rad_not_equal_to_dimensionless`, `test_rad_not_compatible_with_sr`, `test_rad_compatible_with_rad`
- `test_degC_has_absolute_temperature_kind`, `test_deltaK_has_temperature_difference_kind`
- `test_K_has_no_kind`, `test_degC_not_compatible_with_deltaK`
- `test_kinds_compatible_both_none`, `test_kinds_compatible_one_none`

---

## Verification

| Check | Result |
|-------|--------|
| `pytest -q` | 292 passed, 0 failed |
| `mypy src` | 0 errors (was 4) |
| `ruff check src tests` | 0 errors (was 60+) |
| `km == m` | False (was True) |
| `L == m^3` | False (was True) |
| `rad == dimensionless` | False (was True) |
| MCO lbf*s + N*s | Scale mismatch WARNING detected |

---

## Summary of Scope

| Category | Count |
|----------|-------|
| CRITICAL bugs fixed | 7 |
| Source files modified | ~15 |
| Test files modified | 3 |
| New tests added | 29 |
| Tests updated | 2 |
| Total tests passing | 292 |
| mypy errors eliminated | 4 |
| ruff errors eliminated | 61 |
