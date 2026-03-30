# Claude.ai Project Brief: unit-checker

## Suggested Claude.ai Project Setup

**Project Name:** unit-checker
**Project Description:** Static analysis tool that checks physical unit consistency across Python, C++, and Fortran scientific/simulation code without executing it. Uses constraint propagation over dimensional vectors to infer units from sparse annotations and flag every violation in physics language.

---

## Full Context Document

Paste everything below this line into the Claude.ai Project's knowledge base as a single document.

---

### What is unit-checker?

unit-checker is a static analysis tool for scientific and simulation code. Given source code in Python, Fortran, or C++, it:

1. Parses the code without executing it.
2. Identifies variables that represent physical quantities.
3. Infers the physical units of each variable using constraint propagation (the user annotates a few entry-point variables; the tool infers the rest).
4. Flags every location where units are inconsistent (e.g., adding meters to seconds, assigning velocity to an acceleration variable).
5. Reports violations in physics language: "Line 42: adding velocity [m/s] to acceleration [m/s^2]" -- not "type mismatch."

### Why does this matter?

The canonical example is the Mars Climate Orbiter ($327.6M loss) where Lockheed Martin's software output thrust data in pound-force-seconds while NASA's trajectory software expected newton-seconds. A static unit checker would have caught this before the code ever ran.

More broadly: every physics simulation, every aerospace calculation, every CFD code has implicit unit conventions. Errors in these conventions are silent (the code runs fine, the numbers are just wrong) and catastrophic (wrong trajectory, wrong structural load, wrong dosimetry).

### Core Technical Approach

**Constraint propagation over a 7-dimensional vector space.**

Every physical unit can be represented as a vector of exponents over the 7 SI base dimensions:
- Length (L), Mass (M), Time (T), Electric Current (I), Temperature (Theta), Amount of Substance (N), Luminous Intensity (J)

Examples:
- Velocity = [1, 0, -1, 0, 0, 0, 0] (L/T = m/s)
- Force = [1, 1, -2, 0, 0, 0, 0] (MLT^-2 = kg*m/s^2)
- Energy = [2, 1, -2, 0, 0, 0, 0] (ML^2T^-2 = kg*m^2/s^2)

Arithmetic operations map to vector operations:
- Multiplication: vector addition (velocity * time = [1,0,-1] + [0,0,1] = [1,0,0] = length)
- Division: vector subtraction
- Addition/subtraction: vectors must be equal (can only add same-dimension quantities)
- Exponentiation: scalar multiplication of vector

The tool:
1. Parses source code into a language-independent intermediate representation (IR).
2. Builds a constraint graph from the IR (each assignment, expression, function call generates constraints).
3. Seeds the graph with known units from user annotations.
4. Propagates constraints until fixed point or contradiction.
5. Reports contradictions as unit violations with the full propagation chain.

### Tech Stack

- **Python 3.11+** as the implementation language
- **ast** (stdlib) for Python source parsing
- **tree-sitter** (py-tree-sitter) for C++ and Fortran parsing
- **Custom constraint propagation engine** (not a general CSP solver -- the problem structure is linear constraints over rational vectors, which is much simpler and faster than general CSP)
- **rich** for terminal output
- **click/typer** for CLI

### Why Constraint Propagation, Not Type Inference?

We chose constraint propagation over Hindley-Milner-style type inference because:
1. Units are vectors in a well-defined 7D space, not abstract types. The problem is inherently numerical/algebraic, not type-theoretic.
2. Constraint propagation naturally handles partial information (sparse annotations).
3. Constraint propagation provides built-in "why" explanations: the propagation chain IS the explanation.
4. Type inference requires encoding dimensional exponents into a type system, which needs dependent types or type-level arithmetic -- dramatically more complex for no benefit.

### Competitive Landscape

