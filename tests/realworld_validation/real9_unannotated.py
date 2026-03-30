"""Real-world pattern 9: Completely unannotated scientific code.

This is what the tool would encounter in most existing codebases:
no unit annotations at all. Tests graceful degradation.

Expected: No violations (insufficient information to infer), but
the tool should handle it gracefully.
"""

import numpy as np

G = 6.674e-11
M = 5.972e24
R = 6.371e6
alt = 400e3

r = R + alt
v = np.sqrt(G * M / r)
T = 2 * np.pi * r / v
F = G * M * 500.0 / r**2
