# CHECKPOINT_0_AUDIT.md -- unit-checker

**Checkpoint:** 0 -- Planning Complete
**Date:** 2026-03-29
**Auditor:** Claude (automated self-audit)
**Gate:** All planning documents exist, no implementation code, tech stack justified.

---

## Audit Results

### 1. CLAUDE.md covers all required sections

**PASS**

Verified sections present:
- [x] Project name, one-line description, and goals
- [x] Tech stack with justification (including type-inference vs constraint-propagation decision with detailed rationale)
- [x] Directory structure overview
- [x] Development philosophy and constraints
- [x] "Do not begin coding until PLANNING.md has been reviewed and approved" (present under CRITICAL CONSTRAINT heading)
- [x] Agent instructions for sub-agent division of work (5 agent roles defined with coordination rules)
- [x] Audit checkpoint schedule (8 checkpoints from 0 to Beta release)
- [x] Known ambiguities and open questions (8 open questions enumerated)
- [x] External dependencies and APIs required (core packages, reference data, future dependencies)
- [x] Skills identified from GitHub search (with URLs for all resources: tree-sitter, pint, CamFort, IKOS, etc.)

### 2. PLANNING.md has a realistic MVP that could be built by one developer

**PASS**

The MVP is scoped to:
- Single Python file analysis only (no multi-file, no C++/Fortran)
- Comment-based annotations only
- SI unit system only (no CGS/natural units)
- Terminal and JSON output only (no SARIF)

The estimated effort is 50 developer-days (~10 weeks), broken down across 13 components with individual estimates ranging from 2-8 days each. This is realistic for a single experienced Python developer. The largest single component (constraint propagator at 8 days) is well-scoped by the detailed algorithm description in Section 4.

The MVP success criteria are concrete and testable:
- 10 benchmark test cases with zero false negatives
- Under 5 seconds for 1000-line files
- pip-installable CLI

### 3. AUDIT_PLAN.md has project-specific (not generic) audit criteria

**PASS**

The audit plan is specific to unit-checker in the following ways:
- [x] Opens with the correctness asymmetry principle: false negatives are worse than false positives, explicitly tied to aerospace mission failure risk
- [x] Contains 10 benchmark test cases based on real physics scenarios (Mars Climate Orbiter reconstruction, velocity-acceleration addition, energy conservation, exponentiation/square root, etc.)
- [x] Each benchmark specifies the exact expected output, not just "should work"
- [x] Checkpoint criteria reference specific module names (unit_algebra.py, Python parser, constraint propagator) and specific behaviors (vector operations on rational numbers, IR node types, provenance tracking)
- [x] Includes adversarial test cases specific to constraint propagation (long chains, diamond dependencies, self-referencing, shadowed variables)
- [x] Mutation testing strategy tailored to unit-checking violations
- [x] Performance targets are domain-specific (1000 variables/second, 80% inference coverage)
- [x] The Mars Climate Orbiter test case is included with the specific technical details (lbf*s vs N*s, factor of 4.45)

### 4. Tech stack choices are justified and optimal

**PASS**

Each major tech choice has an explicit rationale:

| Choice | Justification | Assessment |
|--------|---------------|------------|
| Python 3.11+ | Target users are scientists who use Python; AST analysis is stdlib; ecosystem for tree-sitter/units is mature | Optimal -- matches user base |
| ast (stdlib) for Python parsing | Zero dependency, complete Python grammar support, well-tested | Optimal -- no alternative needed |
| tree-sitter for C++/Fortran | Language-agnostic parsing without full compiler; grammars exist for both languages; Python bindings available | Optimal -- the only viable approach short of full compiler frontends |
| Constraint propagation over type inference | Detailed 2-page evaluation in PLANNING.md Section 5. Constraint propagation maps directly to the physics (units are vectors, operations are vector arithmetic). Type inference requires dependent types for dimensional exponents, produces worse error messages, and is ~3x more implementation effort for no correctness benefit. | Well-justified -- the evaluation considered both approaches fairly |
| Custom constraint engine (not python-constraint/CPMpy) | Problem structure is linear constraints over 7D rational vectors -- much simpler than general CSP. A general solver adds overhead and complexity without benefit. | Justified -- domain-specific solver is appropriate |
| rich for terminal output | Standard Python library for formatted terminal output | Reasonable |
| Rational numbers (fractions.Fraction) for exponents | Needed for fractional exponents (square root = exponent 0.5); exact arithmetic avoids float comparison issues | Optimal -- prevents subtle comparison bugs |

