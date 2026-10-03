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
import signal
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
    parser.add_argument("--mode", choices=["guided", "loiter"], default="guided",
                        help="hover mode after the GUIDED takeoff; loiter centres RC 1-4 at 1500 (enables hover learning)")
    parser.add_argument("--parm", action="append", default=[],
                        help="extra parameter file(s) loaded after the standard set (e.g. GPS-denied config)")
    parser.add_argument("--ready-msg", default=r"EKF3 IMU0 is using GPS",
                        help="regex of the ArduPilot message that means the EKF is ready to arm")
    parser.add_argument("--stub", action="store_true",
                        help="start tools/externalnav_stub_GROUND_TRUTH_PLUMBING_ONLY.py (GROUND-TRUTH-DERIVED, "
                             "PLUMBING TEST ONLY) after MAVProxy connects")
    parser.add_argument("--nav-loss-at", type=float, default=None,
                        help="seconds after the analysed hover window starts: stop the ExternalNav stub (SIGUSR1)")
    parser.add_argument("--ground-only", action="store_true",
                        help="no arming: after the EKF is ready, record --hover seconds on the ground (plumbing check)")
    parser.add_argument("--nav-loss-dur", type=float, default=0.0,
                        help="seconds of ExternalNav loss (0 = until the end of the test)")
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
    server = streams = sitl = mav = sampler = stub = None
    loss = {}
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
             "--defaults", ",".join(str(p) for p in PARMS + [Path(x).resolve() for x in args.parm]), "-I0", "--home", "-35.363261,149.165230,584,0"],
            cwd=run, stdout=open(run / "arducopter.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(3)
        mav = pexpect.spawn(f"{VENV / 'mavproxy.py'} --master tcp:127.0.0.1:5760 --state-basedir {run}",
                            encoding="utf-8", timeout=60, cwd=str(run))
        mav.logfile_read = open(run / "mavproxy.log", "w")
        mav.expect(["Detected vehicle", "online system"], timeout=90)
        if args.stub:
            stub = subprocess.Popen([sys.executable, str(ROOT / "tools/externalnav_stub_GROUND_TRUTH_PLUMBING_ONLY.py"),
                                     "--log", str(run / "externalnav_stub_GROUND_TRUTH_PLUMBING_ONLY.csv")],
                                    stdout=open(run / "externalnav_stub.log", "w"), stderr=subprocess.STDOUT)
            log("  *** ExternalNav stub started: GROUND-TRUTH-DERIVED, PLUMBING TEST ONLY ***")
        sampler = Sampler(streams, {"gz_sim": "gz sim", "arducopter": "build/sitl/bin/arducopter",
                                    "mavproxy": "mavproxy.py"})
        sampler.start()
        # Wait until the EKF uses GPS, then GUIDED + arm (retry while pre-arm checks are not yet satisfied).
        mav.expect(args.ready_msg, timeout=180)
        log(f"  EKF ready: '{mav.match.group(0)}'")
        rest = streams.latest()
        z_home = rest[3]
        if args.ground_only:
            drain(args.hover)
            marks["ground_only"] = (rest[0], streams.latest()[0])
            raise reg.StageFail("ground-only plumbing check complete (no flight, by request)")
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
        if args.mode == "loiter":
            for ch in (1, 2, 3, 4):
                mav.sendline(f"rc {ch} 1500")
            drain(0.5)
            mav.sendline("mode loiter")
            i = mav.expect([r"LOITER>", pexpect.TIMEOUT], timeout=10)
            ok &= log.check("flight", "switch to LOITER (RC 1-4 = 1500)", i == 0, "LOITER" if i == 0 else "no mode change",
                            "LOITER", "OBSERVED")
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
            if stub is not None and args.nav_loss_at is not None:
                t_loss = reached[0] + args.settle + args.nav_loss_at
                if "start" not in loss and p[0] >= t_loss:
                    os.kill(stub.pid, signal.SIGUSR1)
                    loss.update(start=p[0], start_wall=time.time(), pose=p)
                    log(f"  ExternalNav LOSS started at sim t={p[0]:.2f}")
                if ("start" in loss and "end" not in loss and args.nav_loss_dur > 0
                        and p[0] >= loss["start"] + args.nav_loss_dur):
                    os.kill(stub.pid, signal.SIGUSR1)
                    loss.update(end=p[0], end_wall=time.time())
                    log(f"  ExternalNav LOSS ended at sim t={p[0]:.2f}")
            r, pi, _ = euler(p[4:8])
            if "start" in loss and p[3] < z_home + 0.05 and p[0] > loss["start"] + 2:
                loss["landed"] = p[0]
                log(f"  vehicle on the ground at sim t={p[0]:.2f} (during/after ExternalNav loss)")
                break
            alt_bad = abs(p[3] - target) > 1.0 and "start" not in loss   # failsafe descent is behaviour, not instability
            if p[0] >= reached[0] + 1.0 and (max(abs(r), abs(pi)) > 30 or alt_bad):
                unstable = f"t={p[0]:.2f}: roll {r:+.1f} deg, pitch {pi:+.1f} deg, z {p[3]:.3f} m (target {target:.3f})"
                break
            if p[0] >= t_end:
                break
        marks["hover_end"] = streams.latest()[0]
        ok &= log.check("flight", "stable hover (|tilt| <= 30 deg, |z err| <= 1 m)", unstable is None,
                        unstable or "stable", "stable", "OBSERVED")
        if not args.no_land and "landed" not in loss:
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
        if "ground_only" in marks:
            log(f"  {error}")
        else:
            log(f"  [FAIL] aborted: {error}")
            ok = False
    finally:
        if sampler:
            sampler.stop_flag = True
        if stub is not None and stub.poll() is None:
            stub.terminate()
            try:
                stub.wait(timeout=5)
            except subprocess.TimeoutExpired:
                stub.kill()
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
    bins = sorted((run / "logs").glob("*.BIN"))
    if bins:
        from pymavlink import mavutil
        df = mavutil.mavlink_connection(str(bins[-1]))
        ct = []
        while True:
            m = df.recv_match(type="CTUN", blocking=False)
            if m is None:
                break
            ct.append((m.TimeUS / 1e6, m.ThO, m.ThH, m.Alt))
        ct = np.array(ct)
        df.rewind()
        rf = []
        while True:
            m = df.recv_match(type="RFND", blocking=False)
            if m is None:
                break
            rf.append((m.TimeUS / 1e6, m.Dist, m.Stat))
        if rf and len(ct):
            rf = np.array(rf)
            ct_alt = ct[ct[:, 3] > 0.8 * args.alt]
            if len(ct_alt):
                hv = rf[(rf[:, 0] >= ct_alt[0, 0] + args.settle) & (rf[:, 0] <= ct_alt[-1, 0])]
                pre = rf[rf[:, 0] < ct_alt[0, 0] - 3]
                log.info("hover", "ArduPilot rangefinder (dataflash RFND; status 3 = OutOfRangeHigh, 4 = Good)",
                         f"hover Dist mean {hv[:, 1].mean():.3f} m (std {hv[:, 1].std() * 100:.1f} cm, status "
                         f"{sorted(set(hv[:, 2].astype(int).tolist()))}); before takeoff status "
                         f"{sorted(set(pre[:, 2].astype(int).tolist())) if len(pre) else 'n/a'}", "OBSERVED")
        air = ct[ct[:, 3] > 0.8 * args.alt] if len(ct) else ct
        if len(air):
            log.info("hover", "dataflash CTUN hover throttle", f"ThH {air[0, 2]:.4f} -> {air[-1, 2]:.4f} over "
                     f"{air[-1, 0] - air[0, 0]:.0f} s airborne; ThO mean (last 20 s airborne) "
                     f"{air[air[:, 0] >= air[-1, 0] - 20][:, 1].mean():.4f}", "OBSERVED")
    if "ground_only" in marks or args.stub:
        bins = sorted((run / "logs").glob("*.BIN"))
        if bins:
            from pymavlink import mavutil
            df = mavutil.mavlink_connection(str(bins[-1]))
            visp, xkf, msgs = [], [], []
            while True:
                m = df.recv_match(type=["VISP", "XKF1", "MSG"], blocking=False)
                if m is None:
                    break
                d = m.to_dict()
                if m.get_type() == "VISP":
                    visp.append((d["TimeUS"] / 1e6, d["PX"], d["PY"], d["PZ"], d.get("Y", float("nan")),
                                 d.get("Ign", 0), d.get("Q", -1)))
                elif m.get_type() == "XKF1" and d.get("C", 0) == 0:
                    xkf.append((d["TimeUS"] / 1e6, d["PN"], d["PE"], d["PD"], d.get("Yaw", float("nan"))))
                elif m.get_type() == "MSG":
                    msgs.append(str(d.get("Message", "")))
            visp, xkf = np.array(visp), np.array(xkf)
            ok &= log.check("plumbing", "VISP (ExternalNav pose) records received and consumed",
                            len(visp) > 0 and visp[:, 5].sum() == 0,
                            f"{len(visp)} records over {visp[-1, 0] - visp[0, 0]:.1f} s, ignored {int(visp[:, 5].sum())}, "
                            f"quality {sorted(set(visp[:, 6].astype(int).tolist()))}" if len(visp) else "none",
                            "> 0, none ignored", "OBSERVED")
            log.info("plumbing", "EKF-related messages", " | ".join(x for x in msgs if "EKF" in x or "ext" in x.lower())[:400],
                     "OBSERVED")
            if len(xkf) and len(visp):
                tail = xkf[xkf[:, 0] >= xkf[-1, 0] - 5]
                vt = visp[visp[:, 0] >= visp[-1, 0] - 5]
                log.info("plumbing", "EKF position vs ExternalNav input (last 5 s, vehicle at rest)",
                         f"EKF PN/PE/PD {tail[:, 1].mean():+.3f}/{tail[:, 2].mean():+.3f}/{tail[:, 3].mean():+.3f} m, yaw "
                         f"{tail[:, 4].mean():.2f} deg; VISP PX/PY/PZ {vt[:, 1].mean():+.3f}/{vt[:, 2].mean():+.3f}/"
                         f"{vt[:, 3].mean():+.3f} m, yaw {vt[:, 4].mean():.2f} deg", "OBSERVED")
    if loss and (run / "mav.tlog").exists():
        from pymavlink import mavutil
        tl = mavutil.mavlink_connection(str(run / "mav.tlog"))
        events, last_mode = [], None
        while True:
            m = tl.recv_match(type=["STATUSTEXT", "HEARTBEAT"], blocking=False)
            if m is None:
                break
            dt_rel = m._timestamp - loss["start_wall"]
            if dt_rel < -2:
                continue
            if m.get_type() == "STATUSTEXT":
                events.append(f"{dt_rel:+.1f}s {m.text}")
            elif m.get_srcComponent() == 1 and m.type == mavutil.mavlink.MAV_TYPE_QUADROTOR:
                mode = mavutil.mode_string_v10(m)
                if mode != last_mode:
                    events.append(f"{dt_rel:+.1f}s MODE {mode}")
                    last_mode = mode
        log.info("navloss", "ArduPilot messages / mode changes relative to ExternalNav loss start",
                 " | ".join(events[:25]) or "none", "OBSERVED")
        with streams.lock:
            pl = np.array(streams.poses)
        seg = pl[pl[:, 0] >= loss["start"]]
        if len(seg):
            p0 = loss["pose"]
            d = np.hypot(seg[:, 1] - p0[1], seg[:, 2] - p0[2])
            log.info("navloss", "truth during/after loss", f"max horizontal excursion {d.max() * 100:.1f} cm; z from "
                     f"{p0[3]:.3f} to {seg[-1, 3]:.3f} m; landed at {loss.get('landed', float('nan')) - loss['start']:+.1f} s "
                     f"after loss start" if "landed" in loss else f"max horizontal excursion {d.max() * 100:.1f} cm; "
                     f"z {p0[3]:.3f} -> {seg[-1, 3]:.3f} m; not landed during the window", "OBSERVED")
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
