#!/usr/bin/env python3
"""AirMouse SITL motor test: MAVProxy `motortest` on each motor 1-4, checked against Gazebo joints.

Starts gz sim (SITL world), ArduCopter SITL (JSON model) and MAVProxy; verifies FRAME_CLASS /
FRAME_TYPE / SERVOn_FUNCTION; then for test sequence 1..4 runs `motortest N 1 <pwm> <s>` and checks
that only the expected Gazebo rotor spins, with the expected sign and speed. Vehicle stays on the
ground (single motor, sub-hover thrust). No takeoff.

`motortest` numbers motors by TEST ORDER (AP_MotorsMatrix::_output_test_seq). For BF_X_REV:
  test 1 -> M2 (SERVO2, FR, CW)  -> rotor_3, joint velocity < 0
  test 2 -> M1 (SERVO1, BR, CCW) -> rotor_2, joint velocity > 0
  test 3 -> M3 (SERVO3, BL, CW)  -> rotor_1, joint velocity < 0
  test 4 -> M4 (SERVO4, FL, CCW) -> rotor_0, joint velocity > 0
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pexpect

ROOT = Path(__file__).resolve().parent.parent
AP = ROOT / "src" / "ardupilot"
WORLD = ROOT / "simulation" / "sitl" / "empty_sitl.sdf"
PARM = ROOT / "simulation" / "sitl" / "airmouse_sitl.parm"
VENV = ROOT / ".venv-ardupilot" / "bin"
EXPECTED = {1: (3, -1, "M2 SERVO2 FR CW"), 2: (2, +1, "M1 SERVO1 BR CCW"),
            3: (1, -1, "M3 SERVO3 BL CW"), 4: (0, +1, "M4 SERVO4 FL CCW")}
EXPECTED_PARAMS = {"FRAME_CLASS": 1, "FRAME_TYPE": 18, "SERVO1_FUNCTION": 33, "SERVO2_FUNCTION": 34,
                   "SERVO3_FUNCTION": 35, "SERVO4_FUNCTION": 36, "MOT_PWM_MIN": 1000, "MOT_PWM_MAX": 2000}


def load(name):
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reg = load("airmouse_regression.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pwm", type=int, default=1300)
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument("--logdir", default=str(ROOT / "logs" / f"phase3-{date.today().isoformat()}"))
    args = parser.parse_args()
    os.environ["GZ_IP"] = "127.0.0.1"
    os.environ["PATH"] = f"{VENV}:/opt/homebrew/bin:" + os.environ["PATH"]
    # libArduPilotPlugin + libAirMouseActuatorsBridge, both built by src/airmouse_sitl_bridge/CMakeLists.txt
    os.environ["GZ_SIM_SYSTEM_PLUGIN_PATH"] = str(ROOT / "src" / "airmouse_sitl_bridge" / "build")
    log = reg.Log(Path(args.logdir))
    run = log.dir / f"motortest_{datetime.now():%H%M%S}"
    run.mkdir(parents=True, exist_ok=True)
    gz = reg.gz_bin()
    if reg.gz_sim_processes():
        raise SystemExit("a gz sim process is already running; stop it first")
    omega = 800.0 * (args.pwm - 1000) / 1000.0
    log(f"AirMouse SITL motor test {datetime.now().isoformat(timespec='seconds')}: pwm {args.pwm} -> "
        f"{omega:.1f} rad/s expected; world {WORLD.relative_to(ROOT)}")
    server = streams = sitl = mav = None
    ok = True
    try:
        server = reg.Server(gz, WORLD, run / "gz_server.log")
        time.sleep(6)
        streams = reg.Streams(gz, joints=True)
        sitl_log = open(run / "arducopter.log", "w")
        sitl = subprocess.Popen(
            [str(AP / "build" / "sitl" / "bin" / "arducopter"), "--model", "JSON", "--speedup", "1", "-w",
             "--defaults", f"{AP / 'Tools/autotest/default_params/copter.parm'},{PARM}",
             "-I0", "--home", "-35.363261,149.165230,584,0"],
            cwd=run, stdout=sitl_log, stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(3)
        # Interactive mode (no --non-interactive): MAVProxy only reads commands from the pty when interactive.
        mav = pexpect.spawn(f"{VENV / 'mavproxy.py'} --master tcp:127.0.0.1:5760 --state-basedir {run}",
                            encoding="utf-8", timeout=60, cwd=str(run))
        mav.logfile_read = open(run / "mavproxy.log", "w")
        mav.expect(["STABILIZE>", "Detected vehicle", "online system"], timeout=90)
        log("  MAVProxy connected to SITL")
        time.sleep(8)                                   # let parameters load / defaults settle
        for name, want in EXPECTED_PARAMS.items():
            mav.sendline(f"param show {name}")
            mav.expect(rf"{name}\s+(-?[\d.]+)", timeout=20)
            got = float(mav.match.group(1))
            ok &= log.check("params", name, got == want, f"{got:g}", want, "OBSERVED")
        if not ok:
            raise reg.StageFail("frame / servo parameters not as reviewed")
        for seq in range(1, 5):
            rotor, sign, desc = EXPECTED[seq]
            with streams.lock:
                t_start = streams.joints[-1][0] if streams.joints else 0.0
            mav.sendline(f"motortest {seq} 1 {args.pwm} {args.duration:g}")
            i = mav.expect([r"COMMAND_ACK: DO_MOTOR_TEST: (\w+)", r"Unknown command", pexpect.TIMEOUT], timeout=10)
            ack = mav.match.group(1) if i == 0 else ("UNKNOWN COMMAND" if i == 1 else "no ACK within 10 s")
            ok &= log.check(seq, f"motortest {seq}: MAV_CMD_DO_MOTOR_TEST ack", ack == "ACCEPTED", ack, "ACCEPTED",
                            "OBSERVED")
            deadline = time.monotonic() + args.duration + 2.0
            while time.monotonic() < deadline:                 # keep draining MAVProxy output (and logging it)
                mav.expect([pexpect.TIMEOUT, pexpect.EOF], timeout=0.5)
            with streams.lock:
                rows = np.array([[t, *v] for t, v in streams.joints if t >= t_start])
            win = rows[(rows[:, 0] >= t_start + 0.5) & (rows[:, 0] <= t_start + args.duration - 0.3)]
            if len(win) < 10:
                ok &= log.check(seq, f"motortest {seq}: joint samples", False, len(win), ">= 10", "OBSERVED")
                break
            mean = win[:, 1:].mean(axis=0)
            spinning = [i for i in range(4) if abs(mean[i]) > 0.1 * omega]
            ok &= log.check(seq, f"motortest {seq} ({desc}): only rotor_{rotor} spins", spinning == [rotor],
                            "rotors spinning: " + (", ".join(f"rotor_{i}" for i in spinning) or "none")
                            + "; means " + ", ".join(f"{m:+.1f}" for m in mean),
                            f"rotor_{rotor} only", "OBSERVED")
            ok &= log.check(seq, f"motortest {seq}: rotor_{rotor} sign and speed",
                            np.sign(mean[rotor]) == sign and abs(abs(mean[rotor]) - omega) <= 0.02 * omega,
                            f"{mean[rotor]:+.2f} rad/s (n={len(win)})", f"{sign * omega:+.1f} ±2 %", "OBSERVED")
            time.sleep(1.0)
    except (reg.StageFail, pexpect.ExceptionPexpect, OSError, RuntimeError) as error:
        log(f"  [FAIL] aborted: {error}")
        ok = False
    finally:
        if mav is not None:
            mav.terminate(force=True)
        if sitl is not None and sitl.poll() is None:
            os.killpg(sitl.pid, 15)
            sitl.wait(timeout=5)
        if streams is not None:
            streams.stop()
        if server is not None:
            server.stop()
        log(f"\nCleanup: gz sim processes left = {len(reg.gz_sim_processes())}; run files in {run.relative_to(ROOT)}")
    log(f"OVERALL: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
