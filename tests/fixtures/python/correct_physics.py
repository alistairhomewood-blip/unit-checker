"""Test fixture: correct physics code with no violations.

Benchmark 1.5 from AUDIT_PLAN.md.
Expected result: Zero violations. All units correctly inferred.
"""

distance = 100.0    # unit: m
time = 10.0         # unit: s
velocity = distance / time              # inferred: m/s (correct)
acceleration = velocity / time          # inferred: m/s^2 (correct)
