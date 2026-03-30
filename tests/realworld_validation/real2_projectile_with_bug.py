"""Real-world pattern 2: Projectile motion with a unit error.

Common beginner physics simulation pattern. Contains a deliberate
error where velocity (m/s) is added to position (m) without
multiplying by time.

Expected: ERROR at the addition of position + velocity.
"""

import numpy as np

# Initial conditions
x0 = 0.0           # unit: m
y0 = 100.0         # unit: m
vx = 50.0          # unit: m/s
vy = 30.0          # unit: m/s
g = 9.81            # unit: m/s^2
dt = 0.01           # unit: s

# Correct update: x = x0 + vx * dt
x_correct = x0 + vx * dt  # m + m/s * s = m + m = m (correct)

# BUG: forgot to multiply by dt
x_buggy = x0 + vx  # m + m/s = DIMENSION ERROR
