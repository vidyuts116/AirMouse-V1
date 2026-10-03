# Interface: SLAM odometry (Doshi) → ArduPilot (AirMouse V1)

**Status:** DRAFT interface contract, 2026-10-04.

- **Ownership:** the ArduPilot parameters are PROVISIONAL and owned by Rohit; the producer side is owned by Doshi.
- **Evidence base:** ArduPilot **Copter-4.6.3** source (SOURCE-CODE VERIFIED, with file and line cited per item), plus SITL plumbing tests that used a stub (`docs/phase3-sitl.md` §10.3–10.4).
- **What it replaces:** `tools/externalnav_stub_GROUND_TRUTH_PLUMBING_ONLY.py`, which is **GROUND-TRUTH-DERIVED, PLUMBING TEST ONLY** and **must be deleted** once this interface is fed by real SLAM odometry. Delete `simulation/sitl/airmouse_gps_denied_PLUMBING_TEST.parm` at the same time; the real parameters are Rohit's.

## 1. Message: MAVLink 2 `ODOMETRY` (id 331), recommended

The recommended message is `ODOMETRY` (id 331): one message carries pose, velocity, a reset counter and quality.

The alternative is `VISION_POSITION_ESTIMATE` (id 102) plus `VISION_SPEED_ESTIMATE` (id 103). ArduPilot handles both (`GCS_Common.cpp:3844-3960`). Use the alternative only if `ODOMETRY` cannot be produced; its fields map one-to-one onto §2, with Euler angles instead of a quaternion.

| Field | Required value / meaning | ArduPilot handling (4.6.3) |
|---|---|---|
| `time_usec` | Capture time of the pose, in µs, on the companion's **monotonic** clock (any epoch). | Jitter- and lag-corrected against the receive time (`GCS_Common.cpp:6753`, `correct_offboard_timestamp_usec_to_ms`). |
| `frame_id` | **`MAV_FRAME_LOCAL_FRD` (20)** | Any other value → **message silently dropped** (`GCS_Common.cpp:3885-3889`). |
| `child_frame_id` | **`MAV_FRAME_BODY_FRD` (12)** | Any other value → **silently dropped** (same lines). |
| `x, y, z` | Body origin position in the local frame (§2), in **metres** | Scaled by `VISO_SCALE` and passed to the EKF with `VISO_DELAY_MS` (`AP_VisualOdom_MAV.cpp`). |
| `q` | **[w, x, y, z]**, the rotation from **body FRD to local FRD** | Used as the attitude/yaw measurement, and to rotate the velocity. |
| `vx, vy, vz` | Velocity in **body FRD**, m/s | Rotated to the local frame with `q` (`GCS_Common.cpp:3906-3908`). Its noise is **`VISO_VEL_M_NSE`**; `velocity_covariance` is **not used**. |
| `rollspeed, pitchspeed, yawspeed` | NaN is acceptable | Not used. |
| `pose_covariance[21]` | Upper-triangular 6×6 (x, y, z, roll, pitch, yaw), row-major. Diagonal **variances** at indices **0, 6, 11** (m²) and **15, 18, 20** (rad²); the rest 0. NaN in [0] means "unknown". | posErr = ∛(c0² + c6² + c11²) and angErr = ∛(c15² + c18² + c20²) (`GCS_Common.cpp:3897-3900`), then **clamped to at least `VISO_POS_M_NSE` / `VISO_YAW_M_NSE`** (defaults 0.2 m / 0.2 rad; `AP_VisualOdom_MAV.cpp`). Small covariances do not tighten the EKF below those floors. |
| `velocity_covariance[21]` | Fill honestly, for logging and other consumers | Not used by ArduPilot 4.6.3. |
| `reset_counter` | **Increment by 1 on every discontinuity**: relocalisation, loop-closure jump, map reset | A change is timestamped and the EKF handles it as a position reset (`AP_VisualOdom_Backend.cpp:83-91`). |
| `estimator_type` | `MAV_ESTIMATOR_TYPE_VIO` (3) or `_VISION` | Informational. |
| `quality` | 0–100 (100 best); **−1 = failed / do not use** | Samples with `quality < VISO_QUAL_MIN` are **not fused** (`AP_VisualOdom_MAV.cpp`). Set `VISO_QUAL_MIN ≥ 0` so −1 is rejected. |

**Sender identity:** use the vehicle's system id, with component id `MAV_COMP_ID_VISUAL_INERTIAL_ODOMETRY` (197).

**Transport:** MAVLink 2 to a flight-controller port. In SITL this is TCP 5762 (`SERIAL1`).

## 2. Frames (must match exactly)

- **Local frame (`LOCAL_FRD`):** a fixed, **gravity-aligned** frame. Its origin is the SLAM start pose; x is the vehicle's forward direction at start (horizontal), y is right, z is **down**.
  - With `EK3_SRC1_YAW = 6`, ArduPilot uses this frame's x axis as "north". No compass alignment is needed or expected.
  - z **must** be aligned with gravity. Do not output a camera-tilted frame.
