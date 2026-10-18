#!/usr/bin/env python3
"""Clean AirMouse hover acceptance test with a pre-connected motor publisher.

Sequence: audit topic (0 publishers, 4 subscribers) -> start persistent helper
publishing 0 rad/s -> wait for `gz topic -i` to list the helper and 4 subscribers
and for the helper to report connections -> let the vehicle rest on the ground
-> command the speed -> wait 1 s sim for spin-up -> set_pose to z=2 m -> record
2 s sim. Also records per-rotor force/torque sensor readings when the world
provides them (diagnostic SDF only).
"""

import argparse
import csv
import importlib.util
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

WORLD = "airmouse_physics"
MODEL = "airmouse"
POSE_TOPIC = f"/world/{WORLD}/pose/info"
MOTOR_TOPIC = f"/{MODEL}/gazebo/command/motor_speed"
SET_POSE_SERVICE = f"/world/{WORLD}/set_pose"
FORCE_TOPICS = {i: f"/{MODEL}/diagnostic/force/rotor_{i}" for i in range(4)}
TARGET_AZ = 0.0019


def load_diagnostic():
    path = Path(__file__).with_name("measure_airmouse_diagnostic.py")
    spec = importlib.util.spec_from_file_location("airmouse_existing_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stamp(message):
    s = message.get("header", {}).get("stamp")
    return None if s is None else float(s.get("sec", 0)) + float(s.get("nsec", 0)) * 1e-9


def vec(d):
    return [float(d.get(k, 0.0)) for k in ("x", "y", "z")]


class Recorder:
    """Collects pose and wrench samples from `gz topic -e` streams."""

    def __init__(self, gz, diag, forces):
        self.lock = threading.Lock()
        self.poses = []                       # (t, x, y, z, qx, qy, qz, qw)
        self.wrench = {i: [] for i in range(4)}  # (t, fx, fy, fz, tx, ty, tz)
        self.procs = []
        topics = [("pose", POSE_TOPIC)] + ([(i, t) for i, t in FORCE_TOPICS.items()] if forces else [])
        for label, topic in topics:
            proc = subprocess.Popen([gz, "topic", "-e", "-t", topic, "--json-output"],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            self.procs.append(proc)
            threading.Thread(target=self.pump, args=(label, proc, diag), daemon=True).start()

    def pump(self, label, proc, diag):
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
            else:
                row = (t, *vec(message.get("force", {})), *vec(message.get("torque", {})))
                with self.lock:
                    self.wrench[label].append(row)

    def latest_pose(self):
        with self.lock:
            return self.poses[-1] if self.poses else None

    def stop(self):
        for proc in self.procs:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def wait_sim(rec, predicate, timeout, what):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pose = rec.latest_pose()
        if pose and predicate(pose):
            return pose
        time.sleep(0.02)
    raise RuntimeError(f"timed out waiting for {what}")


def wrench_stats(rows, t0, t1):
    sel = np.array([r[1:] for r in rows if t0 <= r[0] <= t1])
    if not len(sel):
        return None
    return sel.mean(axis=0), sel.std(axis=0), np.abs(sel).max(axis=0), len(sel)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--omega", type=float, default=586.8)
    parser.add_argument("--record", type=float, default=2.0, help="sim seconds recorded after reset")
    parser.add_argument("--spinup", type=float, default=1.0, help="sim seconds on ground after command")
    parser.add_argument("--no-forces", action="store_true", help="world has no force/torque sensors")
    parser.add_argument("--out", default=".", help="directory for CSV outputs")
    args = parser.parse_args()
    gz = shutil.which("gz")
    if not gz:
        parser.error("gz not found on PATH")
    diag = load_diagnostic()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    before, unavailable = diag.audit_topic(gz)
    if unavailable or before["subscribers"] != 4 or before["publishers"] != 0:
        raise RuntimeError(f"pre-test audit must show 0 publishers / 4 subscribers: {before or unavailable}")
    print(f"Pre-test audit: publishers={before['publishers']} subscribers={before['subscribers']}")

    helper = None
    rec = None
    events = []
    with __import__("tempfile").TemporaryDirectory(prefix="airmouse-hover-") as tmp:
        binary = Path(tmp) / "airmouse_hover_helper"
        diag.compile_publisher(Path(__file__).with_name("airmouse_hover_helper.cc"), binary)
        helper = subprocess.Popen([str(binary), "100"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  text=True, bufsize=1)
        lines = queue.Queue()
        threading.Thread(target=lambda: [lines.put(l.strip()) for l in helper.stdout], daemon=True).start()

        def send(cmd):
            helper.stdin.write(cmd + "\n")
            helper.stdin.flush()

        def expect(prefix, timeout):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                events.append(line)
                if line.startswith(prefix):
                    return line
            raise RuntimeError(f"helper did not report {prefix}")

        try:
            expect("READY", 10)
            t_start = time.monotonic()
            while True:
                info, err = diag.audit_topic(gz)
                send("status")
                connected = expect("STATUS", 3).endswith("connected=1")
                if info and info["publishers"] == 1 and info["subscribers"] == 4 and connected:
                    break
                if time.monotonic() - t_start > 30:
                    raise RuntimeError(f"publisher/subscriber connection not established: {info or err}")
                time.sleep(0.2)
            print(f"Connection gate passed after {time.monotonic() - t_start:.2f} s wall: "
                  f"publishers=1 subscribers=4 HasConnections=1 (publishing 0 rad/s)")

            rec = Recorder(gz, diag, not args.no_forces)
            first = wait_sim(rec, lambda p: True, 10, "first pose")
            # Resting on ground: z below 0.06 m and pose stream stable for 0.5 s sim.
            ground = wait_sim(rec, lambda p: p[3] < 0.06, 15, "vehicle on the ground")
            rest = wait_sim(rec, lambda p: p[0] >= ground[0] + 0.5, 10, "0.5 s at rest")
            t_rest0, t_rest1 = ground[0] + 0.2, rest[0]
            print(f"Vehicle at rest on ground: z={rest[3]:.5f} m at t={rest[0]:.3f} s")

            send(f"speed {args.omega:.9g}")
            cmd_line = expect("CMD", 3)
            first_nonzero = None
            if not args.no_forces:
                first_nonzero = expect("FIRST_NONZERO", 5)
            cmd_pose = rec.latest_pose()
            spun = wait_sim(rec, lambda p: p[0] >= cmd_pose[0] + args.spinup, 10, "spin-up interval")
            t_spun0, t_spun1 = spun[0] - 0.5, spun[0]
            print(f"Spun up on ground: z={spun[3]:.5f} m at t={spun[0]:.3f} s")

            diag.service(gz, SET_POSE_SERVICE, "gz.msgs.Pose",
                         'name: "airmouse", position: {x: 0, y: 0, z: 2}, '
                         'orientation: {x: 0, y: 0, z: 0, w: 1}')
            reset = wait_sim(rec, lambda p: p[0] > spun[0] and abs(p[3] - 2.0) < 0.01, 10, "reset to z=2")
            t_reset = reset[0]
            wait_sim(rec, lambda p: p[0] >= t_reset + args.record, 30, "recording window")
            send("speed 0")
        finally:
            if helper and helper.poll() is None:
                try:
                    send("quit")
                    helper.wait(timeout=3)
                except Exception:
                    helper.kill()
            if rec:
                rec.stop()

    # Analysis -------------------------------------------------------------
    with rec.lock:
        poses = np.array(sorted(rec.poses))
        wrench = {i: sorted(rows) for i, rows in rec.wrench.items()}
    win = poses[(poses[:, 0] >= t_reset) & (poses[:, 0] <= t_reset + args.record)]
    tt = win[:, 0] - t_reset
    coeff = np.polyfit(tt, win[:, 3], 2)
    az = 2 * coeff[0]
    zdev = np.abs(win[:, 3] - 2.0).max()
    tilt = np.degrees(2 * np.arcsin(np.clip(np.hypot(win[:, 4], win[:, 5]), 0, 1))).max()
    xy = np.hypot(win[:, 1], win[:, 2]).max()
    pass_az = abs(az - TARGET_AZ) < 0.05
    pass_z = zdev < 0.02

    print("\nHOVER ACCEPTANCE (sim window "
          f"{t_reset:.3f}-{win[-1, 0]:.3f} s, {len(win)} pose samples)")
    print(f"  fitted a_z = {az:+.5f} m/s^2   |a_z-{TARGET_AZ}| = {abs(az - TARGET_AZ):.5f} "
          f"< 0.05 -> {'PASS' if pass_az else 'FAIL'}")
    print(f"  fitted v0  = {coeff[1]:+.5f} m/s at reset")
    print(f"  max |z-2.0| = {zdev:.5f} m < 0.02 -> {'PASS' if pass_z else 'FAIL'}  "
          f"(z range {win[:, 3].min():.5f}-{win[:, 3].max():.5f})")
    print(f"  max tilt {tilt:.4f} deg, max horizontal drift {xy:.5f} m")
    print(f"  OVERALL: {'PASS' if pass_az and pass_z else 'FAIL'}")
    print(f"\nCommand line: {cmd_line}")
    if first_nonzero:
        print(f"Latency: {first_nonzero}")

    if not args.no_forces:
        phases = [("ground, motors stopped", t_rest0, t_rest1),
                  ("ground, spun up", t_spun0, t_spun1),
                  ("airborne, spun up", t_reset + 0.05, t_reset + args.record)]
        print("\nFORCE/TORQUE SENSORS (frame=child; mean over phase; N and N*m)")
        for name, a, b in phases:
            print(f"  [{name}] t={a:.3f}-{b:.3f}")
            for i in range(4):
                s = wrench_stats(wrench[i], a, b)
                if s is None:
                    print(f"    rotor_{i}: no samples")
                    continue
                mean, std, peak, n = s
                print(f"    rotor_{i}: F=({mean[0]:+.5f},{mean[1]:+.5f},{mean[2]:+.5f}) "
                      f"T=({mean[3]:+.5f},{mean[4]:+.5f},{mean[5]:+.5f}) "
                      f"std|F|=({std[0]:.2e},{std[1]:.2e},{std[2]:.2e}) "
                      f"peak|Fxy|=({peak[0]:.3f},{peak[1]:.3f}) n={n}")

    stem = f"hover_{args.omega:g}"
    with (out / f"{stem}_pose.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sim_time_s", "x_m", "y_m", "z_m", "qx", "qy", "qz", "qw", "phase"])
        for p in poses:
            phase = "recorded" if t_reset <= p[0] <= t_reset + args.record else ("pre_reset" if p[0] < t_reset else "post")
            w.writerow([f"{v:.9f}" for v in p] + [phase])
    if not args.no_forces:
        with (out / f"{stem}_wrench.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["rotor", "sim_time_s", "fx", "fy", "fz", "tx", "ty", "tz"])
            for i in range(4):
                for r in wrench[i]:
                    w.writerow([i] + [f"{v:.9g}" for v in r])
    with (out / f"{stem}_events.txt").open("w") as f:
        f.write(f"t_rest={t_rest0:.6f}-{t_rest1:.6f} cmd_pose_t={cmd_pose[0]:.6f} "
                f"t_spun={t_spun0:.6f}-{t_spun1:.6f} t_reset={t_reset:.6f}\n")
        f.write("\n".join(events) + "\n")
    print(f"\nSaved {stem}_pose.csv, {stem}_events.txt" + ("" if args.no_forces else f", {stem}_wrench.csv")
          + f" in {out}")
    return 0 if pass_az and pass_z else 3


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Hover acceptance failed to run: {error}", file=sys.stderr)
        sys.exit(1)
