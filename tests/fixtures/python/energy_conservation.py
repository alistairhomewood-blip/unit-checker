"""Test fixture: energy conservation with correct formulas.

Demonstrates that 0.5*m*v^2 (kinetic) and m*g*h (potential) both
produce Joules, and their sum is valid.
"""

mass = 2.0          # unit: kg
velocity = 3.0      # unit: m/s
height = 10.0       # unit: m
g = 9.81            # unit: m/s^2

kinetic = 0.5 * mass * velocity ** 2    # kg * (m/s)^2 = kg*m^2/s^2 = J
potential = mass * g * height            # kg * m/s^2 * m = kg*m^2/s^2 = J
total = kinetic + potential              # J + J = J (correct)
