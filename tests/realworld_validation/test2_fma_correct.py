"""Synthetic test 2: F = m * a (correct physics, should pass).

Expected: PASS -- no violations. Force correctly inferred as kg*m/s^2 = N.
"""

mass = 10.0          # unit: kg
acceleration = 9.81  # unit: m/s^2

force = mass * acceleration  # Should infer: kg * m/s^2 = N
