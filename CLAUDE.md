# CLAUDE.md -- unit-checker

## Project Overview

**Name:** unit-checker
**One-line:** Paste any physics/simulation code -- Python, Fortran, C++ -- and get back a full unit consistency analysis with every violation flagged in physics language.
**Status:** Planning phase. No implementation code exists yet.

## Goals

1. Build a static analysis tool that infers physical units across scientific/simulation codebases without executing the code.
2. Flag every unit inconsistency with a human-readable physics-language explanation (not just "type mismatch" -- say "you are adding a velocity [m/s] to an acceleration [m/s^2]").
3. Support Python (via AST), C++ (via tree-sitter), and Fortran (via tree-sitter) -- in that priority order.
4. Operate as a CLI tool first, then extend to a VSCode plugin and CI/CD API.

## Core User

Scientists, simulation engineers, aerospace engineers, and national lab researchers who write physics and simulation code in Python, Fortran, and C++.

## Tech Stack

### Language and Runtime
- **Python 3.11+** -- core analysis engine, CLI, and API server.
- **Rationale:** Python is the lingua franca of the scientific computing community (the target user). AST analysis of Python code is trivially done with the stdlib `ast` module. The ecosystem for tree-sitter bindings, unit libraries, and constraint solvers is mature in Python.

### Parsing
- **Python AST** (`ast` stdlib module) -- for analyzing Python source code. No external dependency needed.
- **tree-sitter** (`py-tree-sitter`) -- for parsing C++ and Fortran without needing a full compiler toolchain.
  - C++ grammar: `tree-sitter-cpp` (https://github.com/tree-sitter/tree-sitter-cpp)
  - Fortran grammar: `tree-sitter-fortran` (https://github.com/stadelmanma/tree-sitter-fortran)
  - Fixed-form Fortran: `tree-sitter-fixed-form-fortran` (https://github.com/stadelmanma/tree-sitter-fixed-form-fortran)
  - Python wheels: `py-tree-sitter-languages` (https://github.com/grantjenks/py-tree-sitter-languages)

### Unit Representation (internal)
- Custom unit algebra engine built from scratch. We do NOT use pint/astropy.units/unyt at runtime -- those are runtime unit-tracking libraries, not static analysis tools. However, we will:
  - Reference pint's unit definition files for canonical unit names and conversion factors.
  - Study astropy.units equivalencies model for handling non-obvious conversions (e.g., spectral units).
  - Use UDUNITS-2 XML database as a secondary reference for unit definitions.

### Inference Engine: Constraint Propagation (chosen over Type Inference)
- **Decision:** Constraint propagation, not Hindley-Milner-style type inference.
- **Rationale:**
  - Unit checking is not a type system problem -- it is a constraint satisfaction problem over a 7-dimensional vector space (the SI base dimensions: length, mass, time, current, temperature, amount, luminosity).
  - Each variable's unit is a vector in this space. Multiplication adds vectors; division subtracts them; addition/subtraction requires equality. This maps naturally to linear constraints.
  - Constraint propagation handles partial annotations gracefully: the user annotates a few entry-point variables, and constraints propagate through assignments and expressions to infer the rest.
  - Type inference (Hindley-Milner) would require encoding unit algebra into a type system, which is awkward for dimensional exponents (you end up needing dependent types or type-level naturals).
  - Constraint propagation also makes it trivial to report "why" a violation occurred: the constraint solver can emit the propagation chain that led to the conflict.
- **Library:** Custom constraint propagation engine (not a general CSP solver). The problem structure is highly specific (linear constraints over rational-valued vectors), so a general solver like python-constraint would be overkill and slower.
- **Fallback consideration:** If constraint propagation alone is insufficient for handling polymorphic functions (e.g., a generic `multiply(a, b)` that preserves unit relationships), we may layer a limited form of parametric inference on top. This is an open question -- see PLANNING.md.

### CLI Framework
- **click** or **typer** -- standard Python CLI frameworks. Decision deferred to implementation.

### Testing
- **pytest** -- standard.
- **hypothesis** -- property-based testing for the unit algebra engine.

### Future (not MVP)
- VSCode extension (Language Server Protocol).
- REST API for CI/CD integration.
- GitHub Action / GitLab CI template.

## Directory Structure Overview

```
unit-checker/
  CLAUDE.md                  # This file
  PLANNING.md                # Detailed technical plan
  AUDIT_PLAN.md              # Audit criteria and schedule
  CLAUDE_AI_PROJECT_BRIEF.md # Context document for Claude.ai Project
  CHECKPOINT_0_AUDIT.md      # Planning phase audit
  src/
    unit_checker/
      __init__.py
      cli/                   # CLI entry point and commands
      core/                  # Unit algebra, constraint engine, violation reporting
      parsers/               # Language-specific parsers (Python AST, tree-sitter)
      inference/             # Constraint propagation engine
      models/                # Data models (units, variables, constraints, violations)
      output/                # Report formatters (terminal, JSON, SARIF)
      config/                # Configuration and unit definition loading
  tests/
    unit_tests/              # Fast isolated tests
    integration_tests/       # End-to-end tests on sample code
    benchmark_suite/         # Known-buggy codes for correctness validation
    fixtures/                # Sample code files in Python, C++, Fortran
  docs/
    architecture/            # Architecture decision records
    user_guide/              # Usage documentation
  benchmarks/                # Performance benchmarks
  unit_definitions/          # Unit definition files (SI, CGS, natural, custom)
  examples/                  # Example annotated codes for users
```

## Development Philosophy and Constraints

1. **Correctness over performance.** A missed unit violation (false negative) in aerospace code can cause mission failure. Performance optimization comes after correctness is proven.
2. **No runtime execution.** This is a static analysis tool. It must never execute user code.
3. **Graceful degradation.** If the tool cannot infer a variable's unit, it should say "unknown" rather than guess. Explicit uncertainty is better than silent wrong answers.
4. **Physics language, not compiler language.** Error messages must speak the language of the user: "velocity [m/s] added to acceleration [m/s^2]" not "incompatible types T1 and T2".
5. **Annotation-light.** The user should need to annotate only entry-point variables (function parameters, constants). Everything else should be inferred.
6. **Multi-language from day one in architecture, Python-first in implementation.** The parser layer is abstracted so adding C++ and Fortran does not require rewriting the inference engine.

## CRITICAL CONSTRAINT

**Do not begin coding until PLANNING.md has been reviewed and approved by a human.**

All files in `src/` and `tests/` must remain empty placeholders (comments only, no implementation code) until planning approval is granted.

## Agent Instructions for Sub-Agent Division of Work

When working on this project with multiple agents or sub-agents, divide work as follows:

### Agent Roles
1. **Architecture Agent** -- Owns PLANNING.md, data models, and interface definitions. Makes all decisions about the constraint propagation algorithm and unit representation. Must approve any changes to `src/unit_checker/core/` or `src/unit_checker/inference/`.
2. **Parser Agent** -- Owns `src/unit_checker/parsers/`. Responsible for extracting variable declarations, assignments, expressions, and function signatures from each supported language. Must produce a language-independent intermediate representation (IR) that the inference engine consumes.
3. **Inference Agent** -- Owns `src/unit_checker/inference/`. Implements the constraint propagation engine. Must work exclusively with the IR -- never with language-specific AST nodes.
4. **Output Agent** -- Owns `src/unit_checker/output/` and `src/unit_checker/cli/`. Responsible for formatting violation reports and CLI UX.
5. **Test Agent** -- Owns `tests/`. Responsible for benchmark suite curation, fixture creation, and test coverage. Must independently verify correctness claims.

### Coordination Rules
- No agent may modify another agent's owned directories without explicit approval.
- All agents share `src/unit_checker/models/` -- changes there require Architecture Agent approval.
- The IR (intermediate representation) definition is the contract between Parser Agent and Inference Agent. Changes require both to agree.
- Test Agent has read access to all directories and may file issues against any agent.

## Audit Checkpoint Schedule

| Checkpoint | Gate | Criteria |
|------------|------|----------|
| 0 | Planning complete | All planning docs exist, no code, tech stack justified |
| 1 | Unit algebra engine | Can represent, multiply, divide, compare units correctly |
| 2 | Python parser | Can extract variables, assignments, expressions from Python |
| 3 | Constraint propagation MVP | Can infer units through a 20-line Python function |
| 4 | CLI MVP | User can run `unit-checker file.py` and get a report |
| 5 | C++ parser | tree-sitter C++ parser produces valid IR |
| 6 | Fortran parser | tree-sitter Fortran parser produces valid IR |
| 7 | Benchmark suite passes | All known-buggy codes correctly flagged |
| 8 | Beta release | CLI polished, docs written, packaging complete |

## Known Ambiguities and Open Questions

1. **Dimensionless numbers and ratios.** How do we handle quantities like Reynolds number, Mach number, strain, or angles (radians vs degrees)? They are dimensionless but not interchangeable. Possible approach: "kind" tags on dimensionless quantities.
2. **Unit systems.** When a codebase uses CGS internally, how does the user declare this? Global config? Per-file annotation? Per-function?
3. **Polymorphic functions.** A function like `def scale(x, factor)` where `factor` is dimensionless and `x` can be any unit -- how does constraint propagation handle this without parametric polymorphism?
4. **Array indexing.** `velocity[i]` should have the same unit as `velocity`. But what about `matrix[i][j]` where the matrix represents a transformation? Is this out of scope for MVP?
5. **Constants.** `9.81` is probably gravitational acceleration in m/s^2, but could be anything. Do we maintain a database of common physics constants? Or require explicit annotation?
6. **Implicit conversions.** Some codebases convert units inline: `x_km = x_m / 1000.0`. Can we detect this pattern? Should we?
7. **Cross-function inference.** If `def get_velocity(): return distance / time`, the return type's unit depends on the units of `distance` and `time`, which may be defined in a different function or module. How deep does inter-procedural analysis go?
8. **Annotation syntax.** What is the annotation format? Python type hints (`velocity: float # unit: m/s`)? Decorators? Config file? All three?

## External Dependencies and APIs Required

### Python Packages (core)
- `ast` (stdlib) -- Python source parsing
- `py-tree-sitter` -- C++/Fortran parsing (https://github.com/tree-sitter/py-tree-sitter)
- `tree-sitter-cpp` -- C++ grammar
- `tree-sitter-fortran` -- Fortran grammar
- `click` or `typer` -- CLI framework
- `rich` -- Terminal output formatting
- `pytest` -- Testing
- `hypothesis` -- Property-based testing

### Reference Data (not runtime dependencies)
- **pint unit definitions** (https://github.com/hgrecco/pint) -- reference for canonical unit names
- **UDUNITS-2 XML** (https://www.unidata.ucar.edu/software/udunits/) -- secondary unit reference
- **NIST constants database** -- for recognizing numeric constants

### Future Dependencies
- `lsprotocol` / `pygls` -- Language Server Protocol for VSCode extension
- `fastapi` -- REST API server for CI/CD integration

## Relevant Skills and Resources from GitHub Search

### Static Analysis and AST
- Python linters and code analysis curated list: https://github.com/vintasoftware/python-linters-and-code-analysis
- Static analysis tools list: https://github.com/analysis-tools-dev/static-analysis
- pyan (Python call graph analysis): https://github.com/davidfraser/pyan

### Tree-Sitter Ecosystem
- py-tree-sitter (Python bindings): https://github.com/tree-sitter/py-tree-sitter
- tree-sitter-cpp: https://github.com/tree-sitter/tree-sitter-cpp
- tree-sitter-fortran: https://github.com/stadelmanma/tree-sitter-fortran
- py-tree-sitter-languages (binary wheels): https://github.com/grantjenks/py-tree-sitter-languages
- tree-sitter language pack: https://github.com/Goldziher/tree-sitter-language-pack

### Unit Libraries (reference, not dependencies)
- pint: https://github.com/hgrecco/pint
- astropy.units: https://github.com/astropy/astropy (submodule astropy.units)
- unyt: https://github.com/yt-project/unyt
- pyunitwizard: https://github.com/uibcdf/PyUnitWizard

### Existing Unit Analysis Tools (competitive landscape)
- CamFort (Fortran unit verification): https://github.com/camfort/camfort -- the closest existing tool. Haskell-based, Fortran-only, academic project from Cambridge/Kent. Supports units-of-measure inference via annotation. Key differentiation: CamFort is Fortran-only and requires Haskell; unit-checker targets Python/C++/Fortran with a Python-native tool.
- fortran-src (Fortran parsing infrastructure): https://github.com/camfort/fortran-src
- njoy/DimensionalAnalysis (C++ compile-time): https://github.com/njoy/DimensionalAnalysis -- C++ header-only, compile-time. Requires modifying source code to use special types. Key differentiation: unit-checker works on existing code without modification.
- NASA IKOS (C/C++ abstract interpretation): https://github.com/NASA-SW-VnV/ikos -- general static analyzer, not unit-specific. But relevant as a reference for how NASA approaches static analysis.

### Constraint Propagation Libraries
- python-constraint: https://github.com/python-constraint/python-constraint
- CPMpy: https://github.com/CPMpy/cpmpy

### Claude Code Skills and Configuration
- awesome-claude-code: https://github.com/hesreallyhim/awesome-claude-code
- claude-skills collection: https://github.com/alirezarezvani/claude-skills
- cclint (CLAUDE.md linter): https://github.com/carlrannaberg/cclint
- Trail of Bits security skills (reference for static analysis skill design)

### Historical Reference
- Mars Climate Orbiter unit error: Lockheed Martin's SM_FORCES software output thrust data in pound-force-seconds; NASA's trajectory software expected newton-seconds. Factor of 4.45 error. $327.6M mission loss. This is the canonical test case for our benchmark suite.
