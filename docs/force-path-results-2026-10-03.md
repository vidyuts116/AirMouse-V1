# AirMouse V1 force-path results — 2026-10-03

Labels: **OBSERVED** (measured in a live run or a recorded trace), **SOURCE-CODE VERIFIED** (read in code in this repo), **ANALYTICAL** (computed from SDF parameters), **INFERRED** (reasoned, not directly measured), **NOT VERIFIED** (not checked).

## 1. Summary

The force chain from rotor speed to vertical body acceleration is **verified**. Once all four rotors are at the commanded speed, the measured vertical acceleration equals the analytical value to four significant figures, on the unmodified protected SDF, at both test speeds:

| ω (rad/s) | predicted a_z (m/s²) | measured a_z (m/s²) | label |
|---|---|---|---|
| 586.8 | +0.001896 | +0.00190 | OBSERVED (live) |
| 700.0 | +4.152681 | +4.15268 | OBSERVED (live) |

The fall from 2.0 m to 0.22 m has two causes, and neither is a fault in the force path:

1. For about 0.25 s of simulation time after unpause, the rotors are not commanded (OBSERVED). The vehicle free-falls and reaches about −2.73 m/s.
2. The command is open loop and almost exactly hover: 586.8 rad/s against a hover speed of 586.743 rad/s (ANALYTICAL). The vehicle therefore keeps its fall velocity, which is the expected physics.

**Update (follow-up session, same date):**

- **Per-joint sensors.** The force/torque sensors read **+2.93376 N** axial per rotor when spun up and **−0.00981 N** with the motors stopped (OBSERVED). The sign convention is explained in §9b.
- **Clean hover passes.** With the fixed harness, the hover acceptance test **PASSES** on both the diagnostic SDF and the baseline SDF: a_z = +0.00190 m/s² and max |z − 2| = 0.0083–0.0084 m over 2 s. Command-to-first-non-zero-joint delay is **5 ms of simulation time**, which is one 200 Hz sample, against 254 ms with the old harness.
- **New geometric defect (OBSERVED).** Each rotor joint axis sits 0.4 m outboard of its rotor, and the rotor links **orbit** that axis. Each joint carries a 137.7 N centripetal load. The vertical force path is unaffected, and in symmetric hover the effects cancel exactly. See §9b and §11.

**Update 2: approved joint-frame fix, applied (§9c).**

- **Change.** In each `rotor_i_joint`, `<pose>` changed from the arm coordinates to `0 0 0 0 0 0`. **Physics parameters changed: none (joint frame placement only).**
- **Baseline SDF SHA-256.**
  - Old: `5a72f8bac558ddecf76091790d8d3515e9d77e6da2956fbe3a61d7bd78131957`
  - **New: `92baa42b6fb1d1a45f4e702c292dbf46c2a473909f4b909659690007eedabc02`**
- **Rotors and joints (OBSERVED).** Rotor links stay at exactly (±0.282843, ±0.282843) relative to the base, and the in-plane joint force and torque are 0. The axial force is unchanged at 2.93376 N.
- **Hover acceptance (OBSERVED).** It passes on both the fixed diagnostic copy and the new baseline.
- **Differential thrust, fixed geometry (OBSERVED).** Measured angular acceleration over the analytical value (with rotor point-mass inertia) is **0.9992 / 0.9993 / 0.9995** for the roll, pitch and yaw patterns.
- **Differential thrust, old geometry (OBSERVED).** The yaw response was **55.9×** the prediction. In the pitch pattern, pitch was 8.8× the prediction, with 110° of cross-coupled roll and 1.27 m of drift in 0.35 s.

## 2. Scope and hard-rule compliance

- During the first two sessions, the protected SDF was never modified. Its SHA-256 was the same before and after each session (OBSERVED, see §3). In the third session, the approved joint-frame fix was applied to it (§9c).
- No physics parameters, Gazebo version, ROS 2 or ArduPilot were changed. Everything ran on native macOS with `PATH="/opt/homebrew/bin:$PATH"`, Gazebo Sim 8.15.0, headless server only (`gz sim -s -r`). No GUI was needed.
- Before each run, no other motor publisher was active. The `gz topic -i` audit showed `publishers=0, subscribers=4`, and `pgrep` found no `gz sim` or `airmouse_motor_publisher` processes.

## 3. SDF integrity

