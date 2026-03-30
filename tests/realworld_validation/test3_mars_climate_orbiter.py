"""Synthetic test 3: Mars Climate Orbiter bug (lbf vs N confusion).

The real MCO failure: Lockheed Martin's software output thrust impulse
in pound-force-seconds (lbf*s), but JPL's trajectory code expected
newton-seconds (N*s). Factor of ~4.45 error. $327.6M mission loss.

Expected: ERROR -- unit mismatch when adding lbf*s to N*s.
"""

# Lockheed Martin subsystem outputs in imperial
thrust_impulse_lm = 500.0  # unit: lbf*s

# JPL trajectory software expects SI
thrust_impulse_jpl = 200.0  # unit: N*s

# BUG: combining lbf*s with N*s without conversion
total_impulse = thrust_impulse_lm + thrust_impulse_jpl
