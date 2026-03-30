! Test fixture: energy conservation.
!
! Computes kinetic and potential energy. Contains deliberate error:
! kinetic energy formula is wrong (mass * velocity instead of
! 0.5 * mass * velocity**2).
! Expected result: violation at total_energy = potential + kinetic.

program energy_conservation
  implicit none
  real :: mass              ! unit: kg
  real :: height            ! unit: m
  real :: gravity           ! unit: m/s^2
  real :: velocity          ! unit: m/s
  real :: potential_energy
  real :: kinetic_energy
  real :: total_energy

  mass = 2.0
  height = 10.0
  gravity = 9.81
  velocity = 5.0
  potential_energy = mass * gravity * height
  kinetic_energy = mass * velocity
  total_energy = potential_energy + kinetic_energy
end program energy_conservation
