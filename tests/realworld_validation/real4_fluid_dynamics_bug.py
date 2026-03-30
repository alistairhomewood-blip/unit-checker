"""Real-world pattern 4: Bernoulli equation with a unit bug.

Bernoulli's equation: P + 0.5*rho*v^2 + rho*g*h = constant
Each term should have units of Pa (pressure).

Contains a deliberate bug where density (kg/m^3) is used where
pressure should be, in an addition.

Expected: ERROR when adding pressure to density.
"""

# Fluid properties (water)
rho = 1000.0        # unit: kg/m^3
P_atm = 101325.0    # unit: Pa

# Flow parameters
v = 5.0             # unit: m/s
g = 9.81            # unit: m/s^2
h = 10.0            # unit: m

# Dynamic pressure: 0.5 * rho * v^2
P_dynamic = 0.5 * rho * v ** 2  # kg/m^3 * (m/s)^2 = kg/(m*s^2) = Pa (correct)

# Hydrostatic pressure: rho * g * h
P_hydrostatic = rho * g * h  # kg/m^3 * m/s^2 * m = kg/(m*s^2) = Pa (correct)

# Bernoulli: P_total = P_atm + P_dynamic + P_hydrostatic
P_total = P_atm + P_dynamic + P_hydrostatic  # Pa + Pa + Pa (correct)

# BUG: someone accidentally uses density instead of pressure
P_wrong = P_atm + rho  # Pa + kg/m^3 = DIMENSION ERROR
