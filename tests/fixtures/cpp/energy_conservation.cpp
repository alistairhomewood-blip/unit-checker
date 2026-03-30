// Test fixture: energy conservation (kinetic + potential).
//
// E_kinetic = 0.5 * m * v^2
// E_potential = m * g * h
// E_total = E_kinetic + E_potential   (both are energy in J)
//
// Expected result: zero violations.

double mass = 2.0;      // unit: kg
double velocity = 3.0;  // unit: m/s
double height = 10.0;   // unit: m
double g = 9.81;        // unit: m/s^2

double kinetic = 0.5 * mass * pow(velocity, 2);
double potential = mass * g * height;
double total = kinetic + potential;