```
before: 5a72f8bac558ddecf76091790d8d3515e9d77e6da2956fbe3a61d7bd78131957
after:  5a72f8bac558ddecf76091790d8d3515e9d77e6da2956fbe3a61d7bd78131957
```

**Update:** after the approved joint-frame fix (§9c), the baseline hash is `92baa42b6fb1d1a45f4e702c292dbf46c2a473909f4b909659690007eedabc02`. The pre-fix file is preserved byte-for-byte as `backups/airmouse_quadrotor.sdf.5a72f8ba.pre-jointfix`, whose SHA-256 is the old hash above (OBSERVED).

The handover hash has 63 digits: `5a72f8bac558ddec76091790…`. The missing digit is the **`f` at position 17** (1-based), between `…ddec` and `7609…`. Re-inserting that `f` gives exactly the full hash above (OBSERVED, checked by script).

## 4. Deviation: probe package missing

`~/Downloads/airmouse_force_probe/` does not exist. A search of `~` to depth 5 found no `force_probe`, `analyse_fall_trace*`, `inspect_airmouse_sdf*` or `force-path-investigation*`. As a result:

- Step 1 (copy) was not possible, so nothing was copied and no names clashed.
- Steps 2 and 3 were done by reading the SDF directly and by an equivalent analysis in Python/numpy, not with the named scripts.
- Steps 5–7 (build and run the C++ force probe, check the arm-phase joint-force sign) were **NOT VERIFIED**. Instead, live runs of the existing `tools/measure_airmouse_diagnostic.py` measured body acceleration directly (§9). That covers the end-to-end chain but not the per-joint force.
- The prior analysis doc `force-path-investigation-2026-10-03.md` was not available. Its claims are taken from the task description.

## 5. SDF inspection (`simulation/airmouse_quadrotor.sdf`)

All values below are SOURCE-CODE VERIFIED by reading the file.

- **World:** `airmouse_physics`, gravity (0, 0, −9.81), max step 1 ms, real-time factor 1.0. Plugins: Physics, SceneBroadcaster, UserCommands.
- **Mass:** `base_link` 1.196 kg plus 4 × 0.001 kg rotors = **1.200 kg**. Weight is 11.772 N (ANALYTICAL).
- **Rotor links:** `rotor_0..3` at (±0.282843, ±0.282843, 0) with zero roll, pitch and yaw. Each rotor's +Z axis is therefore parallel to body +Z (0, 0, 1).
- **Joints:** `rotor_N_joint`, type `revolute`, axis `0 0 1`, limits ±1e16 rad. There is **no `<effort>` or `<velocity>` limit element**, so the SDF defaults apply (effort −1 means unlimited). There is no `<dynamics>` element.
- **Motor plugins:** four `MulticopterMotorModel` plugins with these settings:
  - namespace `airmouse`, topic `gazebo/command/motor_speed`, actuators 0–3
  - turning direction ccw / cw / ccw / cw
  - `motorType` velocity, `maxRotVelocity` 800
  - `motorConstant` 8.54858e-06, `momentConstant` 0.016
  - `timeConstantUp` 0.0125, `timeConstantDown` 0.025
  - `rotorDragCoefficient` 0, `rollingMomentCoefficient` 0
  - **`rotorVelocitySlowdownSim` 1**, so the joint speed equals the real rotor speed and there is no hidden scaling
- **Model spawn pose:** z = 1.5 m. The test tools reset the pose to z = 2.0 m.

Two diagnostic copies exist (SOURCE-CODE VERIFIED by diff):

- `simulation/diagnostics/airmouse_joint_velocity.sdf` adds only a `JointStatePublisher`.
- `simulation/diagnostics/airmouse_force_diagnostic.sdf` also adds a `ForceTorque` system and per-joint force_torque sensors.

Neither copy changes any physics parameter.

## 6. Analytical predictions

| Quantity | Value |
|---|---|
| Per-rotor thrust at 586.8 rad/s, k·ω² | 2.943569 N along rotor +Z, i.e. (0, 0, +2.9436) N |
| Total thrust at 586.8 rad/s | 11.774275 N, which is 0.0023 N above weight |
| a_z at 586.8 rad/s | (11.774275 − 11.772)/1.2 = **+0.001896 m/s²** |
| a_z at 700 rad/s | (4·k·700² − 11.772)/1.2 = **+4.152681 m/s²** |
| Exact hover speed | √(m·g / 4k) = **586.743 rad/s** |
| Arm-phase joint reaction | m_rotor·g = 0.001·9.81 = 0.00981 N (the expected +0.0098 N) |

