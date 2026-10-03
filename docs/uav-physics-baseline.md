# TEST 2: Minimal AirMouse Quadrotor Physics

## Status

**Update 2026-10-03:** native dynamic tests have now been run on macOS with Gazebo Sim 8.15.0. The full evidence is in `docs/force-path-results-2026-10-03.md`.

- **Approved fix applied.** The rotor joint frame placement was corrected; see "Joint frame placement" below. Physics parameters changed: none (joint frame placement only).
- **Current baseline SHA-256:** `92baa42b6fb1d1a45f4e702c292dbf46c2a473909f4b909659690007eedabc02`.
- **Previous SHA-256:** `5a72f8bac558ddecf76091790d8d3515e9d77e6da2956fbe3a61d7bd78131957`. The previous file is preserved as `backups/airmouse_quadrotor.sdf.5a72f8ba.pre-jointfix`.
- **Hover acceptance: PASS (OBSERVED).**

The paragraph below is the original status, retained for history.

**Not yet verified / acceptance result: INCOMPLETE.** The SDF parses, but Gazebo could not be run in the available execution sandbox: Gazebo Transport failed to bind its local discovery socket (`Operation not permitted`). An elevated run was rejected by the environment approval policy. No dynamic result or PASS claim is made here. Run the commands below on the native macOS desktop session to complete the baseline and record the observed altitude/time values.

The known-good `simulation/diagnostic.sdf` was inspected and left unchanged.

## Architecture

`simulation/airmouse_quadrotor.sdf` is a self-contained SDF 1.10 world with native Gazebo Harmonic Physics, SceneBroadcaster, and UserCommands systems; a static ground plane; and an `airmouse` model. Four independent instances of Gazebo Harmonic's installed `gz::sim::systems::MulticopterMotorModel` subscribe to actuator indices 0–3 on `/airmouse/gazebo/command/motor_speed`. The motor model applies thrust through the rotor links and Gazebo physics. No model pose/position commands are used.

The body frame is right handed and SI: origin at the vehicle center of mass, +X forward, +Y left, +Z upward. World gravity is `(0, 0, -9.81) m/s²`. The initial model origin is 1.5 m above the ground. The X frame has rotor centers at `(±0.282843, ±0.282843, 0) m` relative to the body, giving 0.4 m center-to-rotor arm length. All four are revolute joints about local +Z. Rotors 0 and 2 use CCW reaction torque; 1 and 3 use CW.

### Joint frame placement (fixed 2026-10-03)

In SDF ≥1.7, a joint `<pose>` without `relative_to` is expressed in the **child link** frame.

**Before the fix (OBSERVED):**

- The joints carried the arm coordinates `(±0.282843, ±0.282843, 0)`, which placed each rotor axis at (±0.566, ±0.566).
- The rotor links orbited that axis at r = 0.4 m, with a 137.73 N in-plane joint load at 586.8 rad/s.
- Symmetric hover was unaffected.
- Differential thrust gave yaw 55.9× and pitch 8.8× the analytical moment, with large cross-axis coupling.

**After the fix:** each `rotor_i_joint` `<pose>` is `0 0 0 0 0 0`, so the axis passes through the rotor centre at `(±0.282843, ±0.282843, 0)` relative to the body. No mass, inertia, motor or world parameter changed. Verified results (OBSERVED):

- Rotor links stay at exactly (±0.282843, ±0.282843).
- In-plane joint force and torque are 0.
- Axial joint force at 586.8 rad/s is 2.933757 N, which is thrust minus rotor weight.
- Measured roll, pitch and yaw angular accelerations under ±5 rad/s differential commands are 0.9992, 0.9993 and 0.9995 of τ/I. Here I includes the rotor point masses: (0.01832, 0.01832, 0.03264) kg·m².

## Mass, inertia, and motor parameters

The base link has mass 1.196 kg; each rotor link has mass 0.001 kg, for 1.200 kg total. The base inertia about the stated center of mass is diagonal `(0.018, 0.018, 0.032) kg·m²`; rotor-link inertias are each diagonal `1e-6 kg·m²`. The mass and inertia are simplified rigid-body assumptions for a small quadrotor.

