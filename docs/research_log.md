# AirMouse research log

Chronological engineering log. Each entry carries evidence labels: OBSERVED, SOURCE-CODE VERIFIED, ANALYTICAL, INFERRED, NOT VERIFIED. Details live in the linked docs.

## 2026-10-03

- **Force path verified; fall explained.** The rotor-speed-to-force chain matches the analytical values to 4 significant figures. The 2 m fall came from the test harness: about 0.25 s of command latency, followed by an open-loop command at exactly hover. See `force-path-results-2026-10-03.md`.
- **Joint-frame defect found and fixed.** Joint `<pose>` values were resolved relative to the child link, so the rotors orbited at 0.4 m. After the approved fix, the moment arms match analytical values within 0.08 %. Baseline `5a72f8ba` → `92baa42b`.
- **Regression suite.** `tools/airmouse_regression.py` runs Stages 0–10 and stops at the first FAIL.
- **Virtual sensors.**
  - IMU (`652ef0c1`), 2D LiDAR (`1224906b`) and RGB camera (`21626e64`) all PASS.
  - **KNOWN ISSUE:** the depth camera crashes Ogre2 on Metal as soon as anything subscribes to it, so it was reverted.
  - See `uav-physics-baseline.md`.
- **Phase 2 worlds.** 7 worlds plus 5 seeded NIDAR variants, all verified against LiDAR ray-casts. The NIDAR maze follows the requested spec; the official rules are NOT VERIFIED. See `phase2-worlds.md`.
- **Phase 3 SITL.**
  - ArduCopter 4.6.3 SITL ↔ Gazebo via `ArduPilotPlugin` and the `airmouse::ActuatorsBridge`.
  - The BF_X_REV map was verified in source, and motortest PASSES on all four motors.
  - Python 3.14 fixes: `setuptools<81` (for `pkg_resources`) and `gnureadline`.
  - See `phase3-sitl.md`.
- **First SITL takeoff (PROVISIONAL params): UNSTABLE.** The vehicle flipped in pitch, then SITL hit `SIGILL` in `EKFGSF_yaw::predict`. Root cause: the AirMouse IMU reports FLU, while `ArduPilotPlugin` passes IMU data raw and assumes FRD (SOURCE-CODE VERIFIED). Pitch and yaw rates and accel z reached ArduPilot inverted; at rest AccZ was +9.817 (OBSERVED). Proposed fix: rotate the IMU sensor by 180° roll in SITL worlds only. Not applied; the campaign stopped per instruction. Regression after the attempt: PASS.
- **Open decisions:**
  - approve the SITL IMU-frame fix and the re-fly
  - Rohit's review of the frame parameters and the provisional flight parameters
  - the GPS-denied configuration
  - the NIDAR spec interpretations (room size, footprint convention, marker shape)
