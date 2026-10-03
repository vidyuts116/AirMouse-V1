#!/usr/bin/env python3
"""AirMouse SITL IMU-frame ground checks (no arming, no flight).

Case "level"  : simulation/sitl/empty_sitl.sdf, vehicle at rest on the ground.
Case "noseup" : simulation/sitl/empty_sitl_hold_pitch10.sdf, vehicle held fixed 10 deg nose-up (diagnostic).

For each case: ArduPilot's IMU (MAVLink RAW_IMU, milli-g, and the dataflash IMU log, m/s^2) and attitude
(ATTITUDE) must follow ArduPilot's FRD convention (at rest AccZ = -g; nose-up = positive pitch with
AccX = +g*sin(pitch)); the ROS-facing FLU IMU on /airmouse/imu must still read az = +g*cos(pitch).
"""

import argparse
import importlib.util
import math
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
from pymavlink import mavutil

ROOT = Path(__file__).resolve().parent.parent
AP = ROOT / "src" / "ardupilot"
VENV = ROOT / ".venv-ardupilot" / "bin"
PARMS = [AP / "Tools/autotest/default_params/copter.parm", ROOT / "simulation/sitl/airmouse_sitl.parm",
         ROOT / "simulation/sitl/airmouse_provisional_flight.parm"]
G = 9.80665       # ArduPilot GRAVITY_MSS (RAW_IMU milli-g scaling); Gazebo world gravity is 9.81
CASES = {"level": (ROOT / "simulation/sitl/empty_sitl.sdf", 0.0),
         "noseup": (ROOT / "simulation/sitl/empty_sitl_hold_pitch10.sdf", 10.0)}


def load(name):
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reg = load("airmouse_regression.py")