Each motor uses Gazebo's velocity motor model with `motorConstant = 8.54858e-6 N/(rad/s)²`, maximum rotor velocity 800 rad/s, rise time constant 0.0125 s, fall time constant 0.025 s, and zero modeled rotor drag / rolling moment. The force law is the native motor model's quadratic speed-to-thrust law, `T = k·ω²`. Commands are angular velocity in rad/s, not thrust in newtons. Independent input is sent as the four-element `gz.msgs.Actuators.velocity` vector `[ω0, ω1, ω2, ω3]`.

From these configured parameters, weight is `1.2 × 9.81 = 11.772 N`; ideal per-rotor hover thrust is 2.943 N, corresponding to about 586.8 rad/s. At 500 rad/s each rotor's ideal thrust is 2.137 N and total is 8.547 N; at 700 rad/s each is 4.189 N and total is 16.754 N. These are calculated inputs, not measured simulator results. Equal-thrust nominal hover is only an estimate; it has not been observed or shown stable.

## Reproducible test procedure

Use a terminal in the native macOS user session where `gz sim -s` is known to run. Each case starts a fresh world so the initial state is repeatable. In Terminal A, launch:

```sh
cd ~/Drone
gz sim -s -r simulation/airmouse_quadrotor.sdf
```

In Terminal B, subscribe to the world's pose stream (use `Ctrl-C` after each observation window):

```sh
gz topic -e -t /world/airmouse_physics/pose/info
```

In Terminal C, send exactly one of these command vectors after the pose stream shows the model. Observe for about 2 simulation seconds, then stop the server and restart for the next case. Record the first pose/time and last pose/time for `airmouse` from the pose stream. Simulation time can be read from `/world/airmouse_physics/stats` (`gz topic -e -t /world/airmouse_physics/stats`).

```sh
# A: zero thrust (all rotors off)
gz topic -t /airmouse/gazebo/command/motor_speed -m gz.msgs.Actuators -p 'velocity: [0, 0, 0, 0]'

# B: equal thrust below weight
gz topic -t /airmouse/gazebo/command/motor_speed -m gz.msgs.Actuators -p 'velocity: [500, 500, 500, 500]'

# C: nominal balanced thrust / estimated hover
gz topic -t /airmouse/gazebo/command/motor_speed -m gz.msgs.Actuators -p 'velocity: [586.8, 586.8, 586.8, 586.8]'

# D: equal thrust above weight
gz topic -t /airmouse/gazebo/command/motor_speed -m gz.msgs.Actuators -p 'velocity: [700, 700, 700, 700]'
```

Because the motor model has a finite spin-up time, ignore the short initial transient when judging steady acceleration. For case C, measure altitude drift across the observation window; do not label it stable hover from a brief visual impression. Four independent control can be checked by publishing a vector with only one nonzero element and confirming that only that rotor's motor speed topic responds; the four speed topics are `/airmouse/motor_speed/0` through `/airmouse/motor_speed/3`.

## Results (native execution, 2026-10-03, baseline `92baa42b…bc02` unless noted)

All values are OBSERVED from live Gazebo runs; "Calculated" columns are ANALYTICAL. Measured accelerations are quadratic fits to the pose stream over the powered (or unpowered) interval with rotors at steady speed.

| Case | Per-rotor command (rad/s) | Calculated total thrust (N) | Calculated a_z (m/s²) | Measured a_z (m/s²) | Observed behavior |
|---|---:|---:|---:|---:|---|
| A: zero | 0 | 0 | −9.81 | −9.81000 | Free fall (from the pre-command phase of each run) |
| B: below weight | 500 | 8.547 | −2.687 | **not run** | NOT VERIFIED |
| C: estimated balance | 586.8 | 11.774 | +0.001896 | +0.00190 | Hover acceptance PASS: from z=2.000 m, max \|z−2\| 0.00831 m over 2.0 s, tilt 0, drift 0 |
| D: above weight | 700 | 16.755 | +4.152681 | +4.15268 | Steady climb acceleration; a second harness gave +4.15452 |

