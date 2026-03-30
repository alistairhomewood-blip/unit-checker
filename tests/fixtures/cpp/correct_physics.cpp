// Test fixture: correct physics computation.
//
// Computes velocity and acceleration from distance and time.
// Expected result: zero violations.

double distance = 100.0;  // unit: m
double time = 10.0;       // unit: s
double velocity = distance / time;
double acceleration = velocity / time;
