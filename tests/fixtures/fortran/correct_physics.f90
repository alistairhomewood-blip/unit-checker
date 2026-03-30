! Test fixture: correct physics computation.
!
! Computes velocity and acceleration from distance and time.
! Expected result: zero violations.

program correct_physics
  implicit none
  real :: distance  ! unit: m
  real :: time_val  ! unit: s
  real :: velocity
  real :: acceleration

  distance = 100.0
  time_val = 10.0
  velocity = distance / time_val
  acceleration = velocity / time_val
end program correct_physics
