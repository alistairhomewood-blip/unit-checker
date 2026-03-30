"""Real-world pattern 7: Cross-function unit inference.

Tests whether unit-checker correctly infers units through function
calls. Defines a kinetic_energy function and calls it with
annotated arguments.

Expected: PASS -- no violations, with units correctly propagated
through function parameters and return values.
"""

def kinetic_energy(mass, velocity):
    """Compute kinetic energy: KE = 0.5 * m * v^2."""
    return 0.5 * mass * velocity ** 2

def momentum(mass, velocity):
    """Compute momentum: p = m * v."""
    return mass * velocity

# Annotated inputs
m = 10.0     # unit: kg
v = 5.0      # unit: m/s

# Function calls -- should infer return types
KE = kinetic_energy(m, v)  # Should infer: kg * (m/s)^2 = J
p = momentum(m, v)         # Should infer: kg * m/s = kg*m/s

# This should be valid: energy + energy
KE2 = kinetic_energy(m, v)
total_KE = KE + KE2  # J + J (correct)

# This should be invalid: energy + momentum
bad_sum = KE + p  # J + kg*m/s = DIMENSION ERROR
