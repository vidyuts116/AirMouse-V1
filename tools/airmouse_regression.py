#!/usr/bin/env python3
"""AirMouse step-by-step regression (Stages 0-10).

Runs the stages in order, prints PASS/FAIL with measured vs expected values and
an OBSERVED/ANALYTICAL/INFERRED label, and stops at the first FAIL. Never edits
any SDF. Every Gazebo server it starts is stopped before it exits.

Timing-critical sequences (spin-up dwell, reset, differential command) run with
the world paused and advanced by WorldControl multi_step, so the simulated
durations are exact and runs are repeatable. Stage 3 deliberately measures the
live (unpaused) command latency instead.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
BASELINE = ROOT / "simulation" / "airmouse_quadrotor.sdf"
DIAG_DIR = ROOT / "simulation" / "diagnostics"
JOINTFIX = DIAG_DIR / "airmouse_force_diagnostic_jointfix.sdf"
BASELINE_SHA = "f1c1d0f7dfdce2407b314244d38c46becb12da1a095e1ec4fbbc7688da6ff46c"  # IMU + LiDAR + RGB + rangefinder
GZ_VERSION = "8.15.0"
REQUIRED_TOOLS = ["airmouse_hover_helper.cc", "airmouse_sensor_probe.cc", "airmouse_hover_acceptance.py",
                  "airmouse_differential_thrust.py", "measure_airmouse_diagnostic.py"]

WORLD = "airmouse_physics"
POSE_TOPIC = f"/world/{WORLD}/pose/info"
CONTROL = f"/world/{WORLD}/control"
SET_POSE = f"/world/{WORLD}/set_pose"
JOINT_TOPIC = "/airmouse/diagnostic/joint_state"
FORCE_TOPICS = {i: f"/airmouse/diagnostic/force/rotor_{i}" for i in range(4)}
JOINTS = [f"rotor_{i}_joint" for i in range(4)]

ARM = 0.282843
K = 8.54858e-06
MASS = 1.2
G = 9.81
TAU_UP = 0.0125
HOVER_CMD = 586.8
SIGNS = [1, -1, 1, -1]
SENSOR_TYPES_OF_INTEREST = {"imu", "lidar", "gpu_lidar", "ray", "gpu_ray", "camera",
                            "depth_camera", "depth", "rgbd_camera"}


def load(name):
    path = TOOLS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


diag = load("measure_airmouse_diagnostic.py")
dt = load("airmouse_differential_thrust.py")   # predicted(), euler(), PATTERNS, I_RIGID


class StageFail(Exception):
    pass


# --------------------------------------------------------------------------- logging
class Log:
    def __init__(self, directory):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = (directory / f"run_{datetime.now():%H%M%S}.log").open("w")
        self.results = []
        self.current = 0

    def stage(self, n, title):
        self.current = n
        self(f"\nStage {n}  {title}")

    def __call__(self, text=""):
        print(text, flush=True)
        self.file.write(text + "\n")
        self.file.flush()

    def check(self, stage, item, ok, measured, expected, label):
        status = "PASS" if ok else "FAIL"
        self.results.append({"stage": stage, "item": item, "status": status,
                             "measured": measured, "expected": expected, "label": label})
        self(f"  [{status}] {item}: measured {measured} | expected {expected} ({label})")
        return ok

    def info(self, stage, item, measured, label, expected="(informational)", status="INFO"):
        self.results.append({"stage": stage, "item": item, "status": status,
                             "measured": measured, "expected": expected, "label": label})
        self(f"  [{status}] {item}: {measured} ({label})")


# --------------------------------------------------------------------------- gz plumbing
def gz_bin():
    gz = shutil.which("gz")
    if not gz:
        raise StageFail("gz not on PATH (use PATH=/opt/homebrew/bin:$PATH)")
    return gz


def gz_sim_processes():
    out = subprocess.run(["pgrep", "-fl", "gz sim"], text=True, capture_output=True).stdout
    return [line for line in out.splitlines() if line.strip()]


class Server:
    def __init__(self, gz, sdf, log_path):
        self.log_file = open(log_path, "w")
        self.proc = subprocess.Popen([gz, "sim", "-s", "-r", str(sdf)], stdout=self.log_file,
                                     stderr=subprocess.STDOUT, start_new_session=True)

    def stop(self):
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self.log_file.close()


def stamp(message):
    s = message.get("header", {}).get("stamp")
    return None if s is None else float(s.get("sec", 0)) + float(s.get("nsec", 0)) * 1e-9


def vec(d):
    return [float(d.get(k, 0.0)) for k in ("x", "y", "z")]


class Streams:
    """Pose (always), joint-state and wrench (optional) streams from `gz topic -e`."""

    def __init__(self, gz, joints=False, forces=False):
        self.lock = threading.Lock()
        self.poses, self.joints = [], []
        self.wrench = {i: [] for i in range(4)}
        self.procs = []
        topics = [("pose", POSE_TOPIC)]
        if joints:
            topics.append(("joint", JOINT_TOPIC))
        if forces:
            topics += list(FORCE_TOPICS.items())
        for label, topic in topics:
            proc = subprocess.Popen([gz, "topic", "-e", "-t", topic, "--json-output"],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            self.procs.append(proc)
            threading.Thread(target=self._pump, args=(label, proc), daemon=True).start()

    def _pump(self, label, proc):
        for message in diag.message_stream(proc):
            if message is None:
                continue
            t = stamp(message)
            if t is None:
                continue
            if label == "pose":
                body = diag.parse_pose_message(message)
                if body:
                    with self.lock:
                        self.poses.append((t, body["x"], body["y"], body["z"],
                                           body["qx"], body["qy"], body["qz"], body["qw"]))
            elif label == "joint":
                v = {j.get("name"): float(j.get("axis1", {}).get("velocity", 0.0))
                     for j in message.get("joint", [])}
                if all(n in v for n in JOINTS):
                    with self.lock:
                        self.joints.append((t, [v[n] for n in JOINTS]))
            else:
                row = (t, *vec(message.get("force", {})), *vec(message.get("torque", {})))
                with self.lock:
                    self.wrench[label].append(row)

    def latest(self):
        with self.lock:
            return self.poses[-1] if self.poses else None

    def stop(self):
        for proc in self.procs:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


class Session:
    """A running server + persistent motor helper + recording streams."""

    def __init__(self, gz, binary, sdf, log, tag, joints=False, forces=False):
        self.gz, self.log, self.tag = gz, log, tag
        self.helper = self.streams = None
        self.events = []
        self.server = Server(gz, sdf, log.dir / f"server_{tag}.log")
        try:
            self.boot_audit = self._wait_boot()
            self.helper = subprocess.Popen([str(binary), "100"], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, text=True, bufsize=1)
            self.lines = queue.Queue()
            threading.Thread(target=lambda: [self.lines.put(l.strip()) for l in self.helper.stdout],
                             daemon=True).start()
            self.expect("READY", 10)
            self.gate = self._gate()
            self.streams = Streams(gz, joints, forces)
            self.wait_pose(lambda p: True, 15, "first pose")
        except Exception:
            self.close()
            raise

    def _wait_boot(self):
        deadline = time.monotonic() + 40
        last = None
        while time.monotonic() < deadline:
            info, err = diag.audit_topic(self.gz)
            last = info or err
            if info and info["subscribers"] == 4:
                return info
            time.sleep(0.5)
        raise StageFail(f"server did not expose 4 motor subscribers within 40 s: {last}")

    def _gate(self):
        t0 = time.monotonic()
        while time.monotonic() - t0 < 30:
            info, _ = diag.audit_topic(self.gz)
            self.send("status")
            connected = self.expect("STATUS").endswith("connected=1")
            if info and info["publishers"] == 1 and info["subscribers"] == 4 and connected:
                return {"wall_s": time.monotonic() - t0, "publishers": 1, "subscribers": 4, "connected": 1}
            time.sleep(0.2)
        raise StageFail("helper connection gate did not pass within 30 s")

    # helper I/O
    def send(self, cmd):
        self.helper.stdin.write(cmd + "\n")
        self.helper.stdin.flush()

    def expect(self, prefix, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self.lines.get(timeout=0.1)
            except queue.Empty:
                continue
            self.events.append(line)
            if line.startswith(prefix):
                return line
        raise StageFail(f"helper did not report {prefix} within {timeout} s")

    def command(self, speeds):
        if np.isscalar(speeds):
            self.send(f"speed {speeds:.9g}")
        else:
            self.send("speeds " + " ".join(f"{v:.9g}" for v in speeds))
        return self.expect("CMD")

    # world control
    def _call(self, what, fn, already_done=None):
        """Service call with up to 2 retries. A lost reply (e.g. transient 'Host unreachable') is retried
        only if the request is idempotent or `already_done()` shows it did not take effect."""
        for attempt in range(3):
            try:
                return fn()
            except RuntimeError as error:
                self.log(f"  (service retry {attempt + 1}/2 for {what}: {str(error).splitlines()[-1][:100]})")
                self.log.retries = getattr(self.log, "retries", 0) + 1
                if already_done and already_done():
                    return None
                time.sleep(0.5)
        raise StageFail(f"service {what} failed after 3 attempts")

    def control(self, request, already_done=None):
        self._call(request, lambda: diag.service(self.gz, CONTROL, "gz.msgs.WorldControl", request), already_done)

    def pause(self):
        self.control("pause: true")

    def unpause(self):
        self.control("pause: false")

    def step(self, n):
        """Advance exactly n 1 ms iterations while paused and wait until the pose stream shows it."""
        start = self.latest_paused_time()
        target = start + n * 1e-3 - 5e-4

        def stepped():
            time.sleep(n * 0.002 + 0.5)
            p = self.streams.latest()
            return p is not None and p[0] >= target
        self.control(f"pause: true, multi_step: {n}", already_done=stepped)
        self.wait_pose(lambda p: p[0] >= start + n * 1e-3 - 5e-4, 10 + n * 0.005, f"multi_step {n}")
        time.sleep(0.1)

    def latest_paused_time(self):
        time.sleep(0.25)        # let the paused pose publication arrive
        return self.streams.latest()[0]

    def set_pose(self, z):
        self._call(f"set_pose z={z}", lambda: diag.service(
            self.gz, SET_POSE, "gz.msgs.Pose", f'name: "airmouse", position: {{x: 0, y: 0, z: {z}}}, '
            'orientation: {x: 0, y: 0, z: 0, w: 1}'))

    def wait_pose(self, predicate, timeout, what):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            p = self.streams.latest() if self.streams else None
            if p and predicate(p):
                return p
            time.sleep(0.02)
        p = self.streams.latest() if self.streams else None
        n = len(self.streams.poses) if self.streams else 0
        raise StageFail(f"timed out waiting for {what} (pose samples={n}, latest t/z="
                        f"{'none' if p is None else f'{p[0]:.3f}/{p[3]:.6f}'})")

    def wait_rest(self):
        """Unpaused: on the ground and stationary (all pose components change < 1e-4 over 0.3 s sim)."""
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            with self.streams.lock:
                p = list(self.streams.poses[-60:])
            if p and p[-1][3] < 0.06:
                recent = [r for r in p if r[0] >= p[-1][0] - 0.3]
                if recent[-1][0] - recent[0][0] >= 0.25 and np.ptp(np.array(recent)[:, 1:], axis=0).max() < 1e-4:
                    return p[-1]
            time.sleep(0.05)
        raise StageFail("vehicle did not come to rest on the ground within 40 s")

    def poses_between(self, t0, t1):
        """Poses in [t0, t1], one per timestamp. While paused the stream repeats a stamp (and a
        paused set_pose changes z under the same stamp), so the LAST sample per stamp is kept."""
        with self.streams.lock:
            latest = {}
            for p in self.streams.poses:
                if t0 <= p[0] <= t1:
                    latest[p[0]] = p
        return np.array([latest[t] for t in sorted(latest)])

    def land(self):
        self.command(0.0)
        self.set_pose(0.045)

    def launch(self, speeds, spin_steps):
        """Rest -> pause -> command -> exact spin-up dwell -> set_pose z=2 (paused). Returns reset sim time."""
        rest = self.wait_rest()
        self.pause()
        self.command(speeds)
        time.sleep(0.5)           # command delivered before the first stepped iteration (0.15 s was marginal)
        self.step(spin_steps)
        t_pause = self.latest_paused_time()
        self.set_pose(2)
        # A paused set_pose is applied but not published until the world steps (OBSERVED):
        # advance exactly one 1 ms iteration and take that sample as the reset time.
        self.control("pause: true, multi_step: 1")
        reset = self.wait_pose(lambda p: p[0] > t_pause and abs(p[3] - 2.0) < 1e-3, 10,
                               "reset to z=2 after paused set_pose + 1 step")
        time.sleep(0.25)
        return reset[0]

    def save(self):
        with self.streams.lock:
            poses = np.array(self.streams.poses)
            joints = list(self.streams.joints)
            wrench = {i: list(r) for i, r in self.streams.wrench.items()}
        if len(poses):
            np.savetxt(self.log.dir / f"{self.tag}_pose.csv", poses, delimiter=",", fmt="%.9f",
                       header="sim_time_s,x,y,z,qx,qy,qz,qw", comments="")
        if joints:
            np.savetxt(self.log.dir / f"{self.tag}_joint.csv", np.array([[t, *v] for t, v in joints]),
                       delimiter=",", fmt="%.9f", header="sim_time_s," + ",".join(JOINTS), comments="")
        if any(wrench.values()):
            with (self.log.dir / f"{self.tag}_wrench.csv").open("w") as f:
                f.write("rotor,sim_time_s,fx,fy,fz,tx,ty,tz\n")
                for i in range(4):
                    for r in wrench[i]:
                        f.write(f"{i}," + ",".join(f"{v:.9g}" for v in r) + "\n")
        (self.log.dir / f"{self.tag}_events.txt").write_text("\n".join(self.events) + "\n")

    def close(self):
        if self.helper and self.helper.poll() is None:
            try:
                self.send("speed 0")
                self.send("quit")
                self.helper.wait(timeout=3)
            except Exception:
                self.helper.kill()
        if self.streams:
            try:
                self.save()
            except Exception as error:
                self.log(f"  (could not save session data: {error})")
            self.streams.stop()
        self.server.stop()


# --------------------------------------------------------------------------- analysis helpers
def predicted_az(omega):
    return (4 * K * omega**2 - MASS * G) / MASS


def fit_az(poses, t0, zmin=0.15):
    sel = poses[(poses[:, 0] >= t0) & (poses[:, 3] > zmin)]
    if len(sel) < 6:
        raise StageFail(f"too few airborne pose samples to fit a_z (n={len(sel)})")
    c = np.polyfit(sel[:, 0] - t0, sel[:, 3], 2)
    return 2 * c[0], c[1], sel


def fmt(x, n=5):
    return f"{x:+.{n}f}"


# --------------------------------------------------------------------------- stages
def stage0(ctx):
    log = ctx.log
    ok = True
    others = gz_sim_processes()
    ok &= log.check(0, "no gz sim process running before the test", not others,
                    f"{len(others)} running", "0", "OBSERVED")
    version = subprocess.run([ctx.gz, "sim", "--versions"], text=True, capture_output=True).stdout.strip()
    ok &= log.check(0, "gz sim version", version == GZ_VERSION, version, GZ_VERSION, "OBSERVED")
    sha = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
    ctx.baseline_sha_before = sha
    ok &= log.check(0, "baseline SHA-256", sha == BASELINE_SHA, sha, BASELINE_SHA, "OBSERVED")
    missing = [t for t in REQUIRED_TOOLS if not (TOOLS / t).exists()]
    ok &= log.check(0, "required tools present", not missing,
                    "all present" if not missing else f"missing {missing}", ", ".join(REQUIRED_TOOLS), "OBSERVED")
    ok &= log.check(0, "jointfix diagnostic SDF present", JOINTFIX.exists(), str(JOINTFIX.exists()), "True", "OBSERVED")
    try:
        diag.compile_publisher(TOOLS / "airmouse_hover_helper.cc", ctx.binary)
        built = ctx.binary.exists()
        detail = "built"
    except RuntimeError as error:
        built, detail = False, str(error).splitlines()[-1]
    ok &= log.check(0, "airmouse_hover_helper builds (Apple Clang, gz-transport13/gz-msgs10)", built, detail,
                    "built", "OBSERVED")
    try:
        diag.compile_publisher(TOOLS / "airmouse_sensor_probe.cc", ctx.probe_bin)
        built, detail = ctx.probe_bin.exists(), "built"
    except RuntimeError as error:
        built, detail = False, str(error).splitlines()[-1]
    ok &= log.check(0, "airmouse_sensor_probe builds", built, detail, "built", "OBSERVED")
    for name in REQUIRED_TOOLS:
        if name.endswith(".py"):
            r = subprocess.run([sys.executable, "-m", "py_compile", str(TOOLS / name)], capture_output=True, text=True)
            ok &= log.check(0, f"{name} compiles", r.returncode == 0, "ok" if r.returncode == 0 else r.stderr.strip(),
                            "ok", "OBSERVED")
    return ok


def parse_model(path):
    root = ET.parse(path).getroot()
    model = next(m for m in root.iter("model") if m.get("name") == "airmouse")
    mass = sum(float(link.find("inertial/mass").text) for link in model.findall("link")
               if link.find("inertial/mass") is not None)
    joints = {j.get("name"): j for j in model.findall("joint")}
    links = {l.get("name"): l for l in model.findall("link")}
    plugins = [p for p in model.findall("plugin") if "MulticopterMotorModel" in (p.get("name") or "")]
    plugins.sort(key=lambda p: int(p.findtext("actuator_number")))
    return mass, joints, links, plugins


def floats(text):
    return [float(v) for v in (text or "").split()]


def stage1(ctx):
    log = ctx.log
    ok = True
    files = [BASELINE] + sorted(DIAG_DIR.glob("*.sdf"))
    for f in files:
        r = subprocess.run([ctx.gz, "sdf", "-k", str(f)], text=True, capture_output=True)
        valid = r.returncode == 0 and "Valid" in r.stdout
        ok &= log.check(1, f"gz sdf -k {f.relative_to(ROOT)}", valid,
                        (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else f"rc={r.returncode}",
                        "Valid.", "OBSERVED")
    for f in [BASELINE, JOINTFIX]:
        rel = f.relative_to(ROOT)
        mass, joints, links, plugins = parse_model(f)
        ok &= log.check(1, f"{rel}: total mass", abs(mass - 1.2) < 1e-9, f"{mass:.6f} kg", "1.200 kg", "OBSERVED")
        poses = {n: floats(joints[n].findtext("pose")) for n in JOINTS}
        ok &= log.check(1, f"{rel}: rotor joint poses", all(p == [0.0] * 6 for p in poses.values()),
                        {n: p for n, p in poses.items()}, "0 0 0 0 0 0 each", "OBSERVED")
        lp = {f"rotor_{i}": floats(links[f"rotor_{i}"].findtext("pose"))[:2] for i in range(4)}
        expect = {f"rotor_{i}": [s * ARM for s in sx] for i, sx in enumerate([(1, 1), (-1, 1), (-1, -1), (1, -1)])}
        ok &= log.check(1, f"{rel}: rotor link positions", all(np.allclose(lp[n], expect[n], atol=1e-9) for n in lp),
                        lp, "(±0.282843, ±0.282843): +,+ / -,+ / -,- / +,-", "OBSERVED")
        slow = [float(p.findtext("rotorVelocitySlowdownSim")) for p in plugins]
        ok &= log.check(1, f"{rel}: rotorVelocitySlowdownSim", slow == [1.0] * 4, slow, "[1,1,1,1]", "OBSERVED")
        kk = [float(p.findtext("motorConstant")) for p in plugins]
        ok &= log.check(1, f"{rel}: motorConstant", all(abs(k - K) < 1e-15 for k in kk), kk, "8.54858e-06 x4", "OBSERVED")
        dirs = [p.findtext("turningDirection") for p in plugins]
        ok &= log.check(1, f"{rel}: turning directions (actuator 0..3)", dirs == ["ccw", "cw", "ccw", "cw"], dirs,
                        "ccw/cw/ccw/cw", "OBSERVED")
        jmap = [p.findtext("jointName") for p in plugins]
        ok &= log.check(1, f"{rel}: actuator->joint mapping", jmap == JOINTS, jmap, JOINTS, "OBSERVED")
    for f in sorted(DIAG_DIR.glob("*.sdf")):
        if f == JOINTFIX:
            continue
        _, joints, _, _ = parse_model(f)
        legacy = any(floats(joints[n].findtext("pose")) != [0.0] * 6 for n in JOINTS)
        log.info(1, f"{f.relative_to(ROOT)} geometry",
                 "LEGACY pre-fix joint poses (diagnostic history only, not used by later stages)" if legacy
                 else "fixed joint poses", "OBSERVED")
    return ok


def stage2(ctx):
    log = ctx.log
    server = Server(ctx.gz, BASELINE, log.dir / "server_stage2.log")
    try:
        deadline = time.monotonic() + 40
        info = None
        while time.monotonic() < deadline:
            info, err = diag.audit_topic(ctx.gz)
            if info and info["subscribers"] == 4:
                break
            time.sleep(0.5)
        streams = Streams(ctx.gz)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 10 and not streams.latest():
            time.sleep(0.1)
        pose = streams.latest()
        streams.stop()
        ok = log.check(2, "world loads (airmouse pose published)", pose is not None,
                       "pose received" if pose else "no pose", "pose received", "OBSERVED")
        ok &= log.check(2, "motor topic subscribers", bool(info) and info["subscribers"] == 4,
                        info["subscribers"] if info else info, 4, "OBSERVED")
        ok &= log.check(2, "motor topic publishers (nothing else publishing)", bool(info) and info["publishers"] == 0,
                        info["publishers"] if info else info, 0, "OBSERVED")
        return ok
    finally:
        server.stop()


def stages3to5(ctx):
    """One session on the jointfix diagnostic SDF; stages evaluated in order afterwards."""
    log = ctx.log
    s = Session(ctx.gz, ctx.binary, JOINTFIX, log, "stage3-5", joints=True, forces=True)
    try:
        log(f"  session: gate {s.gate}")
        rest = s.wait_rest()
        stopped_window = (rest[0] - 0.25, rest[0])
        cmd_line = s.command(HOVER_CMD)                       # live, unpaused: latency measurement
        cmd_sim = float(cmd_line.split("cmd_sim=")[1].split()[0])
        first = s.expect("FIRST_NONZERO", 5)
        s.wait_pose(lambda p: p[0] >= cmd_sim + 1.0, 15, "1 s spin-up on ground")
        ground_window = (cmd_sim + 0.5, cmd_sim + 1.0)
        s.set_pose(2)
        reset = s.wait_pose(lambda p: abs(p[3] - 2.0) < 0.01 and p[0] > cmd_sim + 1.0, 10, "reset to z=2")
        s.wait_pose(lambda p: p[0] >= reset[0] + 1.0, 15, "1 s airborne")
        air_window = (reset[0] + 0.05, reset[0] + 1.0)
        s.land()
        with s.streams.lock:
            joints = list(s.streams.joints)
            wrench = {i: list(r) for i, r in s.streams.wrench.items()}
    finally:
        s.close()
    ctx.rates_jointfix = {"joint_state": joints, **{f"rotor_{i}_force_torque": wrench[i] for i in range(4)}}

    # Stage 3 ------------------------------------------------------------------
    log.stage(3, "Command path")
    sim_delay = float(first.split("sim_delay=")[1].split()[0])
    wall_delay = float(first.split("wall_delay=")[1].split()[0])
    ok3 = log.check(3, "helper connection gate (gz topic -i pub=1 sub=4, HasConnections=1)", True,
                    f"passed after {s.gate['wall_s']:.2f} s wall", "pass", "OBSERVED")
    ok3 &= log.check(3, "command -> first joint motion latency (sim)", sim_delay <= 0.020 + 1e-9,
                     f"{sim_delay * 1e3:.1f} ms sim ({wall_delay * 1e3:.1f} ms wall)", "<= 20 ms sim", "OBSERVED")
    log.info(3, "latency resolution", "200 Hz joint-state sampling -> 5 ms quantisation", "INFERRED")
    if not ok3:
        return 3

    # Stage 4 ------------------------------------------------------------------
    log.stage(4, "Joint speeds at 586.8 rad/s")
    jt = np.array([[t, *v] for t, v in joints if cmd_sim <= t <= cmd_sim + 1.0])
    ok4 = len(jt) > 50
    t95_expected = TAU_UP * math.log(20)
    finals, t95s = [], []
    for i in range(4):
        v = jt[:, 1 + i]
        steady = v[jt[:, 0] >= cmd_sim + 0.3]
        final = float(steady.mean())
        finals.append(final)
        idx = np.argmax(SIGNS[i] * v >= 0.95 * HOVER_CMD)
        t95 = float(jt[idx, 0] - cmd_sim) if SIGNS[i] * v[idx] >= 0.95 * HOVER_CMD else float("nan")
        t95s.append(t95)
        ok4 &= log.check(4, f"rotor_{i} steady speed", abs(final - SIGNS[i] * HOVER_CMD) <= 0.001 * HOVER_CMD,
                         f"{final:+.4f} rad/s", f"{SIGNS[i] * HOVER_CMD:+.1f} (±0.1 %)", "OBSERVED")
        ok4 &= log.check(4, f"rotor_{i} t95 from command", abs(t95 - t95_expected) <= 0.010,
                         f"{t95 * 1e3:.1f} ms", f"{t95_expected * 1e3:.1f} ± 10 ms (ANALYTICAL tau*ln20)", "OBSERVED")
    signs = ["+" if f > 0 else "-" for f in finals]
    ok4 &= log.check(4, "rotation signs", signs == ["+", "-", "+", "-"], ",".join(signs), "+,-,+,-", "OBSERVED")
    if not ok4:
        return 4

    # Stage 5 ------------------------------------------------------------------
    log.stage(5, "Force/torque sensors (jointfix diagnostic SDF)")
    ok5 = True
    axial_expected = K * HOVER_CMD**2 - 0.001 * G
    for name, (a, b) in (("ground, motors stopped", stopped_window), ("ground, spun up", ground_window),
                         ("airborne, spun up", air_window)):
        for i in range(4):
            rows = np.array([r[1:] for r in wrench[i] if a <= r[0] <= b])
            if not len(rows):
                ok5 &= log.check(5, f"{name} rotor_{i} samples", False, 0, "> 0", "OBSERVED")
                continue
            mean = rows.mean(axis=0)
            fxy = float(np.abs(rows[:, :2]).max())
            tq = float(np.abs(rows[:, 3:]).max())
            if "stopped" in name:
                ok5 &= log.check(5, f"{name} rotor_{i} Fz", abs(mean[2] + 0.00981) <= 0.01 * 0.00981,
                                 f"{mean[2]:+.6f} N (n={len(rows)})", "-0.00981 N ±1 %", "OBSERVED")
            else:
                ok5 &= log.check(5, f"{name} rotor_{i} Fz", abs(mean[2] - axial_expected) <= 0.01 * axial_expected,
                                 f"{mean[2]:+.6f} N (n={len(rows)})",
                                 f"{axial_expected:.5f} N ±1 % (ANALYTICAL k*w^2 - m_r*g)", "OBSERVED")
            ok5 &= log.check(5, f"{name} rotor_{i} in-plane |F| and |T| peak", fxy < 1e-3 and tq < 1e-4,
                             f"|Fxy|max={fxy:.2e} N, |T|max={tq:.2e} N*m", "< 1e-3 N, < 1e-4 N*m", "OBSERVED")
    if not ok5:
        return 5
    return None


def vertical_run(s, omega, spin_steps, record):
    t_reset = s.launch(omega, spin_steps)
    s.unpause()
    s.wait_pose(lambda p: p[0] >= t_reset + record or p[3] < 0.15, 20, f"record {record} s")
    time.sleep(0.2)
    poses = s.poses_between(t_reset, t_reset + record)
    s.land()
    return t_reset, poses


def stages6to9(ctx):
    log = ctx.log
    s = Session(ctx.gz, ctx.binary, BASELINE, log, "stage6-9")
    try:
        log(f"  session (baseline SDF): boot audit {s.boot_audit['publishers']} pub / "
            f"{s.boot_audit['subscribers']} sub; gate {s.gate}")

        if not getattr(ctx, "only9", False):
            # Stage 6 --------------------------------------------------------------
            log.stage(6, "Vertical acceleration (airborne window only; spin-up 200 ms exact on ground)")
            ok6 = True
            for omega in (500.0, 586.8, 700.0):
                t_reset, poses = vertical_run(s, omega, 200, 0.8)
                az, v0, sel = fit_az(poses, t_reset)
                pred = predicted_az(omega)
                ok6 &= log.check(6, f"a_z at {omega:g} rad/s", abs(az - pred) <= 0.05,
                                 f"{fmt(az)} m/s^2 (v0 {v0:+.4f} m/s, n={len(sel)}, "
                                 f"window {sel[0, 0] - t_reset:.3f}-{sel[-1, 0] - t_reset:.3f} s)",
                                 f"{fmt(pred)} ±0.05 (ANALYTICAL)", "OBSERVED")
                ctx.az6 = getattr(ctx, "az6", {})
                ctx.az6[omega] = az
            if not ok6:
                return 6

            # Stage 7 --------------------------------------------------------------
            log.stage(7, "Hover acceptance (spin-up 1000 ms exact on ground, reset z=2, record 2 s)")
            hover = hover_run(s)
            ok7 = log.check(7, "|a_z - 0.0019|", abs(hover["az"] - 0.0019) < 0.05,
                            f"a_z {fmt(hover['az'])} m/s^2 (|diff| {abs(hover['az'] - 0.0019):.5f})", "< 0.05", "OBSERVED")
            ok7 &= log.check(7, "max |z - 2| over 2 s", hover["zdev"] < 0.02,
                             f"{hover['zdev']:.5f} m (v0 {hover['v0']:+.5f} m/s, tilt {hover['tilt']:.4f} deg, "
                             f"drift {hover['drift']:.6f} m, n={hover['n']})", "< 0.02 m", "OBSERVED")
            if not ok7:
                return 7

            # Stage 8 --------------------------------------------------------------
            log.stage(8, "Differential thrust (delta = 5 rad/s), primary-axis angular acceleration")
            ok8 = True
            for pattern, axis_index, axis in (("roll", 0, "roll"), ("pitch", 1, "pitch"), ("yaw", 2, "yaw")):
                t_reset = s.launch(HOVER_CMD, 1000)
                s.step(100)                                 # exact 0.1 s airborne hover hold, paused at the end
                t_cmd = t_reset + 0.1
                w = HOVER_CMD + 5.0 * dt.PATTERNS[pattern]
                s.command(list(w))
                time.sleep(0.15)
                s.unpause()
                s.wait_pose(lambda p: p[0] >= t_cmd + 0.35, 15, f"{pattern} window")
                time.sleep(0.2)
                sel = s.poses_between(t_cmd, t_cmd + 0.35)
                s.land()
                ang = np.array([dt.euler(q) for q in sel[:, 4:8]])
                t = sel[:, 0] - t_cmd
                fit = t >= 0.08
                c = np.polyfit(t[fit], ang[fit, axis_index], 2)
                alpha = 2 * c[0]
                _, tau = dt.predicted(HOVER_CMD, 5.0, pattern)
                pred = tau[axis_index] / dt.I_RIGID[axis_index]
                others = [2 * np.polyfit(t[fit], ang[fit, j], 2)[0] for j in range(3) if j != axis_index]
                ok8 &= log.check(8, f"{pattern} pattern: {axis} alpha", abs(alpha - pred) <= 0.02 * abs(pred),
                                 f"{alpha:+.5f} rad/s^2 (ratio {alpha / pred:.4f}; cross-axis "
                                 f"{', '.join(f'{o:+.1e}' for o in others)}; n={fit.sum()})",
                                 f"{pred:+.5f} ±2 % (ANALYTICAL tau/I_rigid)", "OBSERVED")
            if not ok8:
                return 8

        # Stage 9 --------------------------------------------------------------
        log.stage(9, "Repeatability: Stage 6 (586.8) x3 and Stage 7 x3")
        az6, hz_az, hz_dev = [], [], []
        for k in range(3):
            t_reset, poses = vertical_run(s, HOVER_CMD, 200, 0.8)
            az6.append(fit_az(poses, t_reset)[0])
            h = hover_run(s)
            hz_az.append(h["az"])
            hz_dev.append(h["zdev"])
            log(f"  repeat {k + 1}: stage6 a_z {az6[-1]:+.7f}; stage7 a_z {h['az']:+.7f}, max|z-2| {h['zdev']:.7f}")
        ok9 = True
        for name, values in (("Stage 6 a_z @586.8", az6), ("Stage 7 a_z", hz_az), ("Stage 7 max |z-2|", hz_dev)):
            v = np.array(values)
            spread = float(np.ptp(v) / abs(v.mean()))
            ok9 &= log.check(9, f"{name} spread (max-min)/|mean|", spread < 0.01,
                             f"{spread * 100:.4f} % ({', '.join(f'{x:.7f}' for x in v)})", "< 1 %", "OBSERVED")
        if not ok9:
            return 9
    finally:
        s.close()
    return None


def hover_run(s):
    t_reset = s.launch(HOVER_CMD, 1000)
    s.unpause()
    s.wait_pose(lambda p: p[0] >= t_reset + 2.0, 20, "2 s hover")
    time.sleep(0.2)
    poses = s.poses_between(t_reset, t_reset + 2.0)
    s.land()
    az, v0, sel = fit_az(poses, t_reset)
    return {"az": az, "v0": v0, "n": len(poses),
            "zdev": float(np.abs(poses[:, 3] - 2.0).max()),
            "tilt": float(np.degrees(2 * np.arcsin(np.clip(np.hypot(poses[:, 4], poses[:, 5]), 0, 1))).max()),
            "drift": float(np.hypot(poses[:, 1], poses[:, 2]).max())}


class Probe:
    """Runs airmouse_sensor_probe and collects IMU / SCAN / IMG lines."""

    def __init__(self, binary, specs, raw_path):
        self.proc = subprocess.Popen([str(binary)] + specs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1)
        self.lock = threading.Lock()
        self.imu, self.scan, self.img = {}, {}, {}
        self.ready = threading.Event()
        self.raw = open(raw_path, "w")
        threading.Thread(target=self._pump, daemon=True).start()
        if not self.ready.wait(10):
            self.stop()
            raise StageFail("sensor probe did not start")

    def _pump(self):
        for line in self.proc.stdout:
            parts = line.split()
            if not parts:
                continue
            kind = parts[0]
            if kind == "PROBE_READY":
                self.ready.set()
            elif kind == "IMU":
                with self.lock:
                    self.imu.setdefault(parts[1], []).append([float(v) for v in parts[2:9]])
            elif kind == "SCAN":
                head = [float(v) for v in parts[2:8]]
                with self.lock:
                    self.scan.setdefault(parts[1], []).append((head, np.array([float(v) for v in parts[8:]])))
                line = " ".join(parts[:8]) + " ...\n"          # keep the raw log small
            elif kind == "IMG":
                with self.lock:
                    self.img.setdefault(parts[1], []).append([float(v) for v in parts[2:11]])
            self.raw.write(line)

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.raw.close()


def sensors_in(path):
    out = []
    for sensor in ET.parse(path).getroot().iter("sensor"):
        out.append({"name": sensor.get("name"), "type": sensor.get("type"),
                    "rate": float(sensor.findtext("update_rate") or "nan"),
                    "topic": sensor.findtext("topic"), "el": sensor})
    return out


def rate_of(stamps):
    stamps = sorted(set(stamps))
    if len(stamps) < 3:
        return float("nan"), 0.0
    span = stamps[-1] - stamps[0]
    return (len(stamps) - 1) / span, span


def window(rows, a, b):
    return np.array([r for r in rows if a <= r[0] <= b])


def imu_checks(ctx, sensor):
    log = ctx.log
    topic = sensor["topic"]
    noise = {}
    for group, key in (("angular_velocity", "gyro"), ("linear_acceleration", "accel")):
        noise[key] = float(sensor["el"].findtext(f"imu/{group}/z/noise/stddev") or "nan")
    log(f"  IMU {sensor['name']} topic {topic}, configured {sensor['rate']:g} Hz, "
        f"noise stddev gyro {noise['gyro']} rad/s, accel {noise['accel']} m/s^2")
    s = Session(ctx.gz, ctx.binary, BASELINE, log, "stage10-imu")
    probe = None
    try:
        probe = Probe(ctx.probe_bin, [f"imu:{topic}"], log.dir / "stage10-imu_probe.txt")
        rest = s.wait_rest()
        s.wait_pose(lambda p: p[0] >= rest[0] + 1.0, 15, "1 s of IMU data at rest")
        rest_win = (rest[0], rest[0] + 1.0)
        t1 = s.launch(HOVER_CMD, 1000)
        s.unpause()
        s.wait_pose(lambda p: p[0] >= t1 + 1.0, 15, "1 s hover")
        hover_win = (t1 + 0.1, t1 + 1.0)
        s.land()
        t2 = s.launch(700.0, 200)
        s.unpause()
        s.wait_pose(lambda p: p[0] >= t2 + 0.5, 15, "0.5 s climb at 700")
        climb_win = (t2 + 0.05, t2 + 0.5)
        s.land()
        time.sleep(0.3)
        with probe.lock:
            data = list(probe.imu.get(topic, []))
    finally:
        if probe:
            probe.stop()
        s.close()
    rate, span = rate_of([r[0] for r in data])
    ok = log.check(10, "IMU rate (sim time)", abs(rate - sensor["rate"]) <= 0.1 * sensor["rate"],
                   f"{rate:.1f} Hz over {span:.2f} s (n={len(data)})", f"{sensor['rate']:g} Hz ±10 %", "OBSERVED")
    if not ok:
        return False
    r = window(data, *rest_win)
    mean, std = r[:, 1:].mean(axis=0), r[:, 1:].std(axis=0)
    ok &= log.check(10, "IMU at rest: accel z", abs(mean[2] - G) <= 0.05,
                    f"{mean[2]:+.4f} m/s^2 (std {std[2]:.4f}, n={len(r)})", f"+{G} ±0.05 (ANALYTICAL: specific force = g)",
                    "OBSERVED")
    ok &= log.check(10, "IMU at rest: accel x, y", max(abs(mean[0]), abs(mean[1])) <= 0.05,
                    f"{mean[0]:+.4f}, {mean[1]:+.4f} m/s^2", "0 ±0.05", "OBSERVED")
    ok &= log.check(10, "IMU at rest: gyro", np.abs(mean[3:]).max() <= 0.002,
                    f"({mean[3]:+.5f}, {mean[4]:+.5f}, {mean[5]:+.5f}) rad/s", "0 ±0.002 rad/s", "OBSERVED")
    ok &= log.check(10, "IMU noise applied: accel z std / configured", 0.5 <= std[2] / noise["accel"] <= 2.0,
                    f"{std[2]:.5f} / {noise['accel']} = {std[2] / noise['accel']:.2f}", "0.5-2.0", "OBSERVED")
    ok &= log.check(10, "IMU noise applied: gyro z std / configured", 0.5 <= std[5] / noise["gyro"] <= 2.0,
                    f"{std[5]:.6f} / {noise['gyro']} = {std[5] / noise['gyro']:.2f}", "0.5-2.0", "OBSERVED")
    for name, win, omega in (("hover 586.8", hover_win, HOVER_CMD), ("climb 700", climb_win, 700.0)):
        w = window(data, *win)
        expected = 4 * K * omega**2 / MASS
        ok &= log.check(10, f"IMU {name}: accel z = thrust/m", abs(w[:, 3].mean() - expected) <= 0.05,
                        f"{w[:, 3].mean():+.4f} m/s^2 (n={len(w)})", f"{expected:+.5f} ±0.05 (ANALYTICAL 4k*w^2/m)",
                        "OBSERVED")
    return ok


WALL_DIST = 3.0          # wall face distance along +x from the vehicle origin (diagnostic world only)


def make_wall_world(path):
    """Diagnostic copy of the CURRENT baseline plus one static wall (face at x = WALL_DIST)."""
    s = BASELINE.read_text()
    wall = (f'    <model name="diagnostic_wall"><static>true</static><pose>{WALL_DIST + 0.1} 0 1 0 0 0</pose>'
            '<link name="link"><collision name="c"><geometry><box><size>0.2 4 2</size></box></geometry></collision>'
            '<visual name="v"><geometry><box><size>0.2 4 2</size></box></geometry></visual></link></model>\n')
    assert s.count("  </world>") == 1
    path.write_text(s.replace("  </world>", wall + "  </world>"))


def lidar_checks(ctx, sensor):
    log = ctx.log
    el = sensor["el"]
    samples = int(el.findtext("lidar/scan/horizontal/samples"))
    amin, amax = float(el.findtext("lidar/scan/horizontal/min_angle")), float(el.findtext("lidar/scan/horizontal/max_angle"))
    rmin, rmax = float(el.findtext("lidar/range/min")), float(el.findtext("lidar/range/max"))
    sigma = float(el.findtext("lidar/noise/stddev"))
    ok = log.check(10, "LiDAR config: samples / FOV / range", samples == 360 and abs((amax - amin) - 2 * math.pi) < 1e-3
                   and rmin == 0.1 and rmax == 12.0,
                   f"{samples} samples, FOV {math.degrees(amax - amin):.2f} deg, range {rmin}-{rmax} m, noise {sigma} m",
                   "360 samples, 360 deg, 0.1-12 m", "OBSERVED")
    world = log.dir / "airmouse_sensor_wall.sdf"
    make_wall_world(world)
    r = subprocess.run([ctx.gz, "sdf", "-k", str(world)], text=True, capture_output=True)
    ok &= log.check(10, "LiDAR wall world (generated from baseline + wall) valid", "Valid" in r.stdout,
                    r.stdout.strip() or r.stderr.strip(), "Valid.", "OBSERVED")
    if not ok:
        return False
    s = Session(ctx.gz, ctx.binary, world, log, "stage10-lidar")
    probe = None
    try:
        probe = Probe(ctx.probe_bin, [f"scan:{sensor['topic']}"], log.dir / "stage10-lidar_probe.txt")
        rest = s.wait_rest()
        s.wait_pose(lambda p: p[0] >= rest[0] + 3.0, 30, "3 s of scans at rest")
        time.sleep(0.3)
        with probe.lock:
            scans = list(probe.scan.get(sensor["topic"], []))
    finally:
        if probe:
            probe.stop()
        s.close()
    rate, span = rate_of([h[0] for h, _ in scans])
    ok &= log.check(10, "LiDAR rate (sim time)", abs(rate - sensor["rate"]) <= 0.1 * sensor["rate"],
                    f"{rate:.2f} Hz over {span:.2f} s (n={len(scans)})", f"{sensor['rate']:g} Hz ±10 %", "OBSERVED")
    use = [(h, rr) for h, rr in scans if rest[0] <= h[0] <= rest[0] + 3.0]
    if not use:
        return log.check(10, "LiDAR scans at rest", False, 0, "> 0", "OBSERVED")
    h0 = use[0][0]
    ang = h0[2] + h0[3] * np.arange(len(use[0][1]))
    ranges = np.array([rr for _, rr in use])
    ok &= log.check(10, "LiDAR beams per scan", ranges.shape[1] == samples, ranges.shape[1], samples, "OBSERVED")
    on = np.abs(ang) <= math.radians(25)
    err = ranges[:, on] - WALL_DIST / np.cos(ang[on])
    centre = ranges[:, np.argmin(np.abs(ang))]
    ok &= log.check(10, f"LiDAR wall range, beams within ±25 deg (wall face at {WALL_DIST} m)",
                    np.isfinite(err).all() and abs(err.mean()) <= sigma,
                    f"mean error {err.mean() * 1e3:+.2f} mm over {err.size} returns; centre beam "
                    f"{centre.mean():.4f} m", f"|mean error| <= {sigma * 1e3:.0f} mm (ANALYTICAL d/cos(theta))", "OBSERVED")
    ok &= log.check(10, "LiDAR noise: error std / configured", 0.5 <= err.std() / sigma <= 2.0,
                    f"{err.std() * 1e3:.2f} mm / {sigma * 1e3:.0f} mm = {err.std() / sigma:.2f}", "0.5-2.0", "OBSERVED")
    off = np.abs(ang) >= math.radians(40)
    hits = int(np.isfinite(ranges[:, off]).sum())
    ok &= log.check(10, "LiDAR no self-hits / no spurious returns (beams >= 40 deg from wall)", hits == 0,
                    f"{hits} finite returns", "0 (open space beyond 12 m)", "OBSERVED")
    return ok


CAMERA_TYPES = {"depth_camera": ("depth", 4), "depth": ("depth", 4), "camera": ("rgb", 3)}


def camera_checks(ctx, cams):
    """Rate, image size and reading for each camera, facing the diagnostic wall."""
    log = ctx.log
    world = log.dir / "airmouse_sensor_wall.sdf"
    make_wall_world(world)
    s = Session(ctx.gz, ctx.binary, world, log, "stage10-camera")
    probe = None
    try:
        probe = Probe(ctx.probe_bin, [f"image:{c['topic']}" for c in cams], log.dir / "stage10-camera_probe.txt")
        rest = s.wait_rest()
        s.wait_pose(lambda p: p[0] >= rest[0] + 3.0, 40, "3 s of images at rest")
        time.sleep(0.5)
        with probe.lock:
            frames = {c["topic"]: list(probe.img.get(c["topic"], [])) for c in cams}
    finally:
        if probe:
            probe.stop()
        s.close()
    ok = True
    for c in cams:
        kind, bpp = CAMERA_TYPES[c["type"]]
        el = c["el"]
        w_cfg, h_cfg = int(el.findtext("camera/image/width")), int(el.findtext("camera/image/height"))
        rows = np.array(frames[c["topic"]]) if frames[c["topic"]] else np.zeros((0, 9))
        rate, span = rate_of(list(rows[:, 0])) if len(rows) else (float("nan"), 0.0)
        ok &= log.check(10, f"{c['name']} rate (sim time)", abs(rate - c["rate"]) <= 0.1 * c["rate"],
                        f"{rate:.2f} Hz over {span:.2f} s (n={len(rows)})", f"{c['rate']:g} Hz ±10 %", "OBSERVED")
        if not ok:
            return False
        sizes = {(int(r[1]), int(r[2]), int(r[5])) for r in rows}
        ok &= log.check(10, f"{c['name']} image size / bytes", sizes == {(w_cfg, h_cfg, w_cfg * h_cfg * bpp)},
                        sorted(sizes), f"{w_cfg}x{h_cfg}, {w_cfg * h_cfg * bpp} bytes", "OBSERVED")
        at_rest = rows[(rows[:, 0] >= rest[0]) & (rows[:, 0] <= rest[0] + 3.0)]
        if kind == "depth":
            sigma = float(el.findtext("camera/noise/stddev") or "0")
            cam_x = floats(el.findtext("pose"))[0] if el.findtext("pose") else 0.0
            expected = WALL_DIST - cam_x
            centre = at_rest[:, 6]
            ok &= log.check(10, f"{c['name']} centre-pixel depth to wall", abs(centre.mean() - expected) <= 0.02,
                            f"{centre.mean():.4f} m (frame std {centre.std() * 1e3:.1f} mm, n={len(centre)})",
                            f"{expected:.3f} m ±0.02 (ANALYTICAL wall {WALL_DIST} - camera x {cam_x})", "OBSERVED")
            ok &= log.check(10, f"{c['name']} noise: centre-pixel std / configured",
                            sigma == 0 or 0.5 <= centre.std() / sigma <= 2.0,
                            f"{centre.std() * 1e3:.2f} mm / {sigma * 1e3:.1f} mm", "0.5-2.0", "OBSERVED")
        else:
            ok &= log.check(10, f"{c['name']} image content (not blank, not saturated)",
                            at_rest[:, 8].mean() > 5 and 5 < at_rest[:, 7].mean() < 250,
                            f"mean {at_rest[:, 7].mean():.1f}, std {at_rest[:, 8].mean():.1f}, "
                            f"centre {at_rest[:, 6].mean():.1f} (0-255, n={len(at_rest)})",
                            "std > 5, 5 < mean < 250", "OBSERVED")
        if not ok:
            return False
    return ok


def beams(sensor):
    return int(sensor["el"].findtext("lidar/scan/horizontal/samples") or 0)


def rangefinder_checks(ctx, sensor):
    """Downward 1-beam rangefinder: rate, no return below min range at rest, and range = truth height - mount
    offset in a hover at z ~ 2 m."""
    log = ctx.log
    el = sensor["el"]
    rmin, rmax = float(el.findtext("lidar/range/min")), float(el.findtext("lidar/range/max"))
    sigma = float(el.findtext("lidar/noise/stddev"))
    mount = [float(v) for v in el.findtext("pose").split()]
    log(f"  rangefinder {sensor['name']} topic {sensor['topic']}, {sensor['rate']:g} Hz, {rmin}-{rmax} m, "
        f"sigma {sigma} m, mount z {mount[2]:+.3f} m, pitch {math.degrees(mount[4]):.1f} deg")
    s = Session(ctx.gz, ctx.binary, BASELINE, log, "stage10-rangefinder")
    probe = None
    try:
        probe = Probe(ctx.probe_bin, [f"scan:{sensor['topic']}"], log.dir / "stage10-rangefinder_probe.txt")
        rest = s.wait_rest()
        s.wait_pose(lambda p: p[0] >= rest[0] + 1.0, 15, "1 s at rest")
        rest_win = (rest[0], rest[0] + 1.0)
        t1 = s.launch(HOVER_CMD, 1000)
        s.unpause()
        s.wait_pose(lambda p: p[0] >= t1 + 2.0, 20, "2 s hover")
        time.sleep(0.3)
        poses = s.poses_between(t1, t1 + 2.0)
        s.land()
        with probe.lock:
            scans = list(probe.scan.get(sensor["topic"], []))
    finally:
        if probe:
            probe.stop()
        s.close()
    rate, span = rate_of([h[0] for h, _ in scans])
    ok = log.check(10, "rangefinder rate (sim time)", abs(rate - sensor["rate"]) <= 0.1 * sensor["rate"],
                   f"{rate:.1f} Hz over {span:.2f} s (n={len(scans)})", f"{sensor['rate']:g} Hz ±10 %", "OBSERVED")
    at_rest = [rr[0] for h, rr in scans if rest_win[0] <= h[0] <= rest_win[1]]
    ok &= log.check(10, "rangefinder at rest (sensor ~5 mm above ground, below min range): no return",
                    len(at_rest) > 0 and all(not np.isfinite(v) for v in at_rest),
                    f"{sum(not np.isfinite(v) for v in at_rest)}/{len(at_rest)} non-finite", f"all non-finite (< {rmin} m)",
                    "OBSERVED")
    hov = [(h[0], rr[0]) for h, rr in scans if t1 + 0.1 <= h[0] <= t1 + 2.0]
    if not hov or len(poses) < 10:
        return log.check(10, "rangefinder hover samples", False, len(hov), "> 0", "OBSERVED")
    t = np.array([x[0] for x in hov])
    r = np.array([x[1] for x in hov])
    truth = np.interp(t, poses[:, 0], poses[:, 3]) + mount[2]     # sensor height above ground (level hover)
    err = r - truth
    ok &= log.check(10, "rangefinder in hover: range = truth height - mount offset",
                    np.isfinite(r).all() and abs(err.mean()) <= sigma,
                    f"mean {r.mean():.4f} m vs truth {truth.mean():.4f} m: error {err.mean() * 1e3:+.1f} mm (n={len(r)})",
                    f"|mean error| <= {sigma * 1e3:.0f} mm", "OBSERVED")
    ok &= log.check(10, "rangefinder noise: error std / configured", 0.5 <= err.std() / sigma <= 2.0,
                    f"{err.std() * 1e3:.1f} mm / {sigma * 1e3:.0f} mm = {err.std() / sigma:.2f}", "0.5-2.0", "OBSERVED")
    return ok


def stage10(ctx):
    log = ctx.log
    files = [BASELINE] + sorted(DIAG_DIR.glob("*.sdf"))
    for f in files:
        for x in sensors_in(f):
            log.info(10, f"sensor in {f.relative_to(ROOT)}",
                     f"{x['name']} type={x['type']} update_rate={x['rate']:g} topic={x['topic']}", "OBSERVED")
    base = sensors_in(BASELINE)
    kinds = {x["type"] for x in base}
    families = [("IMU", {"imu"}), ("LiDAR / rangefinder", {"gpu_lidar", "lidar", "gpu_ray", "ray"}),
                ("depth camera", {"depth_camera", "depth", "rgbd_camera"}), ("RGB camera", {"camera"})]
    for label, types in families:
        if not kinds & types:
            log.info(10, f"{label} in baseline", "NOT PRESENT", "OBSERVED", status="NOT PRESENT")
    imu = [x for x in base if x["type"] == "imu"]
    if imu and not imu_checks(ctx, imu[0]):
        return False
    lidar = [x for x in base if x["type"] in ("gpu_lidar", "lidar") and beams(x) > 1]
    if lidar and not lidar_checks(ctx, lidar[0]):
        return False
    ranger = [x for x in base if x["type"] in ("gpu_lidar", "lidar") and beams(x) == 1]
    if ranger and not rangefinder_checks(ctx, ranger[0]):
        return False
    cams = [x for x in base if x["type"] in CAMERA_TYPES]
    cams.sort(key=lambda x: 0 if CAMERA_TYPES[x["type"]][0] == "depth" else 1)
    if cams and not camera_checks(ctx, cams):
        return False
    # Diagnostic-only telemetry rates recorded during Stages 3-5 (configured 200 Hz).
    ok = True
    for label, rows in getattr(ctx, "rates_jointfix", {}).items():
        rate, span = rate_of([r[0] for r in rows])
        ok &= log.check(10, f"diagnostic {label} rate (jointfix SDF, sim time)", abs(rate - 200) <= 20,
                        f"{rate:.1f} Hz over {span:.2f} s", "200 Hz ±10 %", "OBSERVED")
    return ok


# --------------------------------------------------------------------------- main
STAGE_TITLES = {
    0: "Environment", 1: "SDF validity and parsed parameters", 2: "Server boot",
    3: "Command path", 4: "Joint speeds at 586.8", 5: "Force/torque sensors",
    6: "Vertical acceleration", 7: "Hover acceptance", 8: "Differential thrust",
    9: "Repeatability", 10: "Virtual sensors",
}


def summary(log, failed_at):
    rows = []
    for stage in range(11):
        items = [r for r in log.results if r["stage"] == stage]
        if not items:
            status = "NOT RUN"
        elif any(r["status"] == "FAIL" for r in items):
            status = "FAIL"
        elif any(r["status"] == "NOT PRESENT" for r in items):
            absent = [r["item"].replace(" in baseline", "") for r in items if r["status"] == "NOT PRESENT"]
            status = f"PASS (NOT PRESENT: {', '.join(absent)})"
        else:
            status = "PASS"
        checks = [r for r in items if r["status"] in ("PASS", "FAIL")]
        rows.append((stage, STAGE_TITLES[stage], status, f"{sum(r['status'] == 'PASS' for r in checks)}/{len(checks)}"))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logdir", default=str(ROOT / "logs" / f"regression-{date.today().isoformat()}"))
    parser.add_argument("--gz-ip", default="127.0.0.1",
                        help="GZ_IP for every process started (default loopback: all processes are local, and "
                             "pinning avoids discovery loss when the network interface changes)")
    parser.add_argument("--only-stage9", action="store_true",
                        help="run Stage 0 then only Stage 9 (repeatability) on the baseline")
    args = parser.parse_args()
    os.environ["GZ_IP"] = args.gz_ip

    class Ctx:
        pass

    ctx = Ctx()
    ctx.log = log = Log(Path(args.logdir))
    ctx.only9 = args.only_stage9
    tmp = tempfile.TemporaryDirectory(prefix="airmouse-regression-")
    ctx.binary = Path(tmp.name) / "airmouse_hover_helper"
    ctx.probe_bin = Path(tmp.name) / "airmouse_sensor_probe"
    failed_at = None
    log(f"AirMouse regression {datetime.now().isoformat(timespec='seconds')}  root={ROOT}  GZ_IP={os.environ['GZ_IP']}")
    try:
        ctx.gz = gz_bin()
        plan = [(0, stage0)] if ctx.only9 else [(0, stage0), (1, stage1), (2, stage2)]
        for n, fn in plan:
            log.stage(n, STAGE_TITLES[n])
            if not fn(ctx):
                failed_at = n
                break
        if failed_at is None and not ctx.only9:
            log.stage(3, "(data collection for Stages 3-5: one session on the jointfix diagnostic SDF)")
            failed_at = stages3to5(ctx)
        if failed_at is None:
            log.stage(6, "(session for Stages 6-9 on the baseline SDF)")
            failed_at = stages6to9(ctx)
        if failed_at is None and not ctx.only9:
            log.stage(10, STAGE_TITLES[10])
            if not stage10(ctx):
                failed_at = 10
    except (StageFail, RuntimeError, OSError, subprocess.SubprocessError) as error:
        stage_now = log.current
        log(f"  [FAIL] aborted: {error}")
        log.results.append({"stage": stage_now, "item": "abort", "status": "FAIL", "measured": str(error),
                            "expected": "-", "label": "OBSERVED"})
        failed_at = stage_now
    finally:
        tmp.cleanup()
        leftovers = gz_sim_processes()
        sha_after = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
        log(f"\nService retries during run: {getattr(log, 'retries', 0)}")
        log(f"\nCleanup: gz sim processes left = {len(leftovers)}; baseline SHA-256 after = {sha_after}")

    rows = summary(log, failed_at)
    log("\nSUMMARY")
    log("| Stage | Name | Result | Checks passed |")
    log("|---|---|---|---|")
    for stage, title, status, count in rows:
        log(f"| {stage} | {title} | {status} | {count} |")
    verdict = "PASS" if failed_at is None else f"FAIL at Stage {failed_at} (later stages NOT RUN)"
    log(f"\nOVERALL: {verdict}")
    (log.dir / "results.json").write_text(json.dumps(
        {"verdict": verdict, "failed_at": failed_at, "baseline_sha_after": sha_after,
         "results": log.results, "summary": rows}, indent=1, default=str))
    md = ["| Stage | Name | Result | Checks passed |", "|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    (log.dir / "summary.md").write_text("\n".join(md) + f"\n\nOVERALL: {verdict}\n")
    return 0 if failed_at is None else 1


if __name__ == "__main__":
    sys.exit(main())