**Hover acceptance:** criteria |a_z − 0.0019| < 0.05 m/s² and |z − 2.0| < 0.02 m over 2 s. The test is `tools/airmouse_hover_acceptance.py`. It starts the motor publisher first, gates on 1 publisher and 4 connected subscribers, spins up on the ground for 1 s, then calls `set_pose` to z = 2 m. Exact hover is 586.743 rad/s, so 586.8 rad/s climbs slightly by design (ANALYTICAL).

**Moment-arm test:** `tools/airmouse_differential_thrust.py` gives a measured-to-analytical angular acceleration ratio of 0.9992–0.9995 on all three axes (OBSERVED).

## Limitations and known issues

- This is a rigid-body propulsion baseline, not a flight controller. The body is not stabilized against attitude disturbances.
- The rotor model abstracts propeller aerodynamics to a quadratic thrust law. Ground effect, inflow, battery, motor torque dynamics beyond the configured first-order speed response, and air drag are not modeled.
- The 1.2 kg mass and diagonal inertia are engineering assumptions. They should be replaced with measured/selected hardware properties before controller tuning.
- ~~Native dynamic testing remains outstanding~~: completed on 2026-10-03 (see Results).
- Case B (500 rad/s) has not been run.
- The per-rotor topics `/airmouse/motor_speed/0..3` mentioned above have not been checked (NOT VERIFIED).
- The open-loop test procedure in this document, using `gz topic -p`, has a variable command latency of 0.25–0.37 s after reset (OBSERVED). Use `tools/airmouse_hover_acceptance.py` for repeatable results.

## Files created

- `simulation/airmouse_quadrotor.sdf`
- `docs/uav-physics-baseline.md`

## Regression run 2026-10-03

- **Tool:** `tools/airmouse_regression.py`. It runs the stages in order and stops at the first FAIL. It never edits an SDF.
- **Logs:** `logs/regression-2026-10-03/`.
  - Passing run: `run_173902.log`, `results.json`, `summary.md`.
  - Per-session CSVs: `stage3-5_*`, `stage6-9_*`.
  - Server logs: `server_*.log`.
  - First, aborted run: `run_173649.log`.
- **Baseline SHA-256 before and after:** `92baa42b6fb1d1a45f4e702c292dbf46c2a473909f4b909659690007eedabc02` (OBSERVED).
- **Gazebo processes left running:** 0 (OBSERVED).

**First attempt: FAIL at Stage 6, caused by a test-tool defect, not physics.**

- **What happened:** waiting for the paused `set_pose` to z = 2 timed out.
- **Root cause (OBSERVED in isolation):** while the world is paused, the continuously subscribed `/world/airmouse_physics/pose/info` stream keeps republishing the *pre-reset* state. The paused `set_pose` is applied, but it is not published until the world steps.
- **Fix (test tool only):** after the paused `set_pose`, advance exactly one 1 ms iteration (`multi_step: 1`) and take that sample as the reset time. The abort was also misattributed to Stage 5 in the summary; that was fixed too.
- **Outcome:** re-run from Stage 0 → all PASS.

**Method notes:**

- Stages 6–9 run the ground spin-up dwell, the reset and the differential command with the world paused and advanced by `multi_step`. Simulated durations are therefore exact and runs are repeatable.
- Stage 3 measures live, unpaused latency.
- Stages 3–5 use `simulation/diagnostics/airmouse_force_diagnostic_jointfix.sdf`, which has the same physics as the baseline plus diagnostic sensors. All other dynamic stages use the baseline.

