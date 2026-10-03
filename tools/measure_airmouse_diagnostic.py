#!/usr/bin/env python3
"""Audit the AirMouse motor topic and capture a verified 5 s propulsion trace."""

import argparse
import csv
import json
import math
import os
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

WORLD = "airmouse_physics"
MODEL = "airmouse"
POSE_TOPIC = f"/world/{WORLD}/pose/info"
MOTOR_TOPIC = f"/{MODEL}/gazebo/command/motor_speed"
CONTROL_SERVICE = f"/world/{WORLD}/control"
SET_POSE_SERVICE = f"/world/{WORLD}/set_pose"
GROUND_Z = 0.04
GROUND_THRESHOLD = 0.06
RATE_HZ = 20.0
WINDOW_S = 5.0


def stamp_seconds(message, pose):
    stamp = message.get("header", {}).get("stamp") or pose.get("header", {}).get("stamp")
    if stamp is None:
        return None
    return float(stamp.get("sec", 0)) + float(stamp.get("nsec", 0)) * 1e-9


def quaternion(pose):
    q = pose.get("orientation", {})
    if not all(key in q for key in ("x", "y", "z", "w")):
        return None
    return tuple(float(q[key]) for key in ("x", "y", "z", "w"))


def vector_position(pose):
    p = pose.get("position", {})
    if not all(key in p for key in ("x", "y", "z")):
        return None
    return tuple(float(p[key]) for key in ("x", "y", "z"))


def parse_pose_message(message):
    """Return exact model pose and any scoped rotor-link poses in one Pose_V."""
    body = None
    rotors = {}
    for entry in message.get("pose", []):
        name = entry.get("name", "")
        position = vector_position(entry)
        orientation = quaternion(entry)
        if name == MODEL:
            if position is not None and orientation is not None:
                body = {
                    "time": stamp_seconds(message, entry),
                    "x": position[0], "y": position[1], "z": position[2],
                    "qx": orientation[0], "qy": orientation[1],
                    "qz": orientation[2], "qw": orientation[3],
                    "rotor_q": {}, "rotor_omega": {},
                }
        normalized = name.replace("/", "::")
        for index in range(4):
            short = f"rotor_{index}"
            if (normalized == f"{MODEL}::{short}" or
                    normalized == short or
                    normalized.endswith(f"::{MODEL}::{short}")):
                if orientation is not None:
                    rotors[index] = orientation
    if body is not None:
        body["rotor_q"] = rotors
    return body


def message_stream(process):
    decoder = json.JSONDecoder()
    buffer = ""
    fd = process.stdout.fileno()
    selector = selectors.DefaultSelector()
    selector.register(fd, selectors.EVENT_READ)
    while True:
        if not selector.select(timeout=0.2):
            yield None
            continue
        chunk = os.read(fd, 16384).decode("utf-8", errors="replace")
        if not chunk:
            break
        buffer += chunk
        while buffer.strip():
            buffer = buffer.lstrip()
            try:
                obj, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                if buffer.startswith(("{", "[")):
                    break
                line_end = buffer.find("\n")
                if line_end < 0:
                    break
                buffer = buffer[line_end + 1:]
                continue
            yield obj
            buffer = buffer[end:]


def parse_topic_info(output):
    """Parse gz topic -i publisher/subscriber sections; None means unparseable."""
    lines = output.splitlines()
    sections = {}
    current = None
    for line in lines:
        lower = line.lower()
        if "publisher" in lower and "subscriber" not in lower:
            current = "publishers"
            sections[current] = []
        elif "subscriber" in lower:
            current = "subscribers"
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    if "publishers" not in sections or "subscribers" not in sections:
        return None
    result = {}
    for section, lines_in_section in sections.items():
        entries = []
        for line in lines_in_section:
            candidate = re.sub(r"^\s*\*\s*", "", line).strip()
            if candidate and ("gz.msgs." in candidate or "://" in candidate):
                entries.append(candidate)
        # An empty publisher section is not reliable evidence of zero peers:
        # Gazebo may omit peer details even while discovery is transient.
        # Subscriber count remains the safety gate for this diagnostic.
        if section == "publishers" and not entries:
            output_text = output.lower()
            explicit_zero = ("no publisher" in output_text or
                             re.search(r"\b0\s+publishers?\b", output_text))
            result[section] = 0 if explicit_zero else None
        else:
            result[section] = len(entries)
        result[section + "_types"] = [re.search(r"\[([^]]+)\]", row).group(1)
                                      for row in entries if re.search(r"\[([^]]+)\]", row)]
    return result


