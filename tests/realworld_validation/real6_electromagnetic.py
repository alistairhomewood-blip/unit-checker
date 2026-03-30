"""Real-world pattern 6: Electromagnetic force calculation.

Computes the Lorentz force F = q*(E + v x B) in one dimension.
Contains a deliberate bug: electric field is added to magnetic field
directly without proper cross product with velocity.

Expected: ERROR when adding V/m (electric field) to T (magnetic field).
"""

# Particle properties
q = 1.6e-19         # unit: C        -- elementary charge
m = 9.109e-31       # unit: kg       -- electron mass

# Fields
E = 1000.0          # unit: V/m      -- electric field  (N/C = V/m)
B = 0.5             # unit: T        -- magnetic field

# Velocity
v = 1e6             # unit: m/s

# Correct: F = q * (E + v*B)
# q*E has units: C * V/m = C * kg*m/(A*s^3*m) = ... -> N
# q*v*B has units: C * m/s * T = C * m/s * kg/(A*s^2) = ... -> N

# BUG: Adding E field to B field directly (wrong dimensions)
total_field = E + B  # V/m + T = kg*m/(A*s^3) + kg/(A*s^2) = DIMENSION ERROR
