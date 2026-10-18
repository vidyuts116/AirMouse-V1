# Simulation realism profiles (ideal / nominal / degraded)

**Status:** 2026-10-04. Simulation only. **All profile values are PROVISIONAL assumptions**, not measurements of the real vehicle. The physics baseline (`simulation/airmouse_quadrotor.sdf`, SHA-256 `f1c1d0f7…`) is never edited: a profile only rewrites the generated SITL world.

## Use

```sh
python3 tools/make_sitl_world.py simulation/worlds/empty.sdf --profile nominal   # -> simulation/sitl/empty_sitl_nominal.sdf (+ .profile.json)
scripts/launch_sim.sh nidar_maze --sitl --profile degraded                       # one command
```

Profiles live in `config/sim_profiles.yaml`. `ideal` produces a world identical to the unprofiled SITL world (checked with `diff`).

## What each profile changes

| Effect | Mechanism | ideal | nominal | degraded |
|---|---|---|---|---|
| Wind | `gz-sim-wind-effects-system` on `base_link`; mean wind (ENU m/s), sinusoidal gusts, noise | none | [0.5, 0.2, 0] m/s, gust ±40 %, drag k 0.05 /s | [2.0, 0.5, 0] m/s, gust ±80 %, drag k 0.15 /s |
| IMU (both the FLU `/airmouse/imu` and the FRD copy ArduPilot uses) | replaces the gaussian noise; bias + slow bias random walk | baseline (gyro σ 0.0005, accel σ 0.007) | gyro σ 0.003 rad/s, bias σ 0.002; accel σ 0.05 m/s², bias σ 0.05 | gyro σ 0.01, bias σ 0.01; accel σ 0.25, bias σ 0.2 |
| LiDAR dropout | `AirMouseLidarDropout` plugin: `/airmouse/lidar_raw` → `/airmouse/lidar`, `+inf` beams | none | 1 % of beams, 0.5 % of scans | 5 % of beams, 3 % of scans |

Limitations (all deliberate or unavoidable):

- **Vibration is white noise.** Gazebo has no narrowband vibration model; the "vibration" is extra white accelerometer/gyro noise.
- **Wind drag also damps the vehicle's own motion on every axis**, because `WindEffects` applies `F = m·k·(wind − v)`. The plugin's real law is `k = scale²`, **measured** (the source and docs suggest `k = scale`): at 2 m/s steady wind, hover lean was 0.11 / 1.04 / 4.17 / 11.49° at scale 0.1 / 0.3 / 0.6 / 1.0, and free-fall terminal speed at scale 1 was 9.84 m/s. The generator therefore sets `scale = sqrt(k)`. Data: `logs/sim-step2-profiles/wind-calibration/`. The wind also ramps up over its first 10–30 s.
- **LiDAR dropout needs a Gazebo plugin** (`src/airmouse_sitl_bridge/LidarDropout.cc`, built by the existing CMake). Measured on the degraded setting in the NIDAR maze: no-return beams rose from 22.8 % (raw) to 29.1 %, and 7 of 200 scans were fully dropped (3.5 %), consistent with 5 % / 3 %.
- IMU noise was measured on the ground (400 samples): nominal gyro σ 0.0029, accel σ 0.047–0.049; degraded gyro σ 0.0097–0.0098, accel σ 0.24–0.26; both match the YAML.

## Result: GPS-denied stub flight and ExternalNav loss under each profile

Empty world, ArduCopter 4.6.3, PROVISIONAL params, **ExternalNav from the GROUND-TRUTH-DERIVED plumbing stub (plumbing test only, not navigation performance)**. LOITER hover (30 s window) and ExternalNav loss (50 s window, stub stopped 5 s into it). Drift = max horizontal distance from the window start, from Gazebo truth. Logs: `logs/sim-step2-profiles/`.

| Profile | Hover: max drift | Hover: mean pitch / roll lean | Hover: roll / pitch std (peak) | Hover: alt err max | Loss test: max drift in window | Loss test: max excursion after loss | Verdict |
|---|---|---|---|---|---|---|---|
| ideal | 2.2 cm | 0.00° / 0.00° | 0.01° (0.06) / 0.05° (0.24) | 1.1 cm | 1.0 cm | 1.4 cm | PASS |
| nominal | 3.2 cm | −0.14° / 0.05° | 0.04° (0.26) / 0.06° (0.25) | 2.0 cm | 1.8 cm | 1.9 cm | PASS |
| degraded | **27.1 cm** | −1.53° / 0.36° | 1.11° (3.03) / 1.32° (3.83) | 7.5 cm | 27.2 cm | 21.4 cm | PASS (stable) |

- Degraded drift is wind-driven: the stub keeps the EKF on truth, and a 0.36 N-class steady wind with ±80 % gusts leaves a ~1.5° lean. The IMU degradation alone (earlier separation test with the old wind scaling) gave 1.5 cm drift; do not read the 27 cm as an IMU result.
- **ExternalNav-loss behaviour is unchanged by the profiles:** in all three, `EKF3 IMU0/IMU1 stopped aiding` at **+15 s** after the loss and **no failsafe and no mode change** (LOITER stayed). The safety finding (`docs/phase3-sitl.md` §10.4, options (a)–(d) for Rohit) stands. The truth excursion after the loss stayed ≤ 21 cm within the ~45 s window in every profile, so the window shows no runaway; it says nothing about longer losses.
- The first `degraded` attempt (before the wind law was measured) used 15× the intended force and went unstable (pitch 30°, 1.4–3.6 m drift). Those runs were discarded as a mis-parameterised profile, not a vehicle result.
- Not tested: any profile in the NIDAR maze flight, longer windows, or the real SLAM.