| Stage | Name | Result | Measured (OBSERVED) | Expected |
|---|---|---|---|---|
| 0 | Environment | PASS | gz sim 8.15.0; baseline hash matches; tools present; helper builds; no prior gz process | as listed |
| 1 | SDF validity and parsed parameters | PASS | `gz sdf -k` Valid for the baseline and all 3 `diagnostics/*.sdf`. Baseline and jointfix: mass 1.200000 kg; joint poses 0 0 0 0 0 0; rotor links (±0.282843, ±0.282843); slowdown 1; k 8.54858e-06; ccw/cw/ccw/cw. | as listed |
| 2 | Server boot | PASS | pose published; motor topic 4 subscribers, 0 publishers | 4 / 0 |
| 3 | Command path | PASS | gate passed after 2.21 s wall; latency **5.0 ms sim** (3.1 ms wall), quantised by 200 Hz sampling | ≤ 20 ms sim |
| 4 | Joint speeds at 586.8 | PASS | +586.8000 / −586.8000 / +586.8000 / −586.8000 rad/s; t95 **45.0 ms** from command (all four) | ±586.8, +,−,+,−; t95 37.4 ± 10 ms (ANALYTICAL τ·ln20) |
| 5 | Force/torque sensors | PASS | axial +2.933757 N spun up (ground and airborne); −0.009810 N stopped; in-plane peak ≤ 2.5e-32 N spun up and ≤ 8.4e-19 N stopped; torque ≤ 1.5e-25 N·m | 2.93376 N ±1 %; −0.00981 N; ≈ 0 |
| 6 | Vertical acceleration (airborne window) | PASS | 500: **−2.68618**; 586.8: **+0.00190**; 700: **+4.15268** m/s² | −2.68618 / +0.00190 / +4.15268 ±0.05 (ANALYTICAL) |
| 7 | Hover acceptance | PASS | a_z +0.00190 m/s²; max \|z−2\| **0.00705 m** over 2 s; tilt 0; drift 0 | < 0.05 m/s²; < 0.02 m |
| 8 | Differential thrust (Δ = 5 rad/s) | PASS | roll **+3.09546** (0.9992); pitch **−3.09547** (0.9992); yaw **−0.09831** (0.9995) rad/s²; cross-axis ≤ 2.2e-6 | +3.09788 / −3.09788 / −0.09836 ±2 % (ANALYTICAL τ/I with rotor masses) |
| 9 | Repeatability (3×) | PASS | Stage 6 a_z spread 0.0345 %; Stage 7 a_z spread 0.0000 %; Stage 7 max \|z−2\| spread 0.0040 % | < 1 % |
| 10 | Virtual sensors | NOT PRESENT | No IMU/LiDAR/camera/depth sensors in any SDF; the baseline has 0 sensors. Diagnostic-only telemetry (jointfix): joint_state and 4× force_torque at 200.0 Hz (sim time) | ±10 % of 200 Hz |

**Overall: PASS** (OBSERVED).

**Notes (INFERRED):**

- **Stage 7 z deviation:** max |z−2| is now 0.00705 m, against 0.0083 m in the earlier acceptance runs. The ground dwell is now exactly 1.000 s simulated, so the small climb picked up on the ground (v₀ +0.00166 m/s) is smaller and fixed.
- **Stage 4 t95:** 45 ms, against the analytical 37.4 ms. The difference includes the 5 ms command latency and the 5 ms joint-state sampling.

## Virtual sensors (2026-10-03)

Sensors were added one at a time. After each addition, `tools/airmouse_regression.py` was re-run, and Stages 0–9 had to pass. **Physics parameters changed: none.** The only changes are sensors on `base_link`, which add no mass or inertia, and world systems (Imu, Sensors). The Stage 1 parsed checks (mass, joints, rotors, k, directions) and Stages 6–9 are unchanged (OBSERVED).

The regression pins `GZ_IP=127.0.0.1`, because Gazebo Transport discovery was lost once when the host network changed (INFERRED cause). It also retries service calls whose reply is lost, which happened once as `Host unreachable` in a server log.