- **pint / astropy.units / unyt**: Runtime unit-tracking libraries. They require modifying source code to use special Quantity types. unit-checker works on existing, unmodified code.
- **CamFort**: Academic tool from Cambridge/Kent. Fortran-only, Haskell-based. Closest competitor. Differentiators: unit-checker supports Python and C++ too, is Python-native (easier for target users to install and extend), and targets a CLI/CI/CD workflow rather than batch verification.
- **njoy/DimensionalAnalysis**: C++ header-only, compile-time. Requires rewriting code to use special types. unit-checker works on existing code.
- **mypy / pyright**: Python type checkers. They check Python types, not physical units. Complementary, not competitive.

### Monetisation

- **Open source CLI** -- free, drives adoption
- **Paid VSCode plugin** -- real-time checking, inline annotations, quick-fix suggestions
- **Paid CI/CD API** -- flag unit errors in pull requests automatically, integrates with GitHub Actions / GitLab CI
- **B2B licensing** -- aerospace companies, national labs, simulation software vendors

### Project Status

Planning phase. All planning documents (CLAUDE.md, PLANNING.md, AUDIT_PLAN.md) are complete. No implementation code exists yet. The directory scaffold is in place with placeholder files.

### Key Files

- `CLAUDE.md` -- Master project document with tech stack, architecture, agent instructions
- `PLANNING.md` -- Detailed technical plan including algorithm design, data models, API surface, phase breakdown
- `AUDIT_PLAN.md` -- Correctness-focused audit criteria and benchmark suite plan
- `src/unit_checker/` -- Source code (currently placeholders only)
- `tests/` -- Test suite (currently placeholders only)
- `unit_definitions/` -- Unit definition files (to be created)

### Key Design Decisions

1. **Correctness over performance.** False negatives (missed violations) are worse than false positives. The tool must be conservative: if in doubt, flag it.
2. **Physics language, not compiler language.** Errors speak the user's domain language.
3. **Annotation-light.** Users annotate entry points only; everything else is inferred.
4. **Multi-language from day one in architecture.** Parser layer is abstracted behind an IR. Adding a new language means writing one new parser, not changing the inference engine.
5. **No runtime execution.** Pure static analysis. Never runs user code.

### Open Questions

1. How to handle dimensionless numbers with distinct physical meaning (Reynolds number vs Mach number vs strain)?
2. How to handle polymorphic functions where unit relationships are parametric?
3. What annotation syntax to use (Python type hints, comments, config files, or all three)?
4. How deep to go with inter-procedural analysis (cross-function, cross-module)?
5. How to detect implicit inline unit conversions (e.g., `x_km = x_m / 1000.0`)?

---

## Instructions for the Human

### Setting Up the Claude.ai Project

1. Go to Claude.ai and create a new Project.
2. Set the **Project Name** to: `unit-checker`
3. Set the **Project Description** to: `Static analysis tool that checks physical unit consistency across Python, C++, and Fortran scientific/simulation code without executing it.`
4. In the Project Knowledge section, upload or paste the full context document above (everything between the two `---` markers).
5. Optionally, also upload these files from the project directory for additional context:
   - `CLAUDE.md`
   - `PLANNING.md`
   - `AUDIT_PLAN.md`

### Using the Project

When you start a conversation in this project, Claude will have full context about:
- The technical approach (constraint propagation over dimensional vectors)
- The competitive landscape and differentiation
- The tech stack and rationale
- The directory structure and module responsibilities
- The open questions and design decisions

You can ask Claude to:
- Help design specific algorithms (e.g., "Design the constraint propagation loop for handling function calls")
- Review architecture decisions
- Draft unit definition file formats
- Design the annotation syntax
- Plan the VSCode extension architecture
- Write test cases for the benchmark suite
- Discuss edge cases (dimensionless numbers, polymorphic functions, etc.)

### Important Constraint

**Do not ask Claude to write implementation code until PLANNING.md has been reviewed and approved.** The planning documents establish the contracts between modules. Coding before the plan is approved risks building on a shaky foundation.

### Recommended First Conversations

1. "Review the constraint propagation approach in PLANNING.md. Are there any edge cases I am missing?"
2. "Help me design the annotation syntax. I want something that works in Python type hints, C++ comments, and Fortran comments."
3. "Design a minimal benchmark suite: 10 test cases that cover the most important unit error patterns."
4. "Review the data model for the intermediate representation. Is it expressive enough for all three languages?"
