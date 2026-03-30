"""Real-world pattern 1: Two-body orbital mechanics (Kepler problem).

Derived from patterns in orbital mechanics simulators like
WStr99/Orbital-Mechanics-Simulator and alfonsogonzalez/AWP.

Computes orbital velocity, period, and energy for a circular orbit.
All physics should be correct -- no violations expected.
"""

import numpy as np

# Constants
G = 6.674e-11       # unit: m^3/(kg*s^2)
M_earth = 5.972e24  # unit: kg
R_earth = 6.371e6   # unit: m

# Satellite parameters
altitude = 400e3     # unit: m
m_sat = 500.0        # unit: kg

# Orbital radius
r = R_earth + altitude  # unit: m

# Orbital velocity (circular): v = sqrt(G*M/r)
v_orbital = np.sqrt(G * M_earth / r)  # unit: m/s

# Orbital period: T = 2*pi*r / v
T_orbit = 2.0 * 3.14159265 * r / v_orbital  # unit: s

# Kinetic energy: KE = 0.5 * m * v^2
KE = 0.5 * m_sat * v_orbital ** 2  # unit: J

# Potential energy: PE = -G * M * m / r
PE = -G * M_earth * m_sat / r  # unit: J

# Total energy
E_total = KE + PE  # unit: J
