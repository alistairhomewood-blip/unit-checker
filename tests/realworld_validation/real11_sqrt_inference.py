"""Real-world pattern 11: Square root unit inference.

Tests that sqrt correctly halves the dimension exponents.
sqrt(m^2/s^2) should give m/s.

Expected: PASS -- no violations.
"""

import math

# Input with known units
area = 25.0          # unit: m^2
length = math.sqrt(area)  # Should infer: m

# Energy per unit mass (specific energy)
E_specific = 1e6     # unit: J/kg  -- same as m^2/s^2

# This doesn't work because J/kg isn't a registered unit
# Let's use raw dimensions instead

v_squared = 100.0    # unit: m^2/s^2
speed = math.sqrt(v_squared)  # Should infer: m/s
