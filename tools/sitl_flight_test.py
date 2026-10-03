#!/usr/bin/env python3
"""AirMouse SITL takeoff / hover / land test (ArduCopter 4.6.3 + Gazebo), PROVISIONAL params.

GUIDED -> arm -> takeoff <alt> -> hover <hover> s -> LAND -> auto-disarm, in a SITL world generated
by tools/make_sitl_world.py. Ground truth comes from Gazebo poses. Reports altitude-hold error,
attitude oscillation, horizontal drift, the learned MOT_THST_HOVER and CPU/RAM/RTF. If the flight is
unstable (tilt > 30 deg or |altitude error| > 1 m during the hover), it lands/disarms and reports
the logs. It never tunes gains.
"""

import argparse
import importlib.util
import math
import os
import re
import subprocess
import sys
import threading
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pexpect

ROOT = Path(__file__).resolve().parent.parent
AP = ROOT / "src" / "ardupilot"
VENV = ROOT / ".venv-ardupilot" / "bin"
PARMS = [AP / "Tools/autotest/default_params/copter.parm", ROOT / "simulation/sitl/airmouse_sitl.parm",
         ROOT / "simulation/sitl/airmouse_provisional_flight.parm"]
HOVER_ANALYTICAL = {"spin 0/1": (586.743 / 800) ** 2, "spin 0.15/0.95 (defaults)": ((586.743 / 800 - 0.15) / 0.80) ** 2}


def load(name):
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reg = load("airmouse_regression.py")


class Sampler(threading.Thread):
    """Once per second: CPU % and RSS (MB) per process group, plus Gazebo sim time vs wall time."""

    def __init__(self, streams, groups):
        super().__init__(daemon=True)
        self.streams, self.groups, self.rows, self.stop_flag = streams, groups, [], False

    def run(self):
        while not self.stop_flag:
            row = {"wall": time.monotonic()}
            p = self.streams.latest()
            row["sim"] = p[0] if p else float("nan")
            for name, pattern in self.groups.items():
                out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True).stdout.split()
                cpu = rss = 0.0
                for pid in out:
                    ps = subprocess.run(["ps", "-o", "%cpu=,rss=", "-p", pid], capture_output=True, text=True).stdout.split()
                    if len(ps) == 2:
                        cpu += float(ps[0])
                        rss += float(ps[1]) / 1024
                row[name] = (cpu, rss)
            self.rows.append(row)
            time.sleep(1.0)