All values in this table are ANALYTICAL.

## 7. Recorded trace analysis (`airmouse_joint_velocity_20261003_153501.csv`)

The header is `sim_time_s`, `rotor_N_joint_measured_rad_s` (N = 0–3) and `airmouse_z_interpolated_m`. There are 158 rows at 5 ms spacing, covering t = 27.535–28.320 s (0.785 s), with z going from 1.99958 to 0.22320 m. The trace was recorded on the joint-velocity diagnostic copy, which is physically identical to the protected SDF (§5).

All values below are OBSERVED from the CSV.

- **Before spin-up:** all four joints read exactly 0. The fitted acceleration is −9.8123 m/s², which is free fall.
- **Spin-up:** the first non-zero joint speed is at t − t0 = 0.255 s (45.1 rad/s). Back-extrapolating the first-order response puts command arrival at **t − t0 = 0.254 s**. The time constant fitted from successive samples is **0.0125 s** on every step, which matches `timeConstantUp`.
- **Rotor speeds:** all joints are ≥95 % of target at 0.295 s and exactly ±586.800 from 0.425 s. Signs are + − + −, which matches ccw/cw.
- **After spin-up:** the fitted acceleration is **+0.00190 m/s²** over 71 samples (0.35 s), and the velocity holds at −2.729 m/s.
- **Trajectory reconstruction:** integrating a = Σk·ω²/m − g from the **measured** ω reproduces the measured z with a maximum error of 4.6 mm (RMS 2.6 mm). The predicted end is 0.2186 m against 0.2232 m measured. A zero-thrust model would predict −1.065 m. This reconstruction is ANALYTICAL and checked against OBSERVED data.

## 8. Latency source (step 4)

The following sequence is SOURCE-CODE VERIFIED in `measure_airmouse_diagnostic.py:348–397` and `measure_airmouse_joint_velocity.py:199–239`:

1. A **zero-speed** publisher process is started. The world is paused, `reset {model_only}` is called, and `set_pose` places the model at z = 2.
2. The scripts wait until the paused pose stream shows z = 2.0.
3. `stop_publisher(zero)` sends SIGUSR1, sleeps 0.12 s, then sends SIGTERM.
4. `start_publisher(binary, speed)` launches a **new process**, which creates a new `gz::transport::Node` and calls `Advertise`, then the script sleeps 0.15 s.
5. `gz service … pause: false` runs as a separate CLI process.

`airmouse_motor_publisher.cc:56–59` publishes at 20 Hz and deliberately does not gate on `HasConnections()`. Gazebo Transport does not queue messages for subscribers that are not yet connected, so anything published before the subscriber connects is dropped.

On timing, the following is OBSERVED and INFERRED as marked:

- The publisher process starts while the simulation is paused, so its start-up alone consumes no simulation time.
- Even so, the first command reaches the motor model about 0.25 s of simulation time after unpause. This was OBSERVED as 0.254 s in the recorded trace and as a departure from free fall at about 0.24–0.26 s in both live runs.
- The delay must therefore be the new publisher being discovered and its subscribers connecting, which finishes only after unpause. The 0–50 ms quantisation from the 20 Hz publish period adds to this. This attribution is INFERRED; the per-stage wall-clock split was **NOT VERIFIED**.
- The zero publisher is already stopped, and after reset the motor model holds a zero or no reference, so the rotors stay at 0 during that gap. This is OBSERVED: joint ω = 0.

## 9. Live verification on the protected SDF (step 6 substitute)

The server ran `gz sim -s -r simulation/airmouse_quadrotor.sdf`. The client was `python3 tools/measure_airmouse_diagnostic.py <ω> --duration 1.0`, and the server was restarted between runs. Pose samples are about 17 ms apart.

All values below are OBSERVED.

| | 586.8 rad/s | 700 rad/s |
|---|---|---|
| Pre-command a_z (fit 0.04–0.22 s) | −9.81000 | −9.81000 |
| Departure from free fall (>1 mm) | t = 0.307 s | t = 0.307 s |
| Powered a_z (fit t > 0.40 s) | **+0.00190** (n=26) | **+4.15268** (n=37) |
| End state | ground contact at t=0.84 s (z 0.0773) | airborne, z 0.5146 at t=1.008 s, decelerating |

