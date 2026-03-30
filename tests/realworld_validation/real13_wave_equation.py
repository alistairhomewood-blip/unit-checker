"""Real-world pattern 13: Wave equation parameters.

Tests a common pattern in acoustics/optics code where wavelength,
frequency, and speed of sound/light are related: c = f * lambda.

All correct -- no violations expected.
"""

# Speed of sound in air
c = 343.0            # unit: m/s

# Frequency of a musical note (A4 = 440 Hz)
f = 440.0            # unit: Hz

# Wavelength: lambda = c / f
wavelength = c / f   # m/s / (1/s) = m/s * s = m (correct)

# Wave period: T = 1/f
period = 1.0 / f     # 1 / (1/s) = s (correct)

# Check: c should equal wavelength * f
check_v = wavelength * f  # m * (1/s) = m/s (correct, should match c)
