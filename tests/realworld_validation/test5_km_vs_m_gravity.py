"""Synthetic test 5: Subtle scale error -- km vs m in gravitational calculation.

Computing gravitational force F = G*M*m/r^2 but altitude is in km
while other quantities are in SI (m, kg, s). This is a common error
in orbital mechanics code.

Expected: WARNING about scale mismatch (km vs m in addition or similar).
"""

G = 6.674e-11       # unit: m^3/(kg*s^2)  -- gravitational constant
M_earth = 5.972e24  # unit: kg
m_sat = 500.0       # unit: kg
R_earth = 6371.0    # unit: km            -- BUG: should be in m (6.371e6 m)
altitude = 400.0    # unit: km            -- BUG: should be in m

# This calculation mixes km and m: R_earth and altitude are in km,
# but G requires meters.
r = R_earth + altitude                    # km + km = km (consistent but wrong scale)
force = G * M_earth * m_sat / r ** 2      # mixes m^3/(kg*s^2) * kg * kg / km^2