- **Body frame (`BODY_FRD`):** the vehicle body, x forward, y right, z down, at the vehicle origin (body centre of mass, `base_link`).
  - If the SLAM camera or IMU is offset or rotated relative to `base_link`, either transform to `base_link` **before** sending, or declare the offset in `VISO_POS_X/Y/Z` and `VISO_ORIENT`. Do not do both.
- **From ROS (REP-103/105, FLU/ENU-style `odom` → `base_link`):** with F = diag(1, −1, −1):
  - position_FRD = F · p_odom
  - R_FRD = F · R_odom←base · F
  - v_body_FRD = F · v_base_FLU
  - In words: flip y and z, conjugate the rotation by F, and keep the time stamp.

  The `/airmouse/imu` topic (FLU) stays the ROS-side IMU contract. ArduPilot's own IMU in SITL is a separate FRD sensor (`docs/phase3-sitl.md` §9.1).

## 3. Rate, latency, startup

- **Rate:** **20–30 Hz, steady.** The plumbing test ran at 30 Hz, with 2198 samples per 72 s fused and none ignored (OBSERVED). Avoid bursts.
- **Latency:** measure the average delay from image or IMU capture to message send, and set **`VISO_DELAY_MS`** to it (default 10 ms). Keep it under about 50 ms.
- **EKF origin:** with no GPS, send **`SET_GPS_GLOBAL_ORIGIN` (id 48)** once at startup, with any fixed lat/lon/alt. Copter's EKF failsafe check is skipped until an origin exists (`ekf_check.cpp:35-39`), and position modes need it. The stub sent it every 2 s for the first 30 s.
- **Readiness:** ArduPilot announces `EKF3 IMU0 is using external nav data` when it is fusing the data (OBSERVED in SITL). Do not arm before that.

## 4. Health and failsafe contract (SAFETY, decision pending, Rohit)

In SITL, stopping the odometry stream mid-hover produced:

- `EKF3 stopped aiding` after 15 s
- **no EKF failsafe and no mode change for at least 25 s after that**, with the vehicle dead-reckoning in LOITER

(OBSERVED, `docs/phase3-sitl.md` §10.4.) The default failsafe watches EKF variances and position availability (`ekf_check.cpp:29-75, 140-165`), and neither tripped.

**Until Rohit decides otherwise, the producer must therefore:**

1. Send `quality = −1` as soon as tracking is lost, rather than stopping silently. ArduPilot logs the sample and the VISO driver reports unhealthy, but on its own this does not trigger a failsafe.
2. Provide a heartbeat-style guarantee: a continuous stream at the stated rate while healthy.
3. Support whichever failsafe Rohit selects:
   - (a) a companion-side watchdog that commands LAND or ALT_HOLD
   - (b) an onboard Lua VISO-health monitor
   - (c) a secondary EKF source set (optical flow) with source switching
   - (d) revised EKF thresholds

## 5. ArduPilot parameters involved (PROVISIONAL; values are Rohit's)

| Parameter | Role |
|---|---|
| `VISO_TYPE` = 1 | MAVLink visual odometry |
| `VISO_POS_X/Y/Z`, `VISO_ORIENT` | Sensor offset and orientation, unless already applied by the producer |
| `VISO_DELAY_MS` | Measured latency |
| `VISO_POS_M_NSE`, `VISO_VEL_M_NSE`, `VISO_YAW_M_NSE` | EKF noise floors (§1) |
| `VISO_QUAL_MIN` | Quality gate |
| `VISO_SCALE` | 1.0 for metric SLAM |
| `EK3_SRC1_POSXY` = 6, `EK3_SRC1_VELXY` = 6, `EK3_SRC1_YAW` = 6 | ExternalNav as the source |
| `EK3_SRC1_POSZ` | 1 (baro) in the plumbing test; 2 (rangefinder) or 6 (ExternalNav) are options |
| `EK3_SRC1_VELZ` | 0 in the plumbing test; 6 if SLAM vertical velocity is trusted |
| `GPS1_TYPE` = 0 | No GPS |
| `FS_EKF_ACTION`, `FS_EKF_THRESH` | See §4 |

## 6. Acceptance tests for replacing the stub

Run the same SITL tests, with Doshi's node instead of the stub:

1. **Ground plumbing:** both EKF3 cores report "using external nav data".
2. **GPS-disabled flight:** takeoff, LOITER for 30 s, then land, with VISP samples fused and 0 ignored.
3. **Loss test:** loss of the stream, with the agreed failsafe now expected to trigger.

Then delete the stub and its parameter file, and remove the `--stub` paths from `tools/sitl_flight_test.py`.
