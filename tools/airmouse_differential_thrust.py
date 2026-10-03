#!/usr/bin/env python3
"""AirMouse differential-thrust moment-arm test.

For each pattern (equal, yaw, roll, pitch): rest on ground -> spin all rotors
to the hover speed for 1 s -> set_pose to z=2 m (vehicle held airborne by
hover thrust) -> hover 0.1 s -> command the pattern -> record -> motors off
and set_pose back onto the ground upright. Measures initial body angular
acceleration and compares it with the analytical moment-arm prediction. Also
reports rotor-link positions relative to the model and joint wrenches in the
equal-speed hover phase.
"""

import argparse
import importlib.util
import math
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

ARM = 0.282843
K = 8.54858e-06
KM = 0.016
I_BASE = np.array([0.018, 0.018, 0.032])
M_ROTOR = 0.001
# Rotor point masses at the intended arm positions add m*r^2 to the rigid-body inertia.
I_RIGID = I_BASE + 4 * M_ROTOR * np.array([ARM**2, ARM**2, 2 * ARM**2])
POS = np.array([[ARM, ARM], [-ARM, ARM], [-ARM, -ARM], [ARM, -ARM]])
SPIN = np.array([1, -1, 1, -1])            # ccw, cw, ccw, cw
PATTERNS = {
    "equal": np.array([0, 0, 0, 0]),
    "yaw": np.array([1, -1, 1, -1]),        # rotors 0,2 up; 1,3 down
    "roll": np.array([1, 1, -1, -1]),       # +y side (0,1) up; -y side (2,3) down
    "pitch": np.array([1, -1, -1, 1]),      # +x side (0,3) up; -x side (1,2) down
}


def load(name):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acc = load("airmouse_hover_acceptance.py")
diag = load("measure_airmouse_diagnostic.py")


class PoseRecorder(acc.Recorder):
    """Recorder that also keeps rotor-link positions (relative to the model)."""

    def __init__(self, *a, **kw):
        self.rotors = []                    # (t, [(x, y, z) for rotor 0..3])
        super().__init__(*a, **kw)

    def pump(self, label, proc, diag_module):
        if label != "pose":
            return super().pump(label, proc, diag_module)
        for message in diag_module.message_stream(proc):
            if message is None:
                continue
            t = acc.stamp(message)
            body = diag_module.parse_pose_message(message)
            if t is None or body is None:
                continue
            rotor = {}
            for entry in message.get("pose", []):
                name = entry.get("name", "")
                for i in range(4):
                    if name == f"rotor_{i}" or name.endswith(f"::rotor_{i}"):
                        rotor[i] = acc.vec(entry.get("position", {}))
            with self.lock:
                self.poses.append((t, body["x"], body["y"], body["z"],
                                   body["qx"], body["qy"], body["qz"], body["qw"]))
                if len(rotor) == 4:
                    self.rotors.append((t, [rotor[i] for i in range(4)]))


def euler(q):
    x, y, z, w = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return roll, pitch, yaw