The departure from free fall shows the 0.25 s delay. The 586.8 rad/s run repeats the handover fall on the protected SDF itself. Per-sample second differences settle at +0.002 and +4.153 m/s² and stay flat.

## 9b. Follow-up: force/torque sensors and clean hover acceptance

**Baseline SHA-256 (full, 64 hex digits):** `5a72f8bac558ddecf76091790d8d3515e9d77e6da2956fbe3a61d7bd78131957`. It was unchanged before and after every run in this follow-up (OBSERVED). The handover's 63-digit value was missing the `f` at position 17. Apart from the shortened quote in §3, which explains the missing digit, no other file in `docs/` contained the incorrect 63-digit string (OBSERVED by `grep -rn 5a72f8 docs/`).

### Harness

The fixed harness consists of two new files. The existing `measure_*` tools were not edited.

- **`tools/airmouse_hover_helper.cc`** is one persistent process. It advertises the motor topic, publishes at 100 Hz starting at 0 rad/s, and accepts `speed X` on stdin. It also subscribes to `/airmouse/diagnostic/joint_state` and timestamps the first sample in which all four joint speeds are non-zero after a command.
- **`tools/airmouse_hover_acceptance.py`** runs the test in this order:
  1. Audit the topic: it must show 0 publishers and 4 subscribers.
  2. Start the helper at 0 rad/s.
  3. Poll `gz topic -i` until it lists publishers=1 and subscribers=4, and the helper reports `HasConnections()`=1.
  4. Wait until the vehicle has rested on the ground for 0.5 s of simulation time.
  5. Command 586.8 rad/s and wait 1.0 s of simulation time.
  6. Call `set_pose` to z = 2 m.
  7. Record 2 s of simulation time.

  It compiles the helper the same way as the existing tool (Apple Clang, `pkg-config gz-transport13 gz-msgs10`) with no compile errors.

### Force/torque sensors, 586.8 rad/s

These readings come from the diagnostic SDF `simulation/diagnostics/airmouse_force_diagnostic.sdf` with `<frame>child</frame>` at 200 Hz. All values are OBSERVED phase means. The standard deviation is below 1e-12 N in every phase.

| Phase | Fz per rotor (all four identical) | Fx, Fy | Torque |
|---|---|---|---|
| Ground, motors stopped (n=72) | **−0.00981 N** | 0 | (±0.00277, ±0.00277, 0) N·m |
| Ground, spun up (n=100) | **+2.93376 N** | ±97.3925 N each | (±0.82979, ±0.82979, 0) N·m |
| Airborne at z ≈ 2 m, spun up (n=390) | **+2.93376 N** | ±97.3925 N each | (±0.82979, ±0.82979, 0) N·m |

Per-rotor signs of (Fx, Fy): rotor_0 (−,−), rotor_1 (+,−), rotor_2 (+,+), rotor_3 (−,+).

**Comparison with the expected values:**

- **Axial force when spun up:** 2.93376 N = k·ω² − m_r·g = 2.943569 − 0.00981. This matches the expected "about 2.934 N" to 5 significant figures.
- **Magnitude with motors stopped:** 0.00981 N, matching the expected 0.0098 N. The **sign is negative**, not the +0.0098 N given in the brief.

**Sign convention (OBSERVED; interpretation INFERRED):** the sensor reports the force **exerted by the child (rotor) on the parent (base)**, expressed in the rotor frame. This is consistent with SDF's default `child_to_parent` measure direction.

- With the motors stopped, the rotor hangs its weight on the base, giving −Z.
- With the rotors spun up, the rotor pulls the base up with its thrust minus its own weight, giving +Z.

**Geometric finding (OBSERVED):**

- **Mechanism.** The joint `<pose>` (±0.282843, ±0.282843, 0) is resolved relative to the **child link**, which is the SDF ≥1.7 default. Each revolute axis therefore sits at **(±0.5657, ±0.5657)**, twice the intended arm position, and 0.400 m from its rotor's centre of mass.
- **Static evidence.**
  - With the motors stopped, the torque equals 0.00981 N × 0.2828 m on each horizontal axis.
  - With the rotors spun up, |Fxy| = 97.3925·√2 = **137.73 N**. This equals m_r·ω²·r = 0.001 × 586.8² × 0.400 = 137.73 N, the centripetal load.