| Step | SHA-256 | Diff | Regression |
|---|---|---|---|
| start | `92baa42b6fb1d1a45f4e702c292dbf46c2a473909f4b909659690007eedabc02` | — | — |
| 1. IMU | `652ef0c11c87fc47fa5acd9bab0546382fe61052b0cfd08a180568b3c489783c` | `logs/regression-2026-10-03/baseline_imu.diff` | **PASS**, Stages 0–10 |
| 2. 2D LiDAR | `1224906b074b16317329e07107e510c751b4693969e1e00ddc48187d8a36b91c` | `logs/regression-2026-10-03/baseline_lidar.diff` | **PASS**, Stages 0–10 |
| 3a. Depth camera | `de85fc006cfa95239bb724c288560ece89fb04c96d96c76c741f80d9d1ed6a0f` (current file) | `logs/regression-2026-10-03/baseline_depth.diff` | Stages 0–9 PASS; **Stage 10 FAIL** |

Byte-exact backups of each pre-step file are in `backups/airmouse_quadrotor.sdf.<hash8>.pre-*`.

### IMU

- **Configuration:** `imu_sensor` on `base_link` at the centre of mass, 200 Hz, topic `/airmouse/imu`, using the `gz-sim-imu-system`.
- **Noise:** gaussian. Gyro σ = 0.0005 rad/s with bias σ = 0.0001 rad/s; accel σ = 0.007 m/s² with bias σ = 0.005 m/s². These match an ICM-42688-class MEMS IMU: 0.0028 °/s/√Hz and 70 µg/√Hz over about 100 Hz bandwidth.
- **Results (OBSERVED):**
  - rate 200.0 Hz
  - at rest: a_z +9.8163 m/s², gyro ≤ 1.7e-4 rad/s
  - in hover at 586.8 rad/s: a_z +9.8129–9.8169 m/s², against thrust/m = 9.81190 (ANALYTICAL)
  - climbing at 700 rad/s: a_z +13.9623–13.9676 m/s², against 13.96268
  - noise std 1.02–1.04× the configured value

### 2D LiDAR

- **Configuration:** `lidar_2d`, type `gpu_lidar`, using the `gz-sim-sensors-system` with Ogre2 on Metal. 10 Hz, 360 samples over 360°, range 0.1–12 m, gaussian σ = 0.01 m. Mounted 0.06 m above the body origin. Topic `/airmouse/lidar`.
- **Test:** a wall world is generated by the regression from the current baseline, with a wall face at x = 3.000 m.
- **Results (OBSERVED):**
  - 10.1 Hz, 360 beams
  - mean error over the ±25° wall beams: +0.7 to +1.0 mm over 1500 returns, against 3.0/cos θ
  - error std 10.6 mm, against 10 mm configured
  - no returns elsewhere, so no self-hits

### Depth camera: FAIL (platform rendering defect)

- **Configuration:** `depth_camera` at x = 0.12 m facing +x, 10 Hz, 320×240 R_FLOAT32, 60° HFOV, 0.1–10 m, σ = 0.005 m. Topic `/airmouse/depth`.
- **Failure (OBSERVED):** the server runs normally until something subscribes to `/airmouse/depth`. Physics Stages 0–9 pass because nothing subscribes during them. On the first subscription, `gz sim` aborts with:

  `Ogre::RenderingAPIException: Failed to created pipeline state for rendering, error output of type float4 is not compatible with a MTLPixelFormatRGBA32Uint color attachment (MetalRenderSystem::_hlmsPipelineStateObjectCreated)`

  This reproduces in both the baseline and the wall world. Log: `logs/regression-2026-10-03/depth_camera_metal_crash.log`.
- **OpenGL backend:** `--render-engine-server-api-backend opengl` is worse. The server aborts inside Ogre GL3Plus buffer creation before any sensor publishes. Log: `depth_camera_opengl_crash.log`.
- **RGB camera trial, scratch copy only:** a type `camera` sensor at 640×480 and 10 Hz **renders on Metal**: 78 frames, 921,600 bytes each (OBSERVED). Log: `rgb_camera_metal_trial_probe.txt`.
- **Current state:** the baseline still contains the depth camera, pending a decision. Any subscriber to `/airmouse/depth` will crash the simulation.
