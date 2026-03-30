# CODEX Audit Report: unit-checker
## Date: 2026-03-29
## Stack: Python static analysis for dimensional consistency

---

### 1. CRITICAL Issues

- **C-1: The registry still collapses scale and angle semantics.**
  Runtime checks confirmed `km == m`, `cm == m`, `L == m^3`, `rad == 1`, and `sr == 1`. The source of the collapse is visible in `src/unit_checker/core/unit_registry.py:272-327`, where prefixed units and liter/radian/steradian are registered only by dimension vector.

### 2. HIGH Issues

- No additional high-severity issue exceeded the core scientific defect above during this pass.

### 3. MEDIUM Issues

- **M-1: `mypy .` fails with 7 errors.**
  These include `src/unit_checker/output/terminal.py:193` (`UnitVector` undefined) and `src/unit_checker/cli/commands.py:78` (`any` used as a type).

- **M-2: `ruff check src tests` fails with 60 issues.**
  The current failure set is mostly unused imports/variables and formatting debt, but it indicates the repo is not held to a passing lint baseline.

### 4. LOW Issues

- **L-1: Bandit is clean on the source tree.**

### 5. VERIFIED / CONFIRMED

- `pytest -q` passed: `263 passed`.
- The scale-collapse bug is directly reproducible at runtime, not just inferable from reading the registry.

### 6. Tool Output Summary

| Tool | Result |
|------|--------|
| `pytest -q` | `263 passed` |
| `mypy .` | `7 errors` |
| `ruff check src tests` | `60 errors` |
| `bandit -q -r src/unit_checker` | clean |

### 7. Notes

- The previous audit was correct about the scientific blocker. This pass confirmed it by executing the registry and comparing parsed units directly.