- **Live position samples.** Rotor link positions sampled from `/world/airmouse_physics/pose/info` while spinning were rotor_0 at (0.1735, 0.6446), (0.3129, 0.2557) and (0.9657, 0.5672). Each is exactly 0.400 m from (0.5657, 0.5657). The four rotors are mirror images across the x and y axes.
- **Why hover is unaffected (ANALYTICAL).** Because of that mirror symmetry (ccw/cw pairs and the same command), the sum of rotor positions stays at zero. The net in-plane force and the roll/pitch moment cancel exactly. This is consistent with the measured base x/y drift of 0.00000 m and tilt of 0.0000°. The vertical thrust path is unaffected.

### Hover acceptance, 586.8 rad/s

All values are OBSERVED. The criteria are |a_z − 0.0019| < 0.05 m/s² and |z − 2.0| < 0.02 m over 2 s.

| World | a_z (fit, 2 s) | v₀ at reset | max \|z−2.0\| | Tilt / drift | Result |
|---|---|---|---|---|---|
| Diagnostic SDF | +0.00190 m/s² | +0.00231 m/s | 0.00839 m | 0 / 0 | **PASS** |
| Baseline `airmouse_quadrotor.sdf` | +0.00190 m/s² | +0.00227 m/s | 0.00829 m | 0 / 0 | **PASS** |

The connection gate passed after 4.64 s and 2.20 s of wall time respectively.

**Where the z deviation comes from (ANALYTICAL):**

- v₀ ≈ +0.0023 m/s is the climb picked up on the ground. Thrust exceeds weight by 0.0023 N, so the vehicle rose from z 0.0400 to 0.0407 m over the 1 s spin-up.
- `set_pose` evidently preserves that velocity (INFERRED).
- The predicted deviation is v₀·2 + ½·0.0019·2² = 0.0084 m, which matches the measured value.

**Command-to-first-non-zero-joint delay (OBSERVED):**

| Run | Simulation time | Wall time |
|---|---|---|
| Acceptance run | **0.005 s** (cmd 103.725 → 103.730) | 2.7 ms |
| Repeat manual run | 0.010 s | 7.7 ms |

The resolution is limited by the 200 Hz joint-state rate. The old harness measured 0.254 s.

### Artifacts

- `logs/force-path-2026-10-03/diag_run/`: `hover_586.8_pose.csv`, `hover_586.8_wrench.csv` and `hover_586.8_events.txt`, from the diagnostic SDF.
- `logs/force-path-2026-10-03/baseline_run/`: pose and events files from the baseline SDF.

## 9c. Approved joint-frame fix, verification and differential-thrust test

### Fixed diagnostic copy

The fixed diagnostic copy is `simulation/diagnostics/airmouse_force_diagnostic_jointfix.sdf`, SHA-256 `acb67b617b0ac7180121add5c399ce903fe8fa9b67086c1233b4f27290e515fc`. It was made from `airmouse_force_diagnostic.sdf` (`d4c344a5…`) by changing only the `<pose>` inside each `rotor_i_joint`:

```diff
- <joint name="rotor_0_joint" …><parent>base_link</parent><child>rotor_0</child><pose>0.282843 0.282843 0 0 0 0</pose>…
+ <joint name="rotor_0_joint" …><parent>base_link</parent><child>rotor_0</child><pose>0 0 0 0 0 0</pose>…
  (same for rotor_1 (-0.282843 0.282843), rotor_2 (-0.282843 -0.282843), rotor_3 (0.282843 -0.282843))
```

The line-by-line diff has 8 lines: 4 removed and 4 added. No other element changed. The rotor `<link>` poses keep their arm coordinates.

### Step 1: verification at 586.8 rad/s on the fixed copy

All values are OBSERVED.

| Check | Old geometry | Fixed geometry |
|---|---|---|
| Rotor link position relative to model, during airborne hover (n=27) | radius 0.407–1.200 m (orbiting) | **exactly (±0.282843, ±0.282843)**, deviation 0.000000 m |
| In-plane joint force per rotor | (±97.3925, ±97.3925) N | **0.000000 N** (peak) |
| Joint torque per rotor | (±0.8298, ±0.8298, 0) N·m | **0.000000 N·m** (peak) |
| Axial joint force, spun up | +2.933757 N | **+2.933757 N** |
| Joint force with motors stopped (ground) | Fz −0.00981 N, torque ±0.00277 N·m | Fz −0.00981 N, **torque 0** |
| Hover acceptance (a_z, max \|z−2\|) | PASS (+0.00190, 0.00839 m) | **PASS** (+0.00190 m/s², 0.00826 m) |
| Command → first non-zero joint delay | 5 ms simulation time | 5 ms simulation time (4.8 ms wall) |

