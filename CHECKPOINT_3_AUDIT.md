# Checkpoint 3 Audit: Constraint Propagation MVP

**Date:** 2026-03-29
**Status:** PASS

## Criteria Results

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| 3.1 | Forward propagation | PASS | Annotated m propagates through x->y->z chain |
| 3.2 | Backward propagation | PASS | distance/time infers velocity as m/s |
| 3.3 | Addition constraint | PASS | c = a + b with known a infers b, c same units |
| 3.4 | Multiplication constraint | PASS | mass * velocity -> kg*m/s |
| 3.5 | Division constraint | PASS | distance / time -> m/s |
| 3.6 | Violation detection | PASS | Conflicting dimensions produce Violation |
| 3.7 | Provenance tracking | PASS | Provenance chain stored for each inference |
| 3.8 | Fixed-point convergence | PASS | 25-variable chain converges correctly |
| 3.9 | Benchmark 1.2 | PASS | Velocity + acceleration mismatch flagged |
| 3.10 | Benchmark 1.5 | PASS | Correct physics code: 0 violations |
| 3.11 | Benchmark 1.10 | PASS | Multi-operation energy expressions correct |

## Test Coverage

14 unit tests in `tests/unit_tests/test_propagation.py`, all passing.
29 integration tests in `tests/integration_tests/test_benchmarks.py`, all passing.

## All 10 Benchmarks

| Benchmark | Description | Violations Expected | Result |
|-----------|-------------|-------------------|--------|
| 1.1 | Mars Climate Orbiter (simplified) | >= 1 | PASS |
| 1.2 | Velocity + acceleration | >= 1 | PASS |
| 1.3 | Wrong force formula | >= 1 | PASS |
| 1.4 | Energy conservation error | >= 1 | PASS |
| 1.5 | Correct code | 0 | PASS |
| 1.6 | Function call propagation | 0 | PASS |
| 1.7 | Exponentiation and sqrt | >= 1 (area + length) | PASS |
| 1.8 | Dimensionless ratio | 0 | PASS |
| 1.9 | Assignment chain | 0 | PASS |
| 1.10 | Multi-operation expression | 0 (correct), >= 1 (bad) | PASS |

## Implementation Files

- `src/unit_checker/inference/constraint_builder.py` -- IR -> constraints
- `src/unit_checker/inference/propagator.py` -- worklist algorithm
- `src/unit_checker/inference/conflict_resolver.py` -- violation enrichment
- `src/unit_checker/models/constraints.py` -- constraint types
- `src/unit_checker/models/violations.py` -- violation model
