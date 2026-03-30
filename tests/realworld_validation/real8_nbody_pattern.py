"""Real-world pattern 8: N-body gravitational simulation pattern.

Simplified version of common N-body simulation code.
Tests force calculation and velocity/position updates.
All physics should be correct.
"""

# Constants
G = 6.674e-11       # unit: m^3/(kg*s^2)
dt = 1.0            # unit: s

# Body 1
m1 = 1.989e30       # unit: kg          -- Sun mass
x1 = 0.0            # unit: m
v1 = 0.0            # unit: m/s

# Body 2
m2 = 5.972e24       # unit: kg          -- Earth mass
x2 = 1.496e11       # unit: m           -- 1 AU
v2 = 29780.0        # unit: m/s

# Distance
dx = x2 - x1        # unit: m
r = abs(dx)          # unit: m (abs preserves unit)

# Gravitational force: F = G * m1 * m2 / r^2
F = G * m1 * m2 / r ** 2  # unit: N

# Accelerations
a1 = F / m1          # unit: m/s^2
a2 = F / m2          # unit: m/s^2

# Velocity updates: v_new = v + a * dt
v1_new = v1 + a1 * dt  # m/s + m/s^2 * s = m/s (correct)
v2_new = v2 - a2 * dt  # m/s - m/s^2 * s = m/s (correct)

# Position updates: x_new = x + v * dt
x1_new = x1 + v1_new * dt  # m + m/s * s = m (correct)
x2_new = x2 + v2_new * dt  # m + m/s * s = m (correct)
