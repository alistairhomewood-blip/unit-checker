! Test fixture: Mars Climate Orbiter style mismatch.
!
! One module uses lbf*s (pound-force-seconds) for impulse,
! another expects N*s (newton-seconds).
! Both have the same dimensions (force * time = momentum),
! so this is a same-dimension test (no violation in dimensional
! analysis since lbf and N have same dimensions in our model).

program mars_climate_orbiter
  implicit none
  real :: thrust_impulse  ! unit: lbf*s
  real :: applied_force   ! unit: N
  real :: delta_v

  thrust_impulse = 4.45
  applied_force = 100.0
  delta_v = thrust_impulse + applied_force
end program mars_climate_orbiter
