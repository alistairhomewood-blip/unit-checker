"""Real-world pattern 12: Tsiolkovsky rocket equation.

Computes delta-v for a rocket: dv = Isp * g0 * ln(m0/mf)
where Isp is specific impulse in seconds, g0 = 9.81 m/s^2.

Contains a subtle bug: using Isp directly as a velocity instead
of Isp * g0 (which gives effective exhaust velocity in m/s).

Expected: ERROR when adding m/s to dimensionless (or seconds,
depending on how the tool handles it).
"""

import math

# Rocket parameters
m0 = 10000.0         # unit: kg     -- initial mass (with propellant)
mf = 3000.0          # unit: kg     -- final mass (dry mass)
Isp = 300.0          # unit: s      -- specific impulse
g0 = 9.81            # unit: m/s^2  -- standard gravity

# Correct exhaust velocity
v_exhaust = Isp * g0  # s * m/s^2 = m/s (correct)

# Correct delta-v: Tsiolkovsky equation
mass_ratio = m0 / mf  # kg / kg = dimensionless
dv_correct = v_exhaust * math.log(mass_ratio)  # m/s * dimensionless = m/s

# BUG: Using Isp directly as velocity (common rookie mistake)
# Isp is in seconds, not m/s!
dv_buggy = Isp * math.log(mass_ratio)  # s * dimensionless = s (NOT m/s!)

# This would be caught if someone tries to add it to a real velocity
initial_velocity = 0.0  # unit: m/s
final_v_correct = initial_velocity + dv_correct  # m/s + m/s = m/s (correct)
final_v_buggy = initial_velocity + dv_buggy      # m/s + s = DIMENSION ERROR
