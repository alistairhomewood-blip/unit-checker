"""Real-world pattern 5: Spring-mass-damper system.

Models the equation of motion: m*a + c*v + k*x = F
where all terms should have units of force (N).

Contains a correct implementation with function calls.
No violations expected.
"""

# System parameters
m = 2.0             # unit: kg
k = 100.0           # unit: N/m
c = 10.0            # unit: N*s/m

# State variables
x = 0.05            # unit: m
v = 0.1             # unit: m/s

# External force
F_ext = 5.0         # unit: N

# Spring force: F_spring = k * x
F_spring = k * x  # N/m * m = N (correct)

# Damping force: F_damp = c * v
F_damp = c * v  # N*s/m * m/s = N (correct)

# Net force: F_net = F_ext - F_spring - F_damp
F_net = F_ext - F_spring - F_damp  # N - N - N = N (correct)

# Acceleration: a = F_net / m
a = F_net / m  # N / kg = m/s^2 (correct)