def predicted(omega, delta, pattern):
    w = omega + delta * PATTERNS[pattern]
    dF = K * (w**2 - omega**2)
    tau = np.array([np.sum(POS[:, 1] * dF), -np.sum(POS[:, 0] * dF), -KM * np.sum(SPIN * dF)])
    return dF, tau


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--omega", type=float, default=586.8)
    parser.add_argument("--delta", type=float, default=5.0)
    parser.add_argument("--window", type=float, default=0.35, help="sim seconds recorded after the pattern command")
    parser.add_argument("--fit-start", type=float, default=0.08, help="fit window start after command (>3 motor time constants)")
    parser.add_argument("--label", required=True, help="name for this geometry, e.g. old or fixed")
    parser.add_argument("--out", default=".")
    args = parser.parse_args()
    gz = shutil.which("gz")
    if not gz:
        parser.error("gz not found on PATH")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    before, unavailable = diag.audit_topic(gz)
    if unavailable or before["subscribers"] != 4 or before["publishers"] != 0:
        raise RuntimeError(f"pre-test audit must show 0 publishers / 4 subscribers: {before or unavailable}")

    marks = {}
    rec = helper = None
    with tempfile.TemporaryDirectory(prefix="airmouse-diff-") as tmp:
        binary = Path(tmp) / "airmouse_hover_helper"
        diag.compile_publisher(Path(__file__).with_name("airmouse_hover_helper.cc"), binary)
        helper = subprocess.Popen([str(binary), "100"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  text=True, bufsize=1)
        lines = queue.Queue()
        threading.Thread(target=lambda: [lines.put(l.strip()) for l in helper.stdout], daemon=True).start()

        def send(cmd):
            helper.stdin.write(cmd + "\n")
            helper.stdin.flush()

        def expect(prefix, timeout=3):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line.startswith(prefix):
                    return line
            raise RuntimeError(f"helper did not report {prefix}")

        def set_pose(z):
            diag.service(gz, acc.SET_POSE_SERVICE, "gz.msgs.Pose",
                         f'name: "airmouse", position: {{x: 0, y: 0, z: {z}}}, '
                         'orientation: {x: 0, y: 0, z: 0, w: 1}')

        def wait_rest():
            # Stationary on the ground: z, x, y and orientation change < 1e-4 over 0.3 s sim.
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with rec.lock:
                    p = list(rec.poses[-40:])
                if p and p[-1][3] < 0.06:
                    recent = [r for r in p if r[0] >= p[-1][0] - 0.3]
                    if recent[-1][0] - recent[0][0] >= 0.25:
                        span = np.ptp(np.array(recent)[:, 1:], axis=0)
                        if span.max() < 1e-4:
                            return p[-1]
                time.sleep(0.05)
            raise RuntimeError("vehicle did not come to rest on the ground")

        try:
            expect("READY", 10)
            t0 = time.monotonic()
            while True:
                info, _ = diag.audit_topic(gz)
                send("status")
                if (info and info["publishers"] == 1 and info["subscribers"] == 4
                        and expect("STATUS").endswith("connected=1")):
                    break
                if time.monotonic() - t0 > 30:
                    raise RuntimeError("connection gate not passed")
                time.sleep(0.2)
            print(f"[{args.label}] connection gate passed: publishers=1 subscribers=4 HasConnections=1")
            rec = PoseRecorder(gz, diag, True)
            acc.wait_sim(rec, lambda p: True, 10, "first pose")

            for name in PATTERNS:
                rest = wait_rest()
                send(f"speed {args.omega:.9g}")
                expect("CMD")
                acc.wait_sim(rec, lambda p: p[0] >= rest[0] + 1.0, 15, "spin-up")
                set_pose(2)
                reset = acc.wait_sim(rec, lambda p: abs(p[3] - 2.0) < 0.01 and p[0] > rest[0] + 1.0, 10, "reset")
                acc.wait_sim(rec, lambda p: p[0] >= reset[0] + 0.1, 10, "hover hold")
                w = args.omega + args.delta * PATTERNS[name]
                send("speeds " + " ".join(f"{v:.9g}" for v in w))
                cmd = float(expect("CMD").split("cmd_sim=")[1].split()[0])
                end = acc.wait_sim(rec, lambda p: p[0] >= cmd + args.window, 15, "pattern window")
                send("speed 0")
                expect("CMD")
                set_pose(0.045)
                marks[name] = (reset[0], cmd, end[0])
                print(f"[{args.label}] {name}: reset t={reset[0]:.3f} cmd t={cmd:.3f} end t={end[0]:.3f}")
            wait_rest()
        finally:
            if helper and helper.poll() is None:
                try:
                    send("quit")
                    helper.wait(timeout=3)
                except Exception:
                    helper.kill()
            if rec:
                rec.stop()

    with rec.lock:
        poses = np.array(sorted(rec.poses))
        rotors = sorted(rec.rotors, key=lambda r: r[0])
        wrench = {i: sorted(rows) for i, rows in rec.wrench.items()}

    report = [f"# Differential thrust, geometry={args.label}, omega={args.omega}, delta={args.delta}",
              f"I_base={I_BASE.tolist()} I_rigid(with rotor point masses)={np.round(I_RIGID, 6).tolist()}"]

    # Equal-speed airborne hover phase: rotor positions and joint wrench.
    reset, cmd, end = marks["equal"]
    hover = (reset + 0.02, end)
    rp = np.array([r[1] for r in rotors if hover[0] <= r[0] <= hover[1]])
    if len(rp):
        dev = np.abs(rp[:, :, :2]) - ARM
        report.append(f"Rotor link positions during equal-speed airborne hover (n={len(rp)}): "
                      f"max | |x|,|y| - {ARM} | = {np.abs(dev).max():.6f} m; "
                      f"radius range {np.hypot(rp[:, :, 0], rp[:, :, 1]).min():.6f}-"
                      f"{np.hypot(rp[:, :, 0], rp[:, :, 1]).max():.6f} m")
        for i in range(4):
            report.append(f"  rotor_{i}: x {rp[:, i, 0].min():+.6f}..{rp[:, i, 0].max():+.6f}, "
                          f"y {rp[:, i, 1].min():+.6f}..{rp[:, i, 1].max():+.6f}")
    for i in range(4):
        s = acc.wrench_stats(wrench[i], *hover)
        if s:
            mean, std, peak, n = s
            report.append(f"  rotor_{i} wrench (hover, n={n}): F=({mean[0]:+.6f},{mean[1]:+.6f},{mean[2]:+.6f}) "
                          f"T=({mean[3]:+.6f},{mean[4]:+.6f},{mean[5]:+.6f}) "
                          f"peak|F|=({peak[0]:.6f},{peak[1]:.6f},{peak[2]:.6f}) peak|T|=({peak[3]:.6f},{peak[4]:.6f},{peak[5]:.6f})")
    hz = poses[(poses[:, 0] >= hover[0]) & (poses[:, 0] <= hover[1])]
    report.append(f"Equal-speed hover z range {hz[:, 3].min():.5f}-{hz[:, 3].max():.5f} m, "
                  f"max |x|,|y| {np.abs(hz[:, 1:3]).max():.6f} m")

    report.append("\npattern  axis   predicted_alpha(I_base)  predicted_alpha(I_rigid)  measured_alpha  ratio_meas/pred_rigid  "
                  "final_angle_deg  max_xy_drift_m  fit_rms_rad")
    for name in ("yaw", "roll", "pitch", "equal"):
        reset, cmd, end = marks[name]
        dF, tau = predicted(args.omega, args.delta, name)
        sel = poses[(poses[:, 0] >= cmd) & (poses[:, 0] <= cmd + args.window)]
        ang = np.array([euler(q) for q in sel[:, 4:8]])
        t = sel[:, 0] - cmd
        fit = t >= args.fit_start
        drift = np.hypot(sel[:, 1], sel[:, 2]).max()
        for axis, idx in (("roll", 0), ("pitch", 1), ("yaw", 2)):
            c = np.polyfit(t[fit], ang[fit, idx], 2)
            rms = np.sqrt(np.mean((np.polyval(c, t[fit]) - ang[fit, idx]) ** 2))
            meas = 2 * c[0]
            pb, pr = tau[idx] / I_BASE[idx], tau[idx] / I_RIGID[idx]
            ratio = meas / pr if abs(pr) > 1e-9 else float("nan")
            report.append(f"{name:7s}  {axis:5s}  {pb:+22.5f}  {pr:+23.5f}  {meas:+14.5f}  {ratio:21.4f}  "
                          f"{math.degrees(ang[-1, idx]):+15.4f}  {drift:14.6f}  {rms:.2e}")
        report.append(f"         dF per rotor = {np.round(dF, 7).tolist()} N; tau = {np.round(tau, 7).tolist()} N*m; "
                      f"fit window {args.fit_start:.2f}-{t[-1]:.3f} s (n={fit.sum()})")
    text = "\n".join(report)
    print(text)
    (out / f"differential_{args.label}.txt").write_text(text + "\n")
    np.savetxt(out / f"differential_{args.label}_pose.csv", poses, delimiter=",",
               header="sim_time_s,x,y,z,qx,qy,qz,qw", comments="", fmt="%.9f")
    with (out / f"differential_{args.label}_marks.txt").open("w") as f:
        for name, (reset, cmd, end) in marks.items():
            f.write(f"{name} reset={reset:.6f} cmd={cmd:.6f} end={end:.6f}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Differential thrust test failed: {error}", file=sys.stderr)
        sys.exit(1)