### Step 2: differential-thrust moment-arm test

The test is `tools/airmouse_differential_thrust.py`, with ω = 586.8 rad/s and Δ = 5 rad/s. For each pattern:

1. The vehicle rests on the ground, so its angular velocity is 0.
2. All rotors spin at 586.8 rad/s for 1 s.
3. `set_pose` moves it to z = 2 m, and it hovers for 0.1 s at equal speeds.
4. The pattern is commanded and recorded for 0.35 s.

The angular acceleration is the 2× quadratic coefficient of a fit to the Euler angle over 0.08–0.35 s after the command. The 0.08 s start is more than 3 × the 0.025 s motor fall time constant.

**Analytical values (ANALYTICAL):**

- Per-rotor thrust change: ΔF(up) = k·(591.8² − 586.8²) = +0.0503768 N and ΔF(down) = −0.0499494 N. ΣΔF across the four rotors is 0.2006524 N.
- Roll/pitch torque: τ = 0.282843 · ΣΔF = 0.0567531 N·m.
- Yaw torque: τ = 0.016 · ΣΔF = 0.0032104 N·m. The sign follows the reaction-torque convention, where a ccw rotor pushes the body −z.
- Two inertias are compared:
  - **I_base** = (0.018, 0.018, 0.032), as given in the brief.
  - **I_rigid** = I_base + 4·m_r·r², which adds the rotor point masses at the arm positions: (0.01832, 0.01832, 0.03264) kg·m².

Pattern definitions:

- **yaw:** rotors 0 and 2 up, 1 and 3 down
- **roll:** the +y pair (0, 1) up, the −y pair (2, 3) down
- **pitch:** the +x pair (0, 3) up, the −x pair (1, 2) down

**Primary axis (OBSERVED measurement, ANALYTICAL prediction):**

| Pattern / axis | α pred, I_base (rad/s²) | α pred, I_rigid | **Fixed: measured** | Fixed: ratio to I_rigid | **Old: measured** | Old: ratio to I_rigid |
|---|---|---|---|---|---|---|
| roll / roll | +3.15295 | +3.09788 | **+3.09554** | **0.9992** | +2.91161 | 0.940 |
| pitch / pitch | −3.15295 | −3.09788 | **−3.09574** | **0.9993** | −27.31571 | 8.82 |
| yaw / yaw | −0.10033 | −0.09836 | **−0.09831** | **0.9995** | −5.49337 | 55.9 |

**Cross-axis coupling and drift over the 0.35 s window (OBSERVED):**

| Pattern | Fixed geometry | Old geometry |
|---|---|---|
| roll | pitch and yaw α = 0.00000; drift 0.0141 m | pitch α −1.23 rad/s², **yaw +169°** at window end; drift 0.031 m |
| pitch | roll α −0.00001, yaw α +0.00005; drift 0.0148 m | **roll −110°, yaw −59°** at window end; drift **1.27 m** |
| yaw | roll and pitch 0; drift 0 | roll and pitch 0; yaw −18.1° at end (prediction about −0.4°) |
| equal (control) | 0 on all axes | 0 on all axes (mirror cancellation) |

Fit residuals: fixed geometry RMS 7e-8 to 3e-6 rad; old geometry 1e-3 to 2e-2 rad. Old-geometry angles become large within the window, so the old-geometry α values are **indicative only** (small-angle quadratic fit).

**Interpretation:**

- **Fixed geometry (OBSERVED and ANALYTICAL).** The moment arm is 0.282843 m. The measured α matches τ/I to within 0.08 %, once the rotor point masses are included in the inertia. Against I_base alone, the measured/predicted ratio is 0.982, which is exactly the inertia ratio 0.018/0.01832.
- **Old geometry: effect sizes (OBSERVED).** Any thrust asymmetry produces errors from −6 % to +5,490 %, plus large cross-axis coupling.
- **Old geometry: likely causes (INFERRED).**
  - The mirror symmetry that cancels the 137.7 N orbital loads breaks as soon as the rotor speeds differ.
  - Each rotor's inertia about the offset axis (m·r² = 1.6e-4 kg·m², 160× its own 1e-6) produces large reaction torques while it spins up or down.
  - The thrust application point sweeps a 0.4 m circle around a joint centre at about 0.80 m radius.
  - The roll and pitch patterns behave differently despite the nominal symmetry, which suggests the response depends on the orbit phase at the moment of the command.

