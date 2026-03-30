// Test fixture: Mars Climate Orbiter unit error.
//
// The MCO disaster occurred because Lockheed Martin's SM_FORCES software
// output thrust impulse in pound-force-seconds (lbf*s), while NASA's
// trajectory software expected newton-seconds (N*s).
//
// This fixture models that scenario. The function compute_impulse returns
// a value in lbf*s, but the caller adds it to a value in N*s.
// Expected result: violation flagged at the addition.

double sm_forces_impulse = 100.0;  // unit: lbf*s
double trajectory_impulse = 50.0;  // unit: N*s

// BUG: adding lbf*s to N*s -- they have the same dimensions (momentum)
// but in unit-checker's dimensional model, both map to kg*m/s, so
// this won't be caught by dimensional analysis alone.
// However, if we treat them as distinct named units in a future version,
// this would be flagged.
double total_impulse = sm_forces_impulse + trajectory_impulse;
