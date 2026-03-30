"""Synthetic test 1: Adding meters to seconds (clear dimension error).

Expected: ERROR -- cannot add length [m] to time [s].
"""

distance = 100.0  # unit: m
elapsed = 5.0     # unit: s

# BUG: adding distance to time makes no physical sense
total = distance + elapsed