### Step 3: change applied to the baseline

| | |
|---|---|
| File | `simulation/airmouse_quadrotor.sdf` |
| Old SHA-256 | `5a72f8bac558ddecf76091790d8d3515e9d77e6da2956fbe3a61d7bd78131957` |
| **New SHA-256** | **`92baa42b6fb1d1a45f4e702c292dbf46c2a473909f4b909659690007eedabc02`** |
| Backup of old file | `backups/airmouse_quadrotor.sdf.5a72f8ba.pre-jointfix`, SHA-256 identical to the old hash |
| Diff | `logs/force-path-2026-10-03/baseline_jointfix.diff`: lines 31–34, the four `rotor_i_joint` `<pose>` values set to `0 0 0 0 0 0`; 4 lines removed, 4 added |
| **Physics parameters changed** | **none (joint frame placement only)** |

The new baseline contains no content that differs from the fixed diagnostic copy except the diagnostic-only sensor and JointStatePublisher additions (OBSERVED by diff).

### Re-tests on the new baseline

All values are OBSERVED; the a_z predictions are ANALYTICAL.

| Test | Result |
|---|---|
| Hover acceptance at 586.8 rad/s (new harness) | **PASS**: a_z +0.00190 m/s², max \|z−2\| 0.00831 m, v₀ +0.00229 m/s, tilt 0, drift 0 |
| a_z at 586.8 rad/s (`measure_airmouse_diagnostic.py`, window 0.477–0.742 s) | **+0.00190 m/s²** (prediction +0.001896) |
| a_z at 700 rad/s (`measure_airmouse_diagnostic.py`, window 0.511–0.809 s) | **+4.15268 m/s²** (prediction +4.152681) |
| a_z at 700 rad/s (new harness, 0.15 s spin-up, 1 s record) | +4.15452 m/s² (+0.04 %) |

**Notes on the a_z windows:**

- In these old-harness runs, the command arrived late again: free fall departed at 0.341 s and 0.375 s, against 0.307 s earlier (OBSERVED). This is the known harness latency (§8).
- The original fixed fit window, t > 0.40 s, therefore overlapped the spin-up and, at 700 rad/s, ground contact. That window gave +0.00188 and +6.42 m/s². The 6.42 m/s² value is contaminated by ground contact and is **not** a valid measurement.
- The windows in the table run from departure + 0.12 s, when the rotors are above 99 % of speed, until z first drops below 0.15 m. They were fitted with `logs/force-path-2026-10-03/fit_window.py`.
- The new-harness 700 rad/s run lifted off during spin-up and reached v₀ = +1.90 m/s at reset. Its PASS/FAIL lines apply the 586.8 rad/s hover criteria and are not meaningful at 700 rad/s. The 0.04 % excess in a_z was not investigated (NOT VERIFIED).

The baseline SHA-256 was `92baa42b…bc02` after all re-tests (OBSERVED). No Gazebo or helper processes were left running.

## 10. Comparison with predictions

| Prediction | Result | Status |
|---|---|---|
| a_z +0.0019 m/s² at 586.8 rad/s | +0.00190 | matches |
| a_z +4.153 m/s² at 700 rad/s | +4.15268 | matches to 5 significant figures |
| Per-rotor force (0, 0, +2.9436) N at 586.8 rad/s | Implied by total a_z with symmetric ω (Σ = 11.7743 N). Not measured per joint. | Total is OBSERVED; per-rotor value is INFERRED from symmetry |
| Arm-phase joint force about +0.0098 N | −0.00981 N: magnitude matches, sign is negative under the child-on-parent convention (§9b) | OBSERVED |
| Spun-up axial force about 2.934 N | +2.93376 N on every rotor, ground and airborne | OBSERVED |
| Clean hover: \|a_z−0.0019\| < 0.05, \|z−2\| < 0.02 over 2 s | +0.00190 m/s², 0.0083–0.0084 m | **PASS** (OBSERVED) |

