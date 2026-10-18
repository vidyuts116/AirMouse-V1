# AirMouse Phase 3: ArduPilot SITL ↔ Gazebo, groundwork and decisions needed (2026-10-03)

**Status: decisions confirmed and applied (see docs/phase3-sitl.md).** Original groundwork notes below are kept for history.

## Inventory (OBSERVED, 2026-10-03)

| Item | State |
|---|---|
| ArduPilot source / `arducopter` SITL binary / `sim_vehicle.py` / `waf` | **not present** |
| MAVProxy, pymavlink, empy, future, lxml (Python) | **not installed** |
| `ardupilot_gazebo` plugin (`ArduPilotPlugin`) | **not present**; `GZ_SIM_SYSTEM_PLUGIN_PATH` unset |
| Gazebo dev packages | gz-sim8 8.15.0, gz-plugin2 2.0.4, gz-sensors8 8.2.2, gz-msgs10 10.4.0, gz-transport13 13.6.0, sdformat14 14.9.0, rapidjson 1.1.0, gz-cmake3 3.6.0, cmake 4.4.3. These are enough to build a Gazebo system plugin. |
| Compilers | Apple clang 17.0.0 (Command Line Tools); no `ninja`; no ARM toolchain (not needed for SITL) |
| Python | Homebrew 3.14 only (`/opt/homebrew/bin/python3.14`), plus system 3.9.6 |
| Baseline | `simulation/airmouse_quadrotor.sdf` `21626e64…a88f`. The IMU at 200 Hz on `/airmouse/imu` is suitable as the SITL IMU source, and the motor input is `gz.msgs.Actuators` on `/airmouse/gazebo/command/motor_speed`, in rad/s. |

**Rotor layout vs ArduPilot (OBSERVED from the SDF; ArduPilot reference INFERRED from documentation, not yet checked against source):**

| Actuator | Link | Position | Spin |
|---|---|---|---|
| 0 | rotor_0 | front-left | ccw |
| 1 | rotor_1 | back-left | cw |
| 2 | rotor_2 | back-right | ccw |
| 3 | rotor_3 | front-right | cw |

ArduPilot quad **X** (`FRAME_TYPE=1`) spins front-right and back-left CCW, and front-left and back-right CW. The AirMouse diagonal is **mirrored**: front-left and back-right are CCW. That matches ArduPilot's *BetaFlight X Reversed* (props-out) frame type (INFERRED; confirm the enum value in `AP_Motors` once the source is available).

## Proposed architecture (recommendation)

Keep the verified physics unchanged and connect ArduPilot SITL through its **JSON SITL interface** (UDP 9002):

```
arducopter (SITL, --model JSON)  <--UDP 9002 JSON-->  Gazebo system plugin  --> gz.msgs.Actuators (rad/s) --> MulticopterMotorModel (verified)
                                                        ^-- IMU (/airmouse/imu), pose/velocity from ECM
```

- **Option A, recommended:** the official `ardupilot_gazebo` `ArduPilotPlugin` (Harmonic build), plus a small adapter that converts its per-channel outputs into one `gz.msgs.Actuators` message. Physics and the verified motor model are unchanged.
- **Option B:** a small custom AirMouse system plugin that implements the JSON SITL protocol directly against `MulticopterMotorModel`. This avoids the external plugin dependency but means more code for us to own.
- **Option C, not recommended:** the stock `ardupilot_gazebo` iris approach, with `LiftDrag` and joint velocity PIDs. This **replaces the verified thrust model**, which is a physics change.

PWM → rad/s mapping, as a proposal: linear from 1000–2000 µs to 0–800 rad/s, matching `maxRotVelocity`. Hover is at 586.743 rad/s, 73.3 % of maximum (ANALYTICAL). With thrust ∝ ω², the expected `MOT_THST_HOVER` is about 0.54 (ANALYTICAL; to be confirmed in SITL).

## Decisions needed (you / Rohit)

1. **ArduPilot version and location:**
   - which tag, for example Copter stable 4.6.x or `master`
   - where to clone it, for example `~/Drone/src/ardupilot` (git-ignored) or `~/ardupilot`

   Cloning with submodules downloads roughly 1 GB from GitHub. This installs a new component, and the earlier rule was "don't change ArduPilot".
2. **Python environment:** only Python 3.14 is available. Compatibility of `waf`, `empy`, MAVProxy and pymavlink with 3.14 is NOT VERIFIED. The options are:
   - (a) a venv on 3.14, then test
   - (b) `brew install python@3.12` for a dedicated venv. This is an environment change.
3. **Bridge architecture:** A, B or C above. I recommend A, or B if we want no external plugin.
4. **Frame / motor order:**
   - (a) keep the SDF and use ArduPilot's BetaFlight-X-Reversed frame type with an explicit channel map; this has no physics change, and I recommend it
   - (b) swap the SDF turning directions to match standard quad X; this is a **physics change** and would need a full regression
5. **Ownership:** who owns the ArduPilot parameter set (frame, `MOT_*`, PWM range, failsafes) for the AirMouse SITL profile.

## Next steps once decided (no decision needed for these)

1. Clone and build SITL (`./waf configure --board sitl && ./waf copter`), then run `sim_vehicle.py -v ArduCopter --model JSON` against a stub, to check that the toolchain works on macOS.
2. Build the bridge plugin under `~/Drone/src/`, add it to a **diagnostic** world copy first, and confirm 4-motor PWM → rad/s → Actuators with the regression tool's sensors.
3. Run SITL acceptance in order:
   - arm
   - hover hold in `empty`
   - attitude steps, compared with the verified moment arms
   - position hold in `nidar_maze`

   Then a regression Stage 11.
