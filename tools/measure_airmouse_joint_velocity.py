#!/usr/bin/env python3
"""Measure AirMouse rotor joint speeds in the running diagnostic Gazebo world."""

import argparse
import csv
import importlib.util
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

WORLD = "airmouse_physics"
MODEL = "airmouse"
POSE_TOPIC = f"/world/{WORLD}/pose/info"
CONTROL_SERVICE = f"/world/{WORLD}/control"
SET_POSE_SERVICE = f"/world/{WORLD}/set_pose"
MOTOR_TOPIC = f"/{MODEL}/gazebo/command/motor_speed"
COMMAND_RAD_S = 586.8
ROTOR_DIRECTIONS = {
    "rotor_0_joint": 1,
    "rotor_1_joint": -1,
    "rotor_2_joint": 1,
    "rotor_3_joint": -1,
}
JOINT_TOPIC = f"/{MODEL}/diagnostic/joint_state"


def load_existing_diagnostic():
    path = Path(__file__).with_name("measure_airmouse_diagnostic.py")
    spec = importlib.util.spec_from_file_location("airmouse_existing_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sim_time(message):
    stamp = message.get("header", {}).get("stamp")
    if stamp is None:
        return None
    return float(stamp.get("sec", 0)) + float(stamp.get("nsec", 0)) * 1e-9


def pose_z_at(message):
    pose = message.get("pose", [])
    for entry in pose:
        if entry.get("name") == MODEL:
            pos = entry.get("position", {})
            if all(k in pos for k in ("x", "y", "z")):
                return (sim_time(message) or 0.0, float(pos["z"]))
    return None


def parse_joint_sample(message):
    if message.get("name") != MODEL:
        return None
    stamp = sim_time(message)
    if stamp is None:
        return None
    velocities = {}
    for joint in message.get("joint", []):
        name = joint.get("name")
        if name not in ROTOR_DIRECTIONS:
            continue
        axis = joint.get("axis1", {})
        if "velocity" in axis:
            velocities[name] = float(axis["velocity"])
    return {"time": stamp, "velocities": velocities}


def call_service(gz, service_name, request, timeout_ms=5000):
    result = subprocess.run(
        [gz, "service", "-s", service_name, "--reqtype", "gz.msgs.WorldControl",
         "--reptype", "gz.msgs.Boolean", "--timeout", str(timeout_ms),
         "--req", request], text=True, capture_output=True,
        timeout=timeout_ms / 1000 + 3)
    if result.returncode or not re.search(r"\bdata\s*:\s*true\b", result.stdout, re.I):
        raise RuntimeError(f"Gazebo service {service_name} failed: " +
                           (result.stderr or result.stdout).strip())
    return result.stdout


def call_typed_service(gz, service_name, req_type, request, timeout_ms=5000):
    result = subprocess.run(
        [gz, "service", "-s", service_name, "--reqtype", req_type,
         "--reptype", "gz.msgs.Boolean", "--timeout", str(timeout_ms),
         "--req", request], text=True, capture_output=True,
        timeout=timeout_ms / 1000 + 3)
    if result.returncode or not re.search(r"\bdata\s*:\s*true\b", result.stdout, re.I):
        raise RuntimeError(f"Gazebo service {service_name} failed: " +
                           (result.stderr or result.stdout).strip())
    return result.stdout


def start_echo(gz, topic):
    return subprocess.Popen([gz, "topic", "-e", "-t", topic, "--json-output"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            bufsize=0, text=False)


def pump_messages(label, process, output_queue, diagnostic):
    try:
        for message in diagnostic.message_stream(process):
            if message is not None:
                output_queue.put((label, message))
        output_queue.put((label, None))
    except Exception as error:  # passed to main thread for orderly cleanup
        output_queue.put((label, error))


def altitude_at(time_s, poses):
    """Linearly interpolate measured body z between pose samples."""
    if not poses:
        return None
    before = None
    for sample in poses:
        if sample[0] == time_s:
            return sample[1]
        if sample[0] < time_s:
            before = sample
            continue
        if before is None:
            return sample[1]
        span = sample[0] - before[0]
        if span <= 0:
            return before[1]
        fraction = (time_s - before[0]) / span
        return before[1] + fraction * (sample[1] - before[1])
    return poses[-1][1]


def stop_process(process):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=1.5,
                        help="propulsion window in simulation seconds (default 1.5)")
    parser.add_argument("--csv", metavar="PATH",
                        help="CSV destination (default: timestamped file in current directory)")
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("duration must be positive")
    gz = shutil.which("gz")
    if not gz:
        parser.error("gz not found on PATH; add /opt/homebrew/bin in normal macOS Terminal")

    diag = load_existing_diagnostic()
    audit, unavailable = diag.audit_topic(gz)
    if unavailable or audit is None:
        raise RuntimeError("initial motor subscriber audit unavailable: " + str(unavailable))
    if audit["subscribers"] != 4:
        raise RuntimeError(f"expected four motor subscribers; initial audit found {audit['subscribers']}")
    print(f"Initial motor-topic audit: subscribers={audit['subscribers']} (four required).")
    print("This confirms subscriptions only; it does not establish rotor speed.")
    print("Joint entities:", ", ".join(ROTOR_DIRECTIONS))

    topic = JOINT_TOPIC
    print(f"Using the SDF-attached JointStatePublisher on {topic} (configured at 200 Hz).")
    print("No runtime system is attached by this tool.")

    source = Path(__file__).with_name("airmouse_motor_publisher.cc")
    output_queue = queue.Queue()
    pose_echo = joint_echo = None
    zero_publisher = motor_publisher = None
    samples = []
    poses = []
    sim_start = None
    deadline = time.monotonic() + 30
    paused = False
    stopped_near_ground = False
    csv_path = args.csv or f"airmouse_joint_velocity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with tempfile.TemporaryDirectory(prefix="airmouse-joint-observer-") as temporary:
        binary = Path(temporary) / "airmouse_motor_publisher"
        diag.compile_publisher(source, binary)
        try:
            pose_echo = start_echo(gz, POSE_TOPIC)
            joint_echo = start_echo(gz, topic)
            for label, process in (("pose", pose_echo), ("joint", joint_echo)):
                threading.Thread(target=pump_messages,
                                 args=(label, process, output_queue, diag),
                                 daemon=True).start()

            zero_publisher = diag.start_publisher(binary, 0.0)
            call_service(gz, CONTROL_SERVICE, "pause: true")
            paused = True
            call_service(gz, CONTROL_SERVICE, "reset: {model_only: true}")
            call_typed_service(gz, SET_POSE_SERVICE, "gz.msgs.Pose",
                               'name: "airmouse", position: {x: 0, y: 0, z: 2}, '
                               'orientation: {x: 0, y: 0, z: 0, w: 1}')

            initial = None
            while time.monotonic() < deadline:
                try:
                    label, message = output_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                if isinstance(message, Exception):
                    raise RuntimeError(f"{label} stream failed: {message}")
                if message is None:
                    continue
                if label == "pose":
                    candidate = diag.parse_pose_message(message)
                    if candidate:
                        zsample = pose_z_at(message)
                        if zsample:
                            poses.append(zsample)
                        if (abs(candidate["z"] - 2.0) <= 0.01 and
                                abs(candidate["x"]) <= 0.01 and abs(candidate["y"]) <= 0.01 and
                                abs(candidate["qx"]) <= 0.01 and abs(candidate["qy"]) <= 0.01 and
                                abs(candidate["qz"]) <= 0.01 and abs(candidate["qw"] - 1.0) <= 0.01 and
                                candidate["time"] is not None):
                            initial = candidate
                            break
            if initial is None:
                raise RuntimeError("did not observe AirMouse upright at z=2.0 m before propulsion")
            sim_start = initial["time"]
            print(f"Initial pose verified before propulsion: t={sim_start:.6f}s, "
                  f"x={initial['x']:.6f}, y={initial['y']:.6f}, z={initial['z']:.6f} m.")

            diag.stop_publisher(zero_publisher)
            zero_publisher = None
            motor_publisher = diag.start_publisher(binary, COMMAND_RAD_S)
            call_service(gz, CONTROL_SERVICE, "pause: false")
            paused = False
            end_sim_time = sim_start + args.duration
            wall_deadline = time.monotonic() + args.duration * 10 + 20
            seen_joint_names = set()
            while time.monotonic() < wall_deadline:
                try:
                    label, message = output_queue.get(timeout=0.2)
                except queue.Empty:
                    if motor_publisher.poll() is not None:
                        raise RuntimeError("motor command publisher exited during test")
                    continue
                if isinstance(message, Exception):
                    raise RuntimeError(f"{label} stream failed: {message}")
                if message is None:
                    continue
                if label == "pose":
                    zsample = pose_z_at(message)
                    if zsample:
                        poses.append(zsample)
                        if zsample[1] <= 0.25:
                            call_service(gz, CONTROL_SERVICE, "pause: true")
                            paused = True
                            stopped_near_ground = True
                            print(f"Paused early at z={zsample[1]:.4f} m to limit ground contact.")
                            break
                    continue
                sample = parse_joint_sample(message)
                if sample is None:
                    continue
                seen_joint_names.update(sample["velocities"])
                if sample["time"] < sim_start:
                    continue
                if sample["time"] > end_sim_time + 0.1:
                    break
                sample["z_m"] = None
                samples.append(sample)
                if sample["time"] >= end_sim_time and len(seen_joint_names) == 4:
                    # Let pose output catch up to the joint-state timestamps for altitude interpolation.
                    if poses and poses[-1][0] >= sample["time"]:
                        break

            diag.stop_publisher(motor_publisher)
            motor_publisher = None
            if paused and not stopped_near_ground:
                call_service(gz, CONTROL_SERVICE, "pause: false")
                paused = False
        finally:
            if motor_publisher is not None:
                diag.stop_publisher(motor_publisher)
            if zero_publisher is not None:
                diag.stop_publisher(zero_publisher)
            if paused and not stopped_near_ground:
                try:
                    call_service(gz, CONTROL_SERVICE, "pause: false")
                except Exception:
                    pass
            stop_process(pose_echo)
            stop_process(joint_echo)

    required = set(ROTOR_DIRECTIONS)
    if not samples or seen_joint_names != required:
        raise RuntimeError(f"joint-state stream did not include all four rotor joints; observed {sorted(seen_joint_names)}")

    for sample in samples:
        sample["z_m"] = altitude_at(sample["time"], poses)
    fields = ["sim_time_s", "command_input_rad_s"]
    fields += [f"{name}_expected_signed_rad_s" for name in ROTOR_DIRECTIONS]
    fields += [f"{name}_measured_rad_s" for name in ROTOR_DIRECTIONS]
    fields += ["airmouse_z_interpolated_m"]
    with Path(csv_path).open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for sample in samples:
            row = {"sim_time_s": f"{sample['time']:.9f}",
                   "command_input_rad_s": f"{COMMAND_RAD_S:.6f}",
                   "airmouse_z_interpolated_m": "" if sample["z_m"] is None else f"{sample['z_m']:.9f}"}
            for name, direction in ROTOR_DIRECTIONS.items():
                row[f"{name}_expected_signed_rad_s"] = f"{direction * COMMAND_RAD_S:.6f}"
                value = sample["velocities"].get(name)
                row[f"{name}_measured_rad_s"] = "" if value is None else f"{value:.9f}"
            writer.writerow(row)

    print("\nMEASURED JOINT VELOCITY RESULTS")
    print(f"Simulation interval: {samples[0]['time']:.6f}–{samples[-1]['time']:.6f} s "
          f"({samples[-1]['time'] - samples[0]['time']:.6f} s); samples={len(samples)}.")
    print(f"Command input for each actuator: {COMMAND_RAD_S:.3f} rad/s. "
          "Expected signed joint targets account for cw/ccw directions.")
    print("joint              measured final    mean |speed|   time to 95% target")
    final_magnitudes = []
    signs_match = True
    for name, direction in ROTOR_DIRECTIONS.items():
        vals = [(s["time"], s["velocities"][name]) for s in samples if name in s["velocities"]]
        target = direction * COMMAND_RAD_S
        final = vals[-1][1]
        mean_abs = sum(abs(value) for _, value in vals) / len(vals)
        final_magnitudes.append(abs(final))
        signs_match = signs_match and direction * final > 0
        reached = next((t - sim_start for t, value in vals
                        if direction * value >= 0.95 * COMMAND_RAD_S), None)
        reached_text = "not reached" if reached is None else f"{reached:.4f} s"
        print(f"{name:18s} {final:+12.3f} {mean_abs:14.3f}   {reached_text}")
        if abs(final - target) > 0.05 * COMMAND_RAD_S:
            print(f"  final signed error from expected target: {final - target:+.3f} rad/s")
    magnitude_mean = sum(final_magnitudes) / len(final_magnitudes)
    magnitude_spread = max(final_magnitudes) - min(final_magnitudes)
    similarly = magnitude_spread <= max(10.0, 0.05 * magnitude_mean)
    print(f"Rotor comparison: {'similar' if similarly else 'not similar'} by final-speed magnitudes "
          f"(range {min(final_magnitudes):.3f}–{max(final_magnitudes):.3f} rad/s); "
          f"expected rotation signs {'match' if signs_match else 'do not all match'}.")

    zvals = [s["z_m"] for s in samples if s["z_m"] is not None]
    if zvals:
        print(f"Altitude paired by interpolation from measured pose samples: "
              f"initial={zvals[0]:.6f} m, final={zvals[-1]:.6f} m, "
              f"range={min(zvals):.6f}–{max(zvals):.6f} m.")
    print(f"Full joint-speed trace saved to {csv_path}")
    if stopped_near_ground:
        print("The run ended early at the altitude safety threshold; it did not complete the requested duration.")
    print("Gazebo server warnings/errors are not captured by this client; check the Terminal running `gz sim`.")
    print("The JointStatePublisher is configured only in the diagnostic SDF and applies no forces.")
    print("This tool does not infer rotor speed from pose and does not calculate thrust.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Joint velocity diagnostic failed: {error}", file=sys.stderr)
        sys.exit(1)
