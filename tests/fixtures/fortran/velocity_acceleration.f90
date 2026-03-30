! Test fixture: velocity + acceleration mismatch.
!
! Attempts to add velocity (m/s) to acceleration (m/s^2).
! Expected result: one violation at the addition.

program velocity_acceleration
  implicit none
  real :: velocity      ! unit: m/s
  real :: acceleration  ! unit: m/s^2
  real :: result

  velocity = 10.0
  acceleration = 9.8
  result = velocity + acceleration
end program velocity_acceleration
