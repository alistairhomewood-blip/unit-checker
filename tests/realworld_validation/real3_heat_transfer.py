"""Real-world pattern 3: Heat transfer calculation.

Models conductive heat transfer through a wall using Fourier's law.
Q = k * A * dT / L

All physics correct -- no violations expected.
"""

# Material properties (steel)
k = 50.0            # unit: W/(m*K)  -- thermal conductivity
# Note: W/(m*K) = kg*m/(s^3*K) which is the SI unit

# Geometry
A = 2.0             # unit: m^2      -- cross-sectional area
L = 0.1             # unit: m        -- wall thickness

# Temperature difference
T_hot = 400.0       # unit: K
T_cold = 300.0      # unit: K
dT = T_hot - T_cold # unit: K        -- temperature difference

# Heat transfer rate: Q = k * A * dT / L
Q = k * A * dT / L  # W/(m*K) * m^2 * K / m = W (correct)