## 11. Where the evidence locates the fault

The chain was checked link by link. The conclusion is that **there is no fault in the force path**.

| Link in the chain | Status | Evidence |
|---|---|---|
| Command reaches the motor model | OK, with about 0.25 s delay | OBSERVED |
| Motor model drives the joint to ω with τ = 0.0125 s | OK | OBSERVED |
| Joint ω produces force k·ω² on the rotor link along +Z | OK | OBSERVED via a_z |
| Force is transmitted to the body and integrated by physics | OK | OBSERVED |

**Follow-up:** with the motor-publisher start-up removed from the measured window, the same baseline SDF hovers within 8.4 mm over 2 s, which confirms the harness diagnosis (OBSERVED).

There was a separate **geometric defect** in the baseline SDF: rotor joint axes sat at twice the arm position, and the rotor links orbited at 0.4 m (OBSERVED, §9b). It did not affect vertical force or symmetric hover. Its effect under unequal rotor speeds is now **measured** (§9c, OBSERVED): yaw response was 55.9× the prediction, pitch 8.8×, with up to 110° of cross-axis coupling in 0.35 s. That would have made attitude control impossible. **The defect is fixed** in baseline `92baa42b…bc02`. On the fixed geometry, roll, pitch and yaw moment arms match the analytical values to within 0.08 % (OBSERVED).

The fall comes from the **test harness**: the vehicle spends about 0.25 s in free fall before the rotors are commanded, and then holds an open-loop near-exact hover command, which keeps the −2.73 m/s it has gained. This conclusion is OBSERVED and ANALYTICAL. The earlier inference is now verified, except for the per-joint force sign.

## 12. Not verified / open items

- ~~Per-joint wrench and sign~~ have now been measured (§9b).
- ~~Rotor-orbit defect under asymmetric commands~~ has now been measured and fixed (§9c).
- Why the old-geometry response depends on orbit phase is INFERRED only. It no longer matters after the fix.
- Behaviour under realistic closed-loop commands, for example ArduPilot, on the fixed geometry (NOT VERIFIED).
- Whether `set_pose` preserves linear velocity. This is INFERRED from v₀; it was not checked against Gazebo source.
- The split of the 0.25 s delay into discovery, connection and publish-phase contributions.
- Whether `reset {model_only}` clears the motor model's stored reference. This does not matter here because the reference was 0.

## 13. Recommendations

- Start the speed publisher **before** pausing and resetting, using one long-lived process whose velocity is changed in place, as the existing SIGUSR1 mechanism already allows. Alternatively, wait for `HasConnections()` before unpausing. Either removes the free-fall gap.
- Do not expect an open-loop hover command to hold altitude. Hover speed is 586.743 rad/s, and any velocity built up before spin-up persists. Altitude hold needs closed-loop control, for example through ArduPilot.

- ~~Rotor joint geometry~~ was **approved and applied** (§9c).
- Use `tools/airmouse_hover_acceptance.py` as the harness from now on. The `measure_*` tools still contain the variable 0.25–0.37 s command latency, so their fit windows must be chosen from the data.
- Re-run `tools/airmouse_differential_thrust.py --label <name>` after any future geometry or inertia change.

## 14. Artifacts

- `logs/force-path-2026-10-03/live_586.8.csv` and `live_700.csv`: live pose traces from the protected SDF.
- `logs/force-path-2026-10-03/fit.py`: free-fall and powered-phase fitting script. Usage: `python3 fit.py <csv> 0.40`.
- Recorded trace: `airmouse_joint_velocity_20261003_153501.csv` (unchanged).
- Server logs (scratchpad only) contained no errors or warnings.
- `logs/force-path-2026-10-03/jointfix_diag_run/`: hover acceptance with force/torque data on the fixed diagnostic copy.
- `logs/force-path-2026-10-03/differential/`: `differential_{fixed,old}.txt`, pose CSVs and marks.
- `logs/force-path-2026-10-03/new_baseline/`: hover acceptance, `live_586.8.csv`, `live_700.csv` and `hover700/`.
- `logs/force-path-2026-10-03/baseline_jointfix.diff` and `fit_window.py`.
- New tools: `tools/airmouse_differential_thrust.py`. `tools/airmouse_hover_helper.cc` now also accepts `speeds a b c d`.