def euler(q):
    x, y, z, w = q
    return (math.degrees(math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))),
            math.degrees(math.asin(max(-1, min(1, 2 * (w * y - z * x))))),
            math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("world", help="SITL world, e.g. simulation/sitl/empty_sitl.sdf")
    parser.add_argument("--alt", type=float, default=1.5)
    parser.add_argument("--hover", type=float, default=30.0, help="analysed hover window, s")
    parser.add_argument("--settle", type=float, default=5.0, help="settling time excluded before the window, s")
    parser.add_argument("--no-land", action="store_true")
    parser.add_argument("--logdir", default=str(ROOT / "logs" / f"phase3-{date.today().isoformat()}"))
    args = parser.parse_args()
    world = Path(args.world).resolve()
    os.environ["GZ_IP"] = "127.0.0.1"
    os.environ["PATH"] = f"{VENV}:/opt/homebrew/bin:" + os.environ["PATH"]
    os.environ["GZ_SIM_SYSTEM_PLUGIN_PATH"] = str(ROOT / "src" / "airmouse_sitl_bridge" / "build")
    log = reg.Log(Path(args.logdir))
    run = log.dir / f"flight_{world.stem}_{datetime.now():%H%M%S}"
    run.mkdir(parents=True, exist_ok=True)
    gz = reg.gz_bin()
    if reg.gz_sim_processes():
        raise SystemExit("a gz sim process is already running; stop it first")
    log(f"AirMouse SITL flight test {datetime.now().isoformat(timespec='seconds')}: {world.relative_to(ROOT)}, "
        f"takeoff {args.alt} m, hover {args.hover} s; params PROVISIONAL (not flight-approved)")
    server = streams = sitl = mav = sampler = None
    ok, unstable, marks, learned = True, None, {}, None

    def drain(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            mav.expect([pexpect.TIMEOUT, pexpect.EOF], timeout=0.3)

    try:
        server = reg.Server(gz, world, run / "gz_server.log")
        time.sleep(6)
        streams = reg.Streams(gz, joints=True)
        sitl = subprocess.Popen(
            [str(AP / "build/sitl/bin/arducopter"), "--model", "JSON", "--speedup", "1", "-w",
             "--defaults", ",".join(str(p) for p in PARMS), "-I0", "--home", "-35.363261,149.165230,584,0"],
            cwd=run, stdout=open(run / "arducopter.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(3)
        mav = pexpect.spawn(f"{VENV / 'mavproxy.py'} --master tcp:127.0.0.1:5760 --state-basedir {run}",
                            encoding="utf-8", timeout=60, cwd=str(run))
        mav.logfile_read = open(run / "mavproxy.log", "w")
        mav.expect(["Detected vehicle", "online system"], timeout=90)
        sampler = Sampler(streams, {"gz_sim": "gz sim", "arducopter": "build/sitl/bin/arducopter",
                                    "mavproxy": "mavproxy.py"})
        sampler.start()
        # Wait until the EKF uses GPS, then GUIDED + arm (retry while pre-arm checks are not yet satisfied).
        mav.expect(r"EKF3 IMU0 is using GPS", timeout=180)
        log("  EKF3 using GPS")
        rest = streams.latest()
        z_home = rest[3]
        armed = False
        for attempt in range(12):
            mav.sendline("mode guided")
            drain(1.0)
            mav.sendline("arm throttle")
            i = mav.expect([r"ARMED", r"(PreArm|Arm): [^\r\n]*", pexpect.TIMEOUT], timeout=8)
            if i == 0:
                armed = True
                break
            log(f"  arm attempt {attempt + 1}: {mav.match.group(0) if i == 1 else 'no response'}")
            drain(5.0)
        ok &= log.check("flight", "GUIDED + arm", armed, "ARMED" if armed else "not armed", "ARMED", "OBSERVED")
        if not armed:
            raise reg.StageFail("could not arm")
        marks["armed"] = streams.latest()[0]
        mav.sendline(f"takeoff {args.alt}")
        target = z_home + args.alt
        t_wall = time.monotonic()
        reached = None
        while time.monotonic() - t_wall < 40:
            drain(0.2)
            if sitl.poll() is not None:
                break
            p = streams.latest()
            if p[3] >= target - 0.1:
                reached = p
                break
        ok &= log.check("flight", f"takeoff to {args.alt} m (truth z >= target - 0.1 m)", reached is not None,
                        f"reached z {reached[3]:.3f} m at t={reached[0]:.2f}" if reached else f"z {p[3]:.3f} m after 40 s",
                        f"z_home {z_home:.3f} + {args.alt} = {target:.3f} m", "OBSERVED")
        if not reached:
            raise reg.StageFail("takeoff did not reach the target altitude")
        marks["reached"] = reached[0]
        # Hover: settle + analysed window, watching for instability.
        t_end = reached[0] + args.settle + args.hover
        wall_end = time.monotonic() + 3 * (args.settle + args.hover) + 30   # lock-step: sim time stops if SITL dies
        while True:
            drain(0.3)
            if sitl.poll() is not None:
                unstable = f"ArduCopter SITL process exited (code {sitl.returncode}); see arducopter.log / crash report"
                break
            if time.monotonic() > wall_end:
                unstable = "hover window did not complete within the wall-clock limit"
                break
            p = streams.latest()
            r, pi, _ = euler(p[4:8])
            if p[0] >= reached[0] + 1.0 and (max(abs(r), abs(pi)) > 30 or abs(p[3] - target) > 1.0):
                unstable = f"t={p[0]:.2f}: roll {r:+.1f} deg, pitch {pi:+.1f} deg, z {p[3]:.3f} m (target {target:.3f})"
                break
            if p[0] >= t_end:
                break
        marks["hover_end"] = streams.latest()[0]
        ok &= log.check("flight", "stable hover (|tilt| <= 30 deg, |z err| <= 1 m)", unstable is None,
                        unstable or "stable", "stable", "OBSERVED")
        if not args.no_land:
            mav.sendline("mode land")
            i = mav.expect([r"DISARMED", pexpect.TIMEOUT], timeout=60)
            marks["disarmed"] = streams.latest()[0]
            ok &= log.check("flight", "LAND -> auto-disarm", i == 0, "DISARMED" if i == 0 else "not disarmed in 60 s",
                            "DISARMED", "OBSERVED")
            drain(3.0)
        mav.sendline("param fetch MOT_THST_HOVER")
        drain(3.0)
        mav.sendline("param show MOT_THST_HOVER")
        mav.expect(r"MOT_THST_HOVER\s+(-?[\d.]+)", timeout=20)
        learned = float(mav.match.group(1))
    except (reg.StageFail, pexpect.ExceptionPexpect, OSError, RuntimeError) as error:
        log(f"  [FAIL] aborted: {error}")
        ok = False
    finally:
        if sampler:
            sampler.stop_flag = True
        if mav is not None:
            if unstable:
                mav.sendline("disarm force")
                time.sleep(1)
            mav.terminate(force=True)
        if sitl is not None and sitl.poll() is None:
            os.killpg(sitl.pid, 15)
            sitl.wait(timeout=5)
        if streams is not None:
            streams.stop()
        if server is not None:
            server.stop()

    # ------------------------------------------------------------------ analysis (Gazebo ground truth)
    if streams is not None:
        with streams.lock:
            poses = np.array(streams.poses)
        if len(poses):
            np.savetxt(run / "truth_pose_all.csv", poses, delimiter=",", fmt="%.6f",
                       header="sim_t,x,y,z,qx,qy,qz,qw", comments="")
    if streams is not None and "reached" in marks and "hover_end" in marks:
        np.savetxt(run / "truth_pose.csv", poses, delimiter=",", fmt="%.6f", header="sim_t,x,y,z,qx,qy,qz,qw",
                   comments="")
        w0 = marks["reached"] + args.settle
        w = poses[(poses[:, 0] >= w0) & (poses[:, 0] <= marks["hover_end"])]
        if len(w) > 20:
            err = w[:, 3] - target
            ang = np.array([euler(q) for q in w[:, 4:8]])
            rp = ang[:, :2]
            dt = np.median(np.diff(w[:, 0]))
            spec = np.abs(np.fft.rfft(rp[:, 0] - rp[:, 0].mean()))
            freqs = np.fft.rfftfreq(len(rp), dt)
            f_dom = freqs[1:][np.argmax(spec[1:])] if len(spec) > 1 else float("nan")
            xy0 = w[0, 1:3]
            drift = np.hypot(w[:, 1] - xy0[0], w[:, 2] - xy0[1])
            climb = poses[(poses[:, 0] >= marks["reached"]) & (poses[:, 0] <= w0)]
            log.info("hover", f"window {w[0, 0] - marks['reached']:.1f}-{w[-1, 0] - marks['reached']:.1f} s after reaching "
                     f"target (n={len(w)}, pose dt {dt * 1e3:.0f} ms)", "", "OBSERVED")
            log.info("hover", "altitude hold error (truth z - target)",
                     f"mean {err.mean() * 100:+.1f} cm, std {err.std() * 100:.1f} cm, max |err| {np.abs(err).max() * 100:.1f} cm; "
                     f"overshoot after reaching {(climb[:, 3].max() - target) * 100:+.1f} cm", "OBSERVED")
            log.info("hover", "attitude (truth)",
                     f"roll std {rp[:, 0].std():.2f} deg (peak {np.abs(rp[:, 0]).max():.2f}), pitch std {rp[:, 1].std():.2f} "
                     f"deg (peak {np.abs(rp[:, 1]).max():.2f}); roll p-p {np.ptp(rp[:, 0]):.2f} deg; dominant roll freq "
                     f"{f_dom:.2f} Hz; yaw drift {np.ptp(ang[:, 2]):.2f} deg", "OBSERVED")
            log.info("hover", "horizontal position hold (truth)", f"max drift {drift.max() * 100:.1f} cm from window start",
                     "OBSERVED")
    if learned is not None:
        log.info("hover", "learned MOT_THST_HOVER (after disarm, MOT_HOVER_LEARN 2)",
                 f"{learned:.4f} vs analytical " + ", ".join(f"{v:.4f} ({k})" for k, v in HOVER_ANALYTICAL.items())
                 + "; initial 0.54", "OBSERVED vs ANALYTICAL")
    if sampler and sampler.rows:
        rows = [r for r in sampler.rows if "reached" in marks and not math.isnan(r["sim"])]
        if len(rows) > 2:
            rtf = (rows[-1]["sim"] - rows[0]["sim"]) / (rows[-1]["wall"] - rows[0]["wall"])
            res = "; ".join(f"{k} CPU {np.mean([r[k][0] for r in rows]):.0f} % / RSS {np.max([r[k][1] for r in rows]):.0f} MB"
                            for k in ("gz_sim", "arducopter", "mavproxy"))
            log.info("resources", "mean CPU (100 % = one core) / peak RSS", res, "OBSERVED")
            log.info("resources", "real-time factor (Gazebo sim time / wall time)", f"{rtf:.3f} over {rows[-1]['wall'] - rows[0]['wall']:.0f} s",
                     "OBSERVED")
    log(f"\nCleanup: gz sim processes left = {len(reg.gz_sim_processes())}; run files in {run.relative_to(ROOT)}")
    log(f"OVERALL: {'PASS' if ok else 'FAIL'}" + (f" (UNSTABLE: {unstable})" if unstable else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