def audit_topic(gz, timeout=3.0):
    try:
        result = subprocess.run([gz, "topic", "-i", "-t", MOTOR_TOPIC],
                                text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"Gazebo discovery unavailable: {error}"
    parsed = parse_topic_info(result.stdout + "\n" + result.stderr)
    if result.returncode != 0 or parsed is None:
        detail = (result.stderr or result.stdout).strip()
        return None, "Gazebo discovery unavailable" + (f": {detail}" if detail else "")
    return parsed, None


def compile_publisher(source, output):
    try:
        flags = subprocess.run(["pkg-config", "--cflags", "--libs",
                                "gz-transport13", "gz-msgs10"],
                               text=True, capture_output=True, check=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"could not query Gazebo C++ build flags: {error}") from error
    compiler = shutil.which("c++") or shutil.which("clang++")
    if not compiler:
        raise RuntimeError("a C++ compiler is required for one persistent Gazebo Transport publisher")
    command = [compiler, "-std=c++17", str(source), "-o", str(output)] + shlex.split(flags.stdout)
    result = subprocess.run(command, text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"publisher helper compilation failed:\n{result.stderr.strip()}")


def start_publisher(binary, speed):
    process = subprocess.Popen([str(binary), f"{speed:.9g}", f"{RATE_HZ:.9g}"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=None)
    # The initial four-subscriber audit is the sole discovery gate. Do not
    # issue a second gz topic query here: short discovery stalls are common.
    time.sleep(0.15)
    if process.poll() is not None:
        raise RuntimeError(f"persistent publisher exited during startup (code {process.returncode})")
    return process


def stop_publisher(process):
    if process is None:
        return
    if process.poll() is None:
        process.send_signal(signal.SIGUSR1)
        time.sleep(0.12)
        process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def service(gz, name, req_type, request, timeout=3000):
    result = subprocess.run(
        [gz, "service", "-s", name, "--reqtype", req_type,
         "--reptype", "gz.msgs.Boolean", "--timeout", str(timeout),
         "--req", request], text=True, capture_output=True, timeout=timeout / 1000 + 3)
    if result.returncode or not re.search(r"\bdata\s*:\s*true\b", result.stdout, re.IGNORECASE):
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Gazebo service {name} failed or returned false: {detail}")
    return result.stdout.strip()


def q_multiply(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw*bx + ax*bw + ay*bz - az*by,
            aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw,
            aw*bw - ax*bx - ay*by - az*bz)


def q_relative(body, rotor):
    return q_multiply((-body[0], -body[1], -body[2], body[3]), rotor)


def rotor_rates(previous, current, dt):
    rates = {}
    if dt <= 0:
        return rates
    for index in set(previous) & set(current):
        delta = q_multiply((-previous[index][0], -previous[index][1],
                            -previous[index][2], previous[index][3]), current[index])
        if delta[3] < 0:
            delta = tuple(-value for value in delta)
        vector_norm = math.sqrt(delta[0]**2 + delta[1]**2 + delta[2]**2)
        if vector_norm < 1e-12:
            rates[index] = 0.0
            continue
        angle = 2.0 * math.atan2(vector_norm, max(-1.0, min(1.0, delta[3])))
        rates[index] = math.copysign(angle, delta[2]) / dt
    return rates


def update_rotor_motion(previous_sample, sample, rate_records, alias_counts):
    if previous_sample is None or sample["time"] <= previous_sample["time"]:
        return
    body_prev = (previous_sample["qx"], previous_sample["qy"],
                 previous_sample["qz"], previous_sample["qw"])
    body_now = (sample["qx"], sample["qy"], sample["qz"], sample["qw"])
    prev = {i: q_relative(body_prev, q) for i, q in previous_sample["rotor_q"].items()}
    now = {i: q_relative(body_now, q) for i, q in sample["rotor_q"].items()}
    dt = sample["time"] - previous_sample["time"]
    rates = rotor_rates(prev, now, dt)
    sample["rotor_omega"] = rates
    for index, speed in rates.items():
        rate_records[index].append(speed)
        if abs(speed * dt) > 3.0:
            alias_counts[index] += 1


def csv_write(path, samples):
    fields = ["sim_time_s", "x_m", "y_m", "z_m", "qx", "qy", "qz", "qw"]
    fields += [f"rotor_{i}_pose_derived_rad_s" for i in range(4)]
    with Path(path).open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for sample in samples:
            row = {"sim_time_s": sample["time"], "x_m": sample["x"],
                   "y_m": sample["y"], "z_m": sample["z"],
                   "qx": sample["qx"], "qy": sample["qy"],
                   "qz": sample["qz"], "qw": sample["qw"]}
            for i in range(4):
                row[f"rotor_{i}_pose_derived_rad_s"] = sample["rotor_omega"].get(i, "")
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("motor_speed", nargs="?", type=float, default=586.8,
                        help="equal rotor speed in rad/s (default: 586.8)")
    parser.add_argument("--duration", type=float, default=WINDOW_S,
                        help="measurement window in simulation seconds (default: 5)")
    parser.add_argument("--csv", metavar="PATH",
                        help="CSV destination (default: timestamped file in current directory)")
    args = parser.parse_args()
    if args.motor_speed < 0 or args.duration <= 0:
        parser.error("motor speed must be nonnegative and duration must be positive")
    gz = shutil.which("gz")
    if not gz:
        parser.error("gz not found on PATH; add /opt/homebrew/bin in normal macOS Terminal")

    # Fail closed if local discovery cannot establish the command topic's peers.
    before, unavailable = audit_topic(gz)
    if unavailable:
        print(f"Motor topic audit: UNAVAILABLE — {unavailable}")
        print("No reset or motor command was sent; run this in normal macOS Terminal with Gazebo discovery available.")
        return 2
    publisher_count = before["publishers"]
    publisher_report = "unavailable" if publisher_count is None else str(publisher_count)
    print(f"Motor topic audit before test: publishers={publisher_report}, "
          f"subscribers={before['subscribers']}, types={before['subscribers_types']}")
    if before["subscribers"] != 4:
        print("Audit failed: the initial audit did not establish exactly four subscribers.")
        print("No reset or propulsion command was sent.")
        return 2
    if publisher_count is None:
        print("Publisher count unavailable from the initial topic audit; no competing-publisher conclusion is made.")
    elif publisher_count:
        print(f"Initial audit reports {publisher_count} publisher(s); competing publishers cannot be ruled out.")
    if before["subscribers_types"] and any(t != "gz.msgs.Actuators" for t in before["subscribers_types"]):
        print("Subscriber type details differ from gz.msgs.Actuators; proceeding based on the requested four-subscriber gate.")

    source = Path(__file__).with_name("airmouse_motor_publisher.cc")
    with tempfile.TemporaryDirectory(prefix="airmouse-diagnostic-") as temporary:
        binary = Path(temporary) / "airmouse_motor_publisher"
        compile_publisher(source, binary)
        echo = subprocess.Popen([gz, "topic", "-e", "-t", POSE_TOPIC, "--json-output"],
                                stdout=subprocess.PIPE, stderr=None, bufsize=0)
        publisher = None
        paused = False
        samples = []
        rate_records = {i: [] for i in range(4)}
        alias_counts = {i: 0 for i in range(4)}
        contact_index = None
        rotor_seen = set()
        previous = None
        try:
            print("Waiting for an exact-name AirMouse pose before resetting.", flush=True)
            deadline = time.monotonic() + 15
            first_pose = None
            for message in message_stream(echo):
                if message is None:
                    if time.monotonic() > deadline:
                        raise RuntimeError("no pose received; check the running world and pose topic")
                    continue
                first_pose = parse_pose_message(message)
                if first_pose is not None:
                    break
            if first_pose is None:
                raise RuntimeError("pose stream ended before AirMouse appeared")

            zero_process = start_publisher(binary, 0.0)
            # Pause, reset all world models (which resets physics state), then set the requested test pose.
            service(gz, CONTROL_SERVICE, "gz.msgs.WorldControl", "pause: true")
            paused = True
            service(gz, CONTROL_SERVICE, "gz.msgs.WorldControl", "reset: {model_only: true}")
            service(gz, SET_POSE_SERVICE, "gz.msgs.Pose",
                    'name: "airmouse", position: {x: 0, y: 0, z: 2}, orientation: {x: 0, y: 0, z: 0, w: 1}')

            # Verify the measured pose, while paused, before replacing the zero command.
            initial = None
            deadline = time.monotonic() + 10
            for message in message_stream(echo):
                if message is None:
                    if time.monotonic() > deadline:
                        raise RuntimeError("no pose confirmation after model reset and set_pose")
                    if zero_process.poll() is not None:
                        raise RuntimeError("zero-speed publisher exited during reset")
                    continue
                candidate = parse_pose_message(message)
                if candidate is None:
                    continue
                rotor_seen.update(candidate["rotor_q"])
                if (abs(candidate["z"] - 2.0) <= 0.01 and
                        abs(candidate["x"]) <= 0.01 and abs(candidate["y"]) <= 0.01 and
                        abs(candidate["qx"]) <= 0.01 and abs(candidate["qy"]) <= 0.01 and
                        abs(candidate["qz"]) <= 0.01 and abs(candidate["qw"] - 1.0) <= 0.01):
                    initial = candidate
                    break
            if initial is None:
                raise RuntimeError("AirMouse pose was not observed at the requested 2 m upright initial state")
            if initial["time"] is None:
                raise RuntimeError("initial pose has no Gazebo simulation timestamp")
            print(f"Reset verified from pose stream at t={initial['time']:.6f}s, "
                  f"(x,y,z)=({initial['x']:.4f},{initial['y']:.4f},{initial['z']:.4f})m, "
                  f"q=({initial['qx']:.4f},{initial['qy']:.4f},{initial['qz']:.4f},{initial['qw']:.4f})")
            print("Velocity reset requested with WorldControl model_only reset; Pose_V itself does not report velocity.")

            stop_publisher(zero_process)
            publisher = None
            publisher = start_publisher(binary, args.motor_speed)
            print("No second Gazebo topic discovery query was made; live publisher count after startup is unavailable.")
            print(f"Persistent publisher active at {RATE_HZ:g} Hz with "
                  f"[{args.motor_speed:g}] repeated for all four actuators.")
            print("Repeated publishing is a delivery diagnostic safeguard; it is not assumed to be a motor-model requirement.")

            samples.append(initial)
            previous = initial
            rotor_seen.update(initial["rotor_q"])
            start_time = initial["time"]
            service(gz, CONTROL_SERVICE, "gz.msgs.WorldControl", "pause: false")
            paused = False
            deadline = time.monotonic() + args.duration * 10.0 + 15.0
            for message in message_stream(echo):
                if message is None:
                    if time.monotonic() > deadline:
                        raise RuntimeError("simulation time did not advance to the requested measurement end")
                    if publisher.poll() is not None:
                        raise RuntimeError("persistent motor publisher exited during measurement")
                    continue
                sample = parse_pose_message(message)
                if sample is None:
                    continue
                if sample["time"] is None:
                    raise RuntimeError("AirMouse pose sample has no simulation timestamp")
                rotor_seen.update(sample["rotor_q"])
                update_rotor_motion(previous, sample, rate_records, alias_counts)
                previous = sample
                samples.append(sample)
                if contact_index is None and sample["z"] <= GROUND_THRESHOLD:
                    contact_index = len(samples) - 1
                if sample["time"] - start_time >= args.duration:
                    break
            else:
                raise RuntimeError("pose topic ended before measurement duration completed")
        finally:
            stop_publisher(publisher)
            if "zero_process" in locals() and zero_process is not None and zero_process.poll() is None:
                stop_publisher(zero_process)
            if paused:
                try:
                    service(gz, CONTROL_SERVICE, "gz.msgs.WorldControl", "pause: false")
                except Exception as error:
                    print(f"Could not resume simulation during cleanup: {error}", file=sys.stderr)
            echo.terminate()
            try:
                echo.wait(timeout=2)
            except subprocess.TimeoutExpired:
                echo.kill()
                echo.wait()

        if len(samples) < 2:
            raise RuntimeError("measurement finished with fewer than two exact-name pose samples")
        final = samples[-1]
        start_time = samples[0]["time"]
        end_time = final["time"]
        csv_path = args.csv or f"airmouse_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_write(csv_path, samples)

        print("\nMEASURED POSE TRACE")
        print(f"Samples: {len(samples)} exact-name AirMouse poses")
        print(f"Initial time: {start_time:.6f}s; final time: {end_time:.6f}s; "
              f"window: {end_time - start_time:.6f}s simulation time")
        print(f"Initial z: {samples[0]['z']:.6f}m; final z: {final['z']:.6f}m")
        if contact_index is not None:
            contact = samples[contact_index]
            print(f"Ground-contact threshold first reached: t={contact['time']:.6f}s, z={contact['z']:.6f}m "
                  f"(threshold {GROUND_THRESHOLD:.3f}m; nominal contact height {GROUND_Z:.2f}m).")
            airborne_last = samples[max(0, contact_index - 1)]
            airborne_dt = airborne_last["time"] - samples[0]["time"]
            if airborne_dt > 0:
                airborne_dz = airborne_last["z"] - samples[0]["z"]
                print(f"Airborne portion before threshold: {airborne_dt:.6f}s; "
                      f"measured z change {airborne_dz:+.6f}m; "
                      f"calculated mean airborne rate {airborne_dz / airborne_dt:+.6f}m/s.")
            else:
                print("Airborne portion before contact: too short to calculate a rate.")
            print("Full-window endpoint change includes ground contact; it is not reported as an airborne rate.")
        else:
            dt = end_time - start_time
            if dt > 0:
                dz = final["z"] - samples[0]["z"]
                print(f"No ground-contact threshold reached. Full observed interval was airborne: "
                      f"calculated mean z rate {dz / dt:+.6f}m/s.")

        if rotor_seen:
            print("\nMEASURED POSE-DERIVED ROTOR MOTION")
            for index in range(4):
                speeds = rate_records[index]
                if speeds:
                    print(f"rotor_{index}: {sum(speeds) / len(speeds):+.3f} rad/s mean over "
                          f"{len(speeds)} pose intervals; alias-suspect intervals={alias_counts[index]}")
                else:
                    print(f"rotor_{index}: link pose seen={index in rotor_seen}, angular motion unavailable")
        else:
            print("Rotor-link orientations were absent from observed Pose_V messages; rotor response is unverified.")
        print(f"Saved full pose trace to {csv_path}")
        print("Calculated values are derived from measured pose samples; no theoretical hover value is used.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Diagnostic failed: {error}", file=sys.stderr)
        sys.exit(1)