### 5. No implementation code exists anywhere

**PASS**

Verified by scanning all 36 .py files in src/ and tests/. Every file contains only comment lines (lines starting with #). Zero non-comment, non-blank lines found in any source file. The pyproject.toml is also a placeholder with comments only.

File count:
- src/unit_checker/: 28 .py files, all comments-only
- tests/: 8 .py files (including __init__.py files), all comments-only
- .gitkeep files: 7, all contain only a comment line

### 6. All GitHub searches were actually performed

**PASS**

The following searches were performed and results recorded in CLAUDE.md under "Relevant Skills and Resources from GitHub Search":

1. **Python AST analysis / static analysis** -- Found: vintasoftware/python-linters-and-code-analysis, davidfraser/pyan, analysis-tools-dev/static-analysis, isidentical/staticc
2. **tree-sitter C++/Fortran grammars** -- Found: tree-sitter/py-tree-sitter, tree-sitter/tree-sitter-cpp, stadelmanma/tree-sitter-fortran, grantjenks/py-tree-sitter-languages, Goldziher/tree-sitter-language-pack
3. **Unit handling libraries** -- Found: hgrecco/pint, astropy/astropy (units submodule), yt-project/unyt, uibcdf/PyUnitWizard
4. **Existing unit checking tools** -- Found: camfort/camfort (Fortran unit verification), njoy/DimensionalAnalysis (C++ compile-time), NASA-SW-VnV/ikos (C/C++ abstract interpretation)
5. **Constraint propagation libraries** -- Found: python-constraint/python-constraint, CPMpy/cpmpy
6. **CLAUDE.md templates / Claude Code skills** -- Found: hesreallyhim/awesome-claude-code, alirezarezvani/claude-skills, carlrannaberg/cclint
7. **Mars Climate Orbiter details** -- Found: specific technical details of the SM_FORCES software error (lbf*s vs N*s, factor of 4.45)
8. **CamFort deep dive** -- Found: camfort/camfort (Haskell, Fortran-only, units-of-measure inference), camfort/fortran-src (parsing infrastructure), academic papers on Fortran unit inference

All URLs are recorded and accessible.

### 7. CLAUDE_AI_PROJECT_BRIEF.md is complete and self-contained

**PASS**

The document contains:
- [x] Suggested Claude.ai Project name: "unit-checker"
- [x] Suggested Project description (one sentence)
- [x] Full context document suitable for pasting into a Claude.ai Project knowledge base
- [x] Context document covers: what the tool does, why it matters, technical approach, tech stack, competitive landscape, monetisation, project status, key files, design decisions, open questions
- [x] Instructions for the human: step-by-step setup guide for creating the Claude.ai Project
- [x] Recommended first conversations (4 specific prompts)
- [x] Self-contained: a reader with no other context can understand the project from this document alone

---

## Summary

| # | Criterion | Result |
|---|-----------|--------|
| 1 | CLAUDE.md covers all required sections | **PASS** |
| 2 | PLANNING.md has a realistic MVP buildable by one developer | **PASS** |
| 3 | AUDIT_PLAN.md has project-specific audit criteria | **PASS** |
| 4 | Tech stack choices are justified and optimal | **PASS** |
| 5 | No implementation code exists anywhere | **PASS** |
| 6 | All GitHub searches were actually performed | **PASS** |
| 7 | CLAUDE_AI_PROJECT_BRIEF.md is complete and self-contained | **PASS** |

**Overall Checkpoint 0 Result: PASS (7/7)**

---

## Next Steps

1. Human reviews PLANNING.md and resolves the 7 open questions in Section 15.
2. Human approves the constraint propagation approach (Section 5).
3. Human approves the annotation syntax (Section 6).
4. Upon approval, implementation begins with Phase 1 (Core Engine, Weeks 1-4).
5. First coding checkpoint (Checkpoint 1: Unit Algebra Engine) at end of Week 2.
