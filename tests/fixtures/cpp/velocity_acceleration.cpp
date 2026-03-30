// Test fixture: velocity + acceleration addition error.
//
// This is Benchmark 1.2 (C++ version) from AUDIT_PLAN.md.
// Expected result: Error flagged at the addition, with message explaining
// that m/s cannot be added to m/s^2.

double velocity = 10.0;     // unit: m/s
double acceleration = 9.8;  // unit: m/s^2
double result = velocity + acceleration;  // BUG: dimensions do not match
