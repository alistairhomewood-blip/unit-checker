"""Synthetic test 4: Temperature conversion error (K vs degC).

Kelvin and Celsius have the same dimension (temperature) but different
zero points. Adding an absolute Celsius temperature to a Kelvin temperature
is a common physics error in thermodynamics code.

Expected: WARNING or ERROR about temperature kind mismatch.
"""

temp_kelvin = 300.0   # unit: K
temp_celsius = 25.0   # unit: degC

# BUG: mixing absolute temperature scales without conversion
# (300 K is not 300 + 25 = 325 in any meaningful sense)
average = (temp_kelvin + temp_celsius) / 2.0
