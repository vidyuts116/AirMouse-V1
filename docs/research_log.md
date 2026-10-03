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
- **SITL IMU-frame fix (approved) and flights 2–3: STABLE.**
  - **Fix:** the SITL worlds keep the FLU IMU on `/airmouse/imu` and add an FRD IMU (roll 180°, same noise) for ArduPilotPlugin.
  - **Ground checks PASS:** at rest AccZ −9.815, and when held 10° nose-up ArduPilot reports pitch +10.00°. `/airmouse/imu` still reads az +9.818.
  - **empty_sitl:** takeoff 1.5 m, hover 30 s, land. Altitude error max 1.0 cm, attitude std 0.01°, drift 0.2 cm, RTF 1.000.
  - **NIDAR maze:** takeoff and hover. Altitude error max 1.2 cm, attitude std 0.02°, RTF 0.997.
  - **Hover speed:** the hover PWM gives ω 586.68–586.70 rad/s, against the analytical 586.743.
  - **Hover learning:** it did not run, because GUIDED's desired vertical velocity is never exactly zero (OBSERVED and SOURCE-CODE VERIFIED). ThO 0.4877 is consistent with 0.532 after ArduPilot's battery and air-density compensation (INFERRED).
  - **Regression:** PASS. See `phase3-sitl.md` §9.
- **Open decisions:**
  - hover-learning procedure (ALT_HOLD/LOITER) or a fixed `MOT_THST_HOVER` ≈ 0.49; takeoff overshoot
  - Rohit's review of the frame parameters and the provisional flight parameters
  - the GPS-denied configuration
  - the NIDAR spec interpretations (room size, footprint convention, marker shape)

## 2026-10-04

- **Hover learning in LOITER (GPS on):** `MOT_THST_HOVER` learned **0.488**, as predicted, which is the thrust-domain value after compensation. It is recorded for Rohit and not applied. The LOITER hover was stable: altitude error max 1.3 cm, drift 2.0 cm. See `phase3-sitl.md` §10.1.
- **Downward rangefinder:**
  - Added to the baseline as a 1-beam `gpu_lidar` (0.2–8 m, σ 2 cm, 50 Hz). New baseline `f1c1d0f7`; regression PASS.
  - `ArduPilotPlugin` forwards it as JSON `rng_1` (SOURCE-CODE VERIFIED), and ArduPilot RFND reads 1.487 m in a 1.5 m hover, status Good.
  - Limitation: on the ground it reports OutOfRangeHigh, because the plugin maps no return to 2 × max. Options are listed for Rohit.
  - All 12 worlds regenerated and re-verified: PASS. See `phase3-sitl.md` §10.2.
- **ExternalNav plumbing stub (GROUND-TRUTH-DERIVED, PLUMBING TEST ONLY; to be removed once Doshi's SLAM exists):**
  - It sends MAVLink ODOMETRY (LOCAL_FRD/BODY_FRD) at 30 Hz from Gazebo truth plus noise and drift.
  - With GPS disabled, both EKF3 cores report "is using external nav data". See `phase3-sitl.md` §10.3.
- **GPS-denied flight (GPS disabled, ExternalNav from the PLUMBING-ONLY stub):**
  - Takeoff, LOITER 30 s and land all PASS: altitude error max 1.2 cm, drift 0.7 cm. 2198 VISP samples consumed, 0 ignored.
  - These are plumbing results only, not navigation performance.
- **ExternalNav loss mid-hover:**
  - "EKF3 stopped aiding" at +15 s. **No failsafe and no mode change** through +40 s, with the vehicle LOITERing on dead-reckoning. EKF test ratios fell to 0.
  - **SAFETY FINDING:** a loss of the SLAM feed is not caught by default failsafes. Options (a)–(d) are listed for Rohit. See `phase3-sitl.md` §10.4.

