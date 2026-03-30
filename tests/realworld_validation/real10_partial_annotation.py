"""Real-world pattern 10: Partially annotated code.

Only some variables are annotated. Tests whether the propagation
engine correctly infers the rest. The tool should propagate
from the few annotated variables and catch a downstream error.

Expected: ERROR at the final addition (mixing energy with force).
"""

# Only annotate input parameters
mass = 5.0           # unit: kg
height = 20.0        # unit: m

# These should be inferred by propagation
g = 9.81             # unit: m/s^2

# Potential energy (inferred as J through propagation)
PE = mass * g * height

# Force (inferred as N through propagation)
F = mass * g

# BUG: adding energy (J = kg*m^2/s^2) to force (N = kg*m/s^2)
wrong = PE + F  # J + N = DIMENSION ERROR
