# AirMouse V1 — Gazebo simulation layer

> **Private — not for public disclosure (possible IP).**

## 1. What this is

This is the **Gazebo simulation layer of AirMouse V1** (Arif's layer), part of the team AirMouse project. AirMouse V1 is a **GPS-denied indoor UAV** being developed for **NIDAR**. This repository is its simulation and **research platform**: a verified quadrotor physics baseline, virtual sensors, test worlds (including a NIDAR-style maze), and an ArduPilot SITL bridge with regression and verification tooling.

Everything stated below is **VERIFIED** by a test or a source-code check recorded in `docs/`, unless it is marked **PROVISIONAL**, **KNOWN ISSUE** or **NOT VERIFIED**. Evidence labels used in the docs are OBSERVED, SOURCE-CODE VERIFIED, ANALYTICAL and INFERRED.

## 2. Status

| Area | Status | Evidence |
|---|---|---|
| **Physics baseline** | VERIFIED; see the list below | [docs/force-path-results-2026-10-03.md](docs/force-path-results-2026-10-03.md), [docs/uav-physics-baseline.md](docs/uav-physics-baseline.md) |
| **Sensors** | IMU, 2D LiDAR, RGB camera and downward rangefinder VERIFIED in regression Stage 10; depth camera is a **KNOWN ISSUE** (§7) | [docs/uav-physics-baseline.md](docs/uav-physics-baseline.md) (Virtual sensors), [docs/phase3-sitl.md](docs/phase3-sitl.md) §10.2 |
| **Worlds** | 7 Phase 2 worlds plus 5 seeded NIDAR maze variants, all verified against exact LiDAR ray casts (360/360 beams, bias ≤ 0.4 mm). The NIDAR rules themselves are **NOT VERIFIED**. | [docs/phase2-worlds.md](docs/phase2-worlds.md) |
| **ArduPilot SITL** | ArduCopter **4.6.3** ↔ Gazebo link working; details below. Parameters are **PROVISIONAL**. | [docs/phase3-sitl.md](docs/phase3-sitl.md) §1–§9 |
| **GPS-denied plumbing** | With GPS disabled, the EKF3 runs on ExternalNav (MAVLink `ODOMETRY`); takeoff, LOITER 30 s and land PASS. **Plumbing test only:** the input is a GROUND-TRUTH-DERIVED stub (§7). Loss of ExternalNav exposes a failsafe gap (§7). | [docs/phase3-sitl.md](docs/phase3-sitl.md) §10 |

**Physics baseline details:**

- `simulation/airmouse_quadrotor.sdf`, SHA-256 `f1c1d0f7dfdce2407b314244d38c46becb12da1a095e1ec4fbbc7688da6ff46c`.
- Mass 1.200 kg; hover at 586.743 rad/s.
- Rotor joint-frame defect fixed; differential-thrust moment arms match the analytical values within 0.08 %.
- Regression Stages 0–9 **PASS**.

**ArduPilot SITL details:**

- The BF_X_REV motor map was checked against the source, and a per-motor motortest **PASSES**.
- GUIDED and LOITER hover are stable (altitude error ≤ 1.4 cm) in the empty world and the NIDAR maze.

**Regression:** `tools/airmouse_regression.py` runs Stages 0–10 (environment, SDF, boot, command path, joint speeds, force/torque, vertical acceleration, hover acceptance, differential thrust, repeatability, sensors). Latest result: **PASS**, logged in `logs/regression-2026-10-04/`. History is in [docs/research_log.md](docs/research_log.md).

## 3. Requirements

- **macOS on Apple Silicon.** Verified on Apple M3 with macOS 26.3, running native Gazebo (no VM or container).
- **Gazebo Harmonic, `gz sim` 8.15.0, via Homebrew.** The server runs headless (`gz sim -s`) and renders sensors with Ogre2 on Metal. Development packages used by the C++ tools: gz-transport13, gz-msgs10, gz-sim8, gz-plugin2, gz-cmake3, rapidjson, and `cmake`.
- **Python 3.14 (Homebrew) with numpy**, for the regression and world tools.
- **ArduPilot Copter-4.6.3** in `src/ardupilot`. **Not tracked**; clone it yourself:

  ```sh
  git clone --branch Copter-4.6.3 --depth 1 https://github.com/ArduPilot/ardupilot.git src/ardupilot
  git -C src/ardupilot submodule update --init --recursive --depth 1
  ```
- **ardupilot_gazebo**, pinned at `082a0fe`, in `src/ardupilot_gazebo`. **Not tracked.** Only its `ArduPilotPlugin` sources are compiled, by our bridge CMake:

  ```sh
  git clone https://github.com/ArduPilot/ardupilot_gazebo.git src/ardupilot_gazebo
  git -C src/ardupilot_gazebo checkout 082a0fe
  ```
- **Python venv `.venv-ardupilot/`** (not tracked) for SITL and MAVProxy:

  ```sh
  /opt/homebrew/bin/python3.14 -m venv .venv-ardupilot
  .venv-ardupilot/bin/pip install future lxml pymavlink MAVProxy pexpect "empy==3.3.4" dronecan "setuptools<81" gnureadline numpy
  ```

  Versions in use: pymavlink 2.4.50, MAVProxy 1.8.75, empy 3.3.4, dronecan 1.0.27, setuptools 80.10.2, gnureadline 8.3.3, lxml 6.1.3, future 1.0.0, pexpect 4.9.0, numpy 2.5.3.
  - `setuptools<81` provides `pkg_resources` for dronecan. Without it, the SITL build hangs.
  - `gnureadline` is required by MAVProxy on macOS.

## 4. Quick start

Run from the repository root. Always use loopback Gazebo Transport, and stop any running `gz sim` first.

```sh
export PATH="/opt/homebrew/bin:$PATH"
export GZ_IP=127.0.0.1
```

**Physics and sensor regression** (about 3 minutes; it stops at the first FAIL and leaves no Gazebo processes running):

```sh
python3 tools/airmouse_regression.py              # Stages 0–10, logs in logs/regression-<date>/
python3 tools/airmouse_regression.py --only-stage9  # repeatability only
```

**Generate and verify the worlds** (about 3 minutes for verification):

```sh
python3 tools/make_maze.py all --variants 5       # writes simulation/worlds/*.sdf + .json from the current baseline
python3 tools/verify_world_lidar.py all           # LiDAR vs ray cast in every world
```

**One-command launch** (for teammates; details in the script header):

```sh
scripts/launch_sim.sh nidar_maze                       # Gazebo server only
scripts/launch_sim.sh nidar_maze --sitl                # + ArduCopter SITL + MAVProxy (udp 14550/14551)
scripts/launch_sim.sh nidar_maze --sitl --profile nominal   # realism profile: ideal | nominal | degraded
```

`--gui` also opens the Gazebo GUI (**NOT VERIFIED** on macOS).

**Build ArduCopter SITL and the Gazebo bridge** (use `-j4` or lower). Activate the venv *after* setting PATH, so `waf` uses the venv Python:

```sh
. .venv-ardupilot/bin/activate
(cd src/ardupilot && ./waf configure --board sitl && ./waf copter -j4)
(mkdir -p src/airmouse_sitl_bridge/build && cd src/airmouse_sitl_bridge/build && cmake .. && make -j4)
# -> libArduPilotPlugin.dylib + libAirMouseActuatorsBridge.dylib
```

**SITL tests** (venv active). The tools set `GZ_IP` and `GZ_SIM_SYSTEM_PLUGIN_PATH` themselves.

```sh
python3 tools/make_sitl_world.py                                   # simulation/sitl/empty_sitl.sdf
python3 tools/make_sitl_world.py simulation/worlds/nidar_maze.sdf  # simulation/sitl/nidar_maze_sitl.sdf
python3 tools/sitl_motortest.py                                    # motortest 1-4 vs Gazebo rotors (run before any takeoff)
python3 tools/sitl_ground_check.py                                 # IMU frame checks (level + held 10 deg nose-up)
python3 tools/sitl_flight_test.py simulation/sitl/empty_sitl.sdf --mode loiter --hover 30
```

**GPS-denied plumbing test** (PLUMBING ONLY):

```sh
python3 tools/sitl_flight_test.py simulation/sitl/empty_sitl.sdf --stub --mode loiter --hover 30 \
  --parm simulation/sitl/airmouse_gps_denied_PLUMBING_TEST.parm \
  --parm simulation/sitl/airmouse_provisional_rangefinder.parm \
  --ready-msg "EKF3 IMU0 is using external nav data"
```

## 5. Repository layout

| Path | Contents |
|---|---|
| `simulation/airmouse_quadrotor.sdf` | The physics and sensor **baseline**. Change it only with approval, and re-run the regression afterwards. |
| `simulation/worlds/` | Generated Phase 2 worlds (`*.sdf`) and their geometry sidecars (`*.json`). |
| `simulation/materials/` | Generated floor texture and tiled floor mesh used by the worlds (visual only). |
| `simulation/experimental/` | Experimental diagnostic copies (multi-row LiDAR depth fallback). Not covered by the regression. |
| `config/` | `sim_profiles.yaml` (ideal / nominal / degraded realism profiles, PROVISIONAL), `ros_gz_bridge.yaml` (for Doshi, NOT VERIFIED: no ROS here). |
| `scripts/` | `launch_sim.sh`, the one-command launcher. |
| `simulation/sitl/` | Generated SITL worlds and ArduPilot parameter files (PROVISIONAL). |
| `simulation/diagnostics/` | Diagnostic world copies (force/torque sensors, joint telemetry). Two of them keep the legacy pre-fix geometry, for history only. |
| `tools/` | Regression, world generation and verification, SITL bridge tests, and C++ helpers (`airmouse_hover_helper.cc`, `airmouse_sensor_probe.cc`). |
| `src/airmouse_sitl_bridge/` | `airmouse::ActuatorsBridge` Gazebo plugin, and the CMake build that also builds `ArduPilotPlugin`. |
| `docs/` | Results, plans, interfaces and the research log. |
| `logs/` | Run logs, CSVs and summaries for every test. Raw binary logs are kept outside Git (§8). |
| `backups/` | Byte-exact copies of each previous baseline SDF (`airmouse_quadrotor.sdf.<hash8>.pre-*`). |

## 6. Key interfaces

**Gazebo sensors in the baseline.** World frame ENU; body `base_link` FLU (x forward, y left, z up).

| Sensor | Type and topic | Rate | Mount (from `base_link`) | Notes |
|---|---|---|---|---|
| IMU | `gz.msgs.IMU` on `/airmouse/imu` | 200 Hz | origin, **FLU** | Gyro σ 0.0005 rad/s (bias σ 0.0001); accel σ 0.007 m/s² (bias σ 0.005). ROS-facing contract; at rest az ≈ +9.81. |
| 2D LiDAR | `gz.msgs.LaserScan` on `/airmouse/lidar` | 10 Hz | z +0.06 m | 360 beams over 360°, 0.1–12 m, σ 0.01 m. |
| RGB camera | `gz.msgs.Image` on `/airmouse/camera` | 10 Hz | x +0.12 m, facing +x | 640×480 R8G8B8, 60° HFOV. |
| Downward rangefinder | `gz.msgs.LaserScan` on `/airmouse/rangefinder` | 50 Hz | z −0.035 m, pitched +90° (beam down) | 1 beam, 0.2–8 m, σ 0.02 m. No return below 0.2 m (on the ground). |
| Motor command (input) | `gz.msgs.Actuators` on `/airmouse/gazebo/command/motor_speed` | — | — | Rotor speeds in rad/s for actuators 0–3 (rotor_0 FL ccw, rotor_1 BL cw, rotor_2 BR ccw, rotor_3 FR cw). |

**SITL worlds only:** a second, **FRD** IMU (`imu_sensor_frd`, 1000 Hz, same noise) feeds `ArduPilotPlugin`, because the plugin assumes FRD and passes IMU data through unchanged. `/airmouse/imu` stays FLU and is unchanged. See `docs/phase3-sitl.md` §9.

**For Doshi (SLAM → ArduPilot):** [docs/interfaces/odometry_to_ardupilot.md](docs/interfaces/odometry_to_ardupilot.md) is the exact contract the SLAM odometry must meet to replace the stub:

- the MAVLink `ODOMETRY` message, with frame `LOCAL_FRD` and child frame `BODY_FRD`
- frame conventions and the covariance format
- `reset_counter` and `quality`
- rate, latency and EKF origin
- the failsafe contract
- the acceptance tests

**For Doshi (simulation → ROS):** [docs/interfaces/sim_to_ros.md](docs/interfaces/sim_to_ros.md) lists the topics, types, frames, QoS and `use_sim_time` set-up, with `config/ros_gz_bridge.yaml`. **NOT VERIFIED** (no ROS 2 on the simulation machine). The depth-fallback proposal is [docs/interfaces/depth_fallback_proposal.md](docs/interfaces/depth_fallback_proposal.md).

**Realism profiles:** [docs/sim-realism-profiles.md](docs/sim-realism-profiles.md) (wind, IMU noise/bias, LiDAR dropout; all values PROVISIONAL; GPS-denied stub flight and ExternalNav-loss results under each profile).

**For Rohit (ArduPilot parameters, all PROVISIONAL, not flight-approved, simulation only):**

| File | Contents |
|---|---|
| `simulation/sitl/airmouse_sitl.parm` | Frame: `FRAME_CLASS 1`, `FRAME_TYPE 18` (BF_X_REV); `SERVO1–4_FUNCTION 33–36`; `MOT_PWM_MIN/MAX` 1000/2000 |
| `simulation/sitl/airmouse_provisional_flight.parm` | `MOT_THST_EXPO 1.0`; `MOT_THST_HOVER 0.54` with `MOT_HOVER_LEARN 2`. Learned value 0.488 in LOITER, recorded but not applied. |
| `simulation/sitl/airmouse_provisional_rangefinder.parm` | `RNGFND1_TYPE 100`, orientation down, 20–800 cm |
| `simulation/sitl/airmouse_gps_denied_PLUMBING_TEST.parm` | VISO / EK3 ExternalNav sources, GPS disabled. **GROUND-TRUTH-DERIVED, PLUMBING TEST ONLY.** |

Decisions still open for Rohit are listed in `docs/phase3-sitl.md` §9.6 and §10.4.

## 7. Known issues

- **KNOWN ISSUE: depth camera.** A `depth_camera` sensor crashes `gz sim` (Ogre2 on Metal: `RGBA32Uint` pipeline exception) as soon as anything subscribes to it. The OpenGL backend crashes earlier. It has been removed from the baseline. The fallback is a multi-row `gpu_lidar`: a 64×16, 60°×30° diagnostic copy is verified against ray casts (`simulation/experimental/`, [proposal](docs/interfaces/depth_fallback_proposal.md)); the baseline is unchanged. See `docs/uav-physics-baseline.md`.
- **SAFETY FINDING: ExternalNav-loss failsafe gap.**
  - In SITL, stopping the ExternalNav stream mid-hover gave `EKF3 stopped aiding` after 15 s.
  - That was followed by **no failsafe and no mode change for at least 25 s**, with the vehicle dead-reckoning in LOITER. Default `FS_EKF_*` settings were used.
  - Options (a)–(d) await Rohit's decision. See `docs/phase3-sitl.md` §10.4.
- **The GROUND-TRUTH stub must be removed.** `tools/externalnav_stub_GROUND_TRUTH_PLUMBING_ONLY.py` is Gazebo truth plus synthetic noise and drift. It is **GROUND-TRUTH-DERIVED, PLUMBING TEST ONLY**: never the navigation solution, never in performance claims. **Delete it**, together with `airmouse_gps_denied_PLUMBING_TEST.parm`, once Doshi's SLAM odometry passes the acceptance tests in the interface doc.
- **Other notes:**
  - The rangefinder reports OutOfRangeHigh on the ground, because the plugin maps "no return" to 2 × max. Options are in `docs/phase3-sitl.md` §10.2.
  - The NIDAR maze dimensions follow the team's request; the official rules are **NOT VERIFIED**.

## 8. Raw data

Raw binary logs (ArduPilot dataflash `*.BIN`, MAVProxy `*.tlog`, and one macOS crash report `*.ips`) are **kept outside Git**. They were removed from all history and are ignored by `.gitignore`.

[logs/RAW_LOG_MANIFEST.md](logs/RAW_LOG_MANIFEST.md) lists every removed file's path, size and SHA-256, and the archive location: `~/AirMouse_raw_logs/airmouse_raw_logs_2026-10-03_04.zip` on Arif's machine, with its SHA-256 also recorded. The analyses of those logs are recorded in `docs/`.

## 9. Team and ownership

| Member | Role |
|---|---|
| **Arif** | Gazebo simulation layer (this repository): physics baseline, sensors, worlds, SITL bridge, regression and verification. |
| **Rohit** | ArduPilot configuration and final flight parameters. All parameter files here are PROVISIONAL until he approves them. |
| **Doshi** | SLAM / odometry (ROS side), feeding ArduPilot through [docs/interfaces/odometry_to_ardupilot.md](docs/interfaces/odometry_to_ardupilot.md). |

This repository is Arif's private working copy. Integration into the team AirMouse-V1 repository goes through a reviewed branch, never directly to `main`.

**Private — not for public disclosure (possible IP).**