def run_case(log, gz, name, world, pitch_deg, seconds, run_root):
    run = run_root / f"ground_{name}"
    run.mkdir(parents=True, exist_ok=True)
    th = math.radians(pitch_deg)
    g_w = 9.81
    exp = {"ap_acc": (g_w * math.sin(th), 0.0, -g_w * math.cos(th)), "ap_pitch": pitch_deg,
           "flu_acc": (g_w * math.sin(th), 0.0, g_w * math.cos(th))}
    server = probe = sitl = None
    raw, att = [], []
    try:
        server = reg.Server(gz, world, run / "gz_server.log")
        time.sleep(6)
        probe = reg.Probe(ROOT / "src/airmouse_sitl_bridge/build/airmouse_sensor_probe", ["imu:/airmouse/imu"],
                          run / "probe_airmouse_imu.txt")
        sitl = subprocess.Popen(
            [str(AP / "build/sitl/bin/arducopter"), "--model", "JSON", "--speedup", "1", "-w",
             "--defaults", ",".join(str(p) for p in PARMS), "-I0", "--home", "-35.363261,149.165230,584,0"],
            cwd=run, stdout=open(run / "arducopter.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(3)
        mav = mavutil.mavlink_connection("tcp:127.0.0.1:5760", source_system=250)
        mav.wait_heartbeat(timeout=60)
        mav.mav.request_data_stream_send(mav.target_system, mav.target_component,
                                         mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            m = mav.recv_match(type=["RAW_IMU", "ATTITUDE"], blocking=True, timeout=1)
            if m is None:
                continue
            if m.get_type() == "RAW_IMU":
                raw.append((time.monotonic(), m.xacc, m.yacc, m.zacc, m.xgyro, m.ygyro, m.zgyro))
            else:
                att.append((time.monotonic(), math.degrees(m.roll), math.degrees(m.pitch)))
        mav.close()
        with probe.lock:
            flu = np.array(probe.imu.get("/airmouse/imu", []))
    finally:
        if probe:
            probe.stop()
        if sitl is not None and sitl.poll() is None:
            os.killpg(sitl.pid, 15)
            sitl.wait(timeout=5)
        if server:
            server.stop()
    ok = True
    tag = f"{name} ({pitch_deg:g} deg nose-up)"
    last = lambda rows, k: np.array([r for r in rows if r[0] >= rows[-1][0] - k])
    r = last(raw, 5.0)
    acc = r[:, 1:4].mean(axis=0) * G / 1000.0          # milli-g -> m/s^2
    gyro = r[:, 4:7].mean(axis=0) / 1000.0             # mrad/s -> rad/s
    for i, ax in enumerate("XYZ"):
        ok &= log.check(tag, f"ArduPilot RAW_IMU Acc{ax} (FRD)", abs(acc[i] - exp["ap_acc"][i]) <= 0.15,
                        f"{acc[i]:+.3f} m/s^2 (n={len(r)})", f"{exp['ap_acc'][i]:+.3f} ±0.15 (ANALYTICAL)", "OBSERVED")
    ok &= log.check(tag, "ArduPilot RAW_IMU gyro ~ 0", np.abs(gyro).max() <= 0.01,
                    f"({gyro[0]:+.4f}, {gyro[1]:+.4f}, {gyro[2]:+.4f}) rad/s", "|w| <= 0.01 rad/s", "OBSERVED")
    a = last(att, 5.0)
    ok &= log.check(tag, "ArduPilot ATTITUDE pitch (nose-up positive)", abs(a[:, 2].mean() - exp["ap_pitch"]) <= 1.0,
                    f"{a[:, 2].mean():+.2f} deg (roll {a[:, 1].mean():+.2f})", f"{exp['ap_pitch']:+.1f} ±1.0 deg", "OBSERVED")
    # Dataflash IMU (m/s^2), last 5 s of the log
    bins = sorted((run / "logs").glob("*.BIN"))
    if bins:
        df = mavutil.mavlink_connection(str(bins[-1]))
        rows = []
        while True:
            m = df.recv_match(type="IMU", blocking=False)
            if m is None:
                break
            if m.I == 0:
                rows.append((m.TimeUS / 1e6, m.AccX, m.AccY, m.AccZ))
        rows = np.array(rows)
        rows = rows[rows[:, 0] >= rows[-1, 0] - 5]
        ok &= log.check(tag, "ArduPilot dataflash IMU AccZ", abs(rows[:, 3].mean() - exp["ap_acc"][2]) <= 0.15,
                        f"{rows[:, 3].mean():+.3f} m/s^2 (AccX {rows[:, 1].mean():+.3f}; n={len(rows)})",
                        f"{exp['ap_acc'][2]:+.3f} ±0.15", "OBSERVED")
    f = flu[flu[:, 0] >= flu[-1, 0] - 5]
    ok &= log.check(tag, "/airmouse/imu (FLU, ROS contract) accel x / z",
                    abs(f[:, 1].mean() - exp["flu_acc"][0]) <= 0.15 and abs(f[:, 3].mean() - exp["flu_acc"][2]) <= 0.15,
                    f"ax {f[:, 1].mean():+.3f}, az {f[:, 3].mean():+.3f} m/s^2 (n={len(f)})",
                    f"ax {exp['flu_acc'][0]:+.3f}, az {exp['flu_acc'][2]:+.3f} ±0.15", "OBSERVED")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--logdir", default=str(ROOT / "logs" / f"phase3-{date.today().isoformat()}"))
    args = parser.parse_args()
    os.environ["GZ_IP"] = "127.0.0.1"
    os.environ["PATH"] = f"{VENV}:/opt/homebrew/bin:" + os.environ["PATH"]
    os.environ["GZ_SIM_SYSTEM_PLUGIN_PATH"] = str(ROOT / "src" / "airmouse_sitl_bridge" / "build")
    log = reg.Log(Path(args.logdir))
    run_root = log.dir / f"groundcheck_{datetime.now():%H%M%S}"
    gz = reg.gz_bin()
    if reg.gz_sim_processes():
        raise SystemExit("a gz sim process is already running; stop it first")
    probe_bin = ROOT / "src/airmouse_sitl_bridge/build/airmouse_sensor_probe"
    reg.diag.compile_publisher(ROOT / "tools/airmouse_sensor_probe.cc", probe_bin)
    log(f"AirMouse SITL IMU-frame ground checks {datetime.now().isoformat(timespec='seconds')}")
    ok = True
    for name, (world, pitch) in CASES.items():
        log.stage(0, f"Ground check: {name}")
        ok &= run_case(log, gz, name, world, pitch, args.seconds, run_root)
        if not ok:
            break
    log(f"\nCleanup: gz sim processes left = {len(reg.gz_sim_processes())}; run files in {run_root.relative_to(ROOT)}")
    log(f"OVERALL: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
