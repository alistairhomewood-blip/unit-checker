---
title: 'unit-checker: Static Dimensional Analysis for Scientific Code in Python, C++, and Fortran'
tags:
  - Python
  - dimensional analysis
  - static analysis
  - units of measure
  - scientific computing
  - constraint propagation
authors:
  - name: Alistair Homewood
    orcid: 0009-0004-8005-3571
    affiliation: 1
affiliations:
  - name: University of British Columbia, Vancouver, Canada
    index: 1
date: 29 March 2026
bibliography: paper.bib
---

# Summary

`unit-checker` is a static analysis tool that infers physical units in scientific code and flags dimensional inconsistencies without executing the code. The user annotates a small number of entry-point variables (function parameters, physical constants) with their units via inline comments, and the tool propagates unit information through assignments, arithmetic, and function calls using constraint propagation over SI base dimension vectors. Violations are reported in physics language---for example, "cannot add velocity [m/s] to acceleration [m/s^2]"---with source locations and inference chains showing how each unit was derived.

`unit-checker` supports Python (via the `ast` standard library module), C++ (via tree-sitter [@brunsfeld_treesitter]), and Fortran (via tree-sitter), with all three languages producing a common intermediate representation consumed by a single inference engine. Output formats include Rich-formatted terminal reports, JSON, and SARIF 2.1.0 for integration with CI/CD pipelines and GitHub Code Scanning. The tool is available as a `pip`-installable Python package with a CLI interface.

# Statement of Need

Dimensional errors in scientific code are a well-documented source of costly failures. The loss of the Mars Climate Orbiter in 1999---caused by one software module outputting thrust in pound-force-seconds while another expected newton-seconds---remains the canonical example of a unit error with catastrophic consequences [@stephenson1999mco]. Less dramatic but equally problematic unit errors are common in computational physics, aerospace engineering, and climate modeling, where code is often written by domain scientists rather than software engineers and may lack the type safety infrastructure of production software.

Existing approaches to unit safety fall into three categories, none of which fully addresses the needs of working scientists. **Runtime unit-tracking libraries** such as pint [@grecco_pint], astropy.units [@astropy2013; @astropy2018], and unyt [@goldbaum2018unyt] attach unit metadata to values at runtime, catching errors dynamically. These libraries are effective but require rewriting existing code to use their special types, impose runtime performance overhead, and cannot analyze code before it runs. **Compile-time dimensional analysis** for C++ (e.g., njoy/DimensionalAnalysis [@njoy_dimensional_analysis]) provides zero-overhead checking but similarly requires modifying source code to use template-based unit types, and is limited to a single language. **Static analysis** of units has been explored most thoroughly by CamFort [@contrastin2016units; @orchard2015evolving], which infers and verifies units of measure in Fortran programs. CamFort is the closest prior work to `unit-checker`, but it supports only Fortran, is implemented in Haskell (creating a deployment barrier for the Python-dominant scientific computing community), and does not support Python or C++.

The theoretical foundations for units of measure in programming languages were established by Kennedy [@kennedy1997relational; @kennedy2010types], who developed type systems for dimensional analysis in F#. `unit-checker` takes a different approach: rather than encoding units in a type system (which requires dependent types or type-level integers to express dimensional exponents), it models the problem as constraint propagation over a 7-dimensional rational vector space corresponding to the SI base dimensions. This approach handles partial annotations naturally, produces explanatory inference chains for error messages, and avoids the complexity of building a full type inference engine.

`unit-checker` fills the gap of a **multi-language, static, annotation-light** unit analysis tool that works on existing scientific code without requiring source modification beyond lightweight comments.

# Implementation

## Unit Representation

Physical units are represented as 7-dimensional vectors corresponding to the SI base dimensions (length, mass, time, electric current, temperature, amount of substance, luminous intensity). Each vector element is a rational number representing the dimensional exponent. Multiplication adds vectors; division subtracts them; exponentiation scales them. An additional scale factor field tracks metric prefixes (km = 1000 m) and non-SI units (lbf = 4.44822 N), and an optional kind tag distinguishes dimensionless quantities that are not interchangeable (e.g., radians vs. steradians, absolute temperature vs. temperature difference).

## Constraint Propagation

The inference engine builds a constraint graph from the parsed intermediate representation. Each arithmetic operation generates constraints: addition and subtraction require operands to have equal dimension vectors; multiplication and division produce product and quotient vectors; exponentiation scales the vector by the exponent. A worklist algorithm propagates known units (from annotations) through the graph until a fixed point is reached. When propagation produces a conflict---two different unit vectors assigned to the same variable---a violation is recorded along with the full provenance chain tracing back to the original annotations.

## Multi-Language Parsing

Each supported language has a dedicated parser that produces a language-independent intermediate representation (IR). The Python parser uses the `ast` standard library module; the C++ and Fortran parsers use tree-sitter grammars [@brunsfeld_treesitter]. The IR captures assignments, arithmetic expressions, function definitions, function calls, and return statements, each annotated with source locations. The inference engine operates exclusively on the IR and is language-agnostic.

## Scale and Kind Checking

Beyond dimensional equality, `unit-checker` detects scale-factor mismatches in addition and subtraction operations. When operands have the same dimensions but different scale factors (e.g., lbf\*s and N\*s), a warning is emitted identifying the scale discrepancy. This directly addresses the class of error that caused the Mars Climate Orbiter failure. Kind tags provide additional checking for dimensionless quantities: radians and steradians are distinguished from pure dimensionless numbers, and absolute temperatures are distinguished from temperature differences.

# Real-World Validation

`unit-checker` was validated on a suite of 18 test files comprising 5 synthetic benchmarks and 13 realistic scientific code patterns drawn from orbital mechanics, fluid dynamics, heat transfer, electromagnetism, wave physics, rocket propulsion, N-body simulation, and spring-mass systems. A total of 290 variables were analyzed, with 278 units successfully inferred (96% inference coverage across all files; 98.4% for annotated files).

The tool achieved a **100% detection rate** for dimensional errors (all planted bugs detected) and a **0% false positive rate** (no correct code wrongly flagged) across the 18-file test suite. Detected errors included: adding position to velocity (missing `*dt`), adding pressure to density in a Bernoulli equation, adding electric and magnetic field quantities with incompatible dimensions, cross-function unit conflicts propagated through return values, energy-force confusion with partial annotations, and specific impulse confusion in a rocket equation. The Mars Climate Orbiter scenario (lbf\*s added to N\*s) was correctly detected as a scale-factor mismatch with the precise conversion factor of 4.44822 reported in the warning.

All 292 unit tests pass, and the tool produces valid SARIF 2.1.0 output suitable for CI/CD integration.

Known limitations include: scale-factor mismatches in multiplication and division (as opposed to addition) are not currently flagged, and the tool requires at least some unit annotations to begin inference. Completely unannotated code degrades gracefully, producing no false violations and clearly reporting which variables could not be inferred.

# Acknowledgements

This work was supported by the University of British Columbia. The author thanks his time at PARSEC for providing motivating use cases, particularly regarding PULCEIC's active radiation shielding project.

# References
