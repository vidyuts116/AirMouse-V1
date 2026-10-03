#!/usr/bin/env python3
"""Measure one commanded AirMouse thrust interval from Gazebo's pose topic."""

import argparse
import csv
import json
import os
import selectors
import shutil
import subprocess
import sys
import time
from pathlib import Path


POSE_TOPIC = "/world/airmouse_physics/pose/info"
MOTOR_TOPIC = "/airmouse/gazebo/command/motor_speed"


def sim_time(message, pose=None):
    stamp = message.get("header", {}).get("stamp")
    if not stamp and pose:
        stamp = pose.get("header", {}).get("stamp")
    if not stamp:
        return None
    return float(stamp.get("sec", 0)) + float(stamp.get("nsec", 0)) * 1e-9


def airframe_pose(message):
    """Return the exactly named model pose, or None if absent in this message."""
    for pose in message.get("pose", []):
        if pose.get("name") == "airmouse":
            position = pose.get("position", {})
            orientation = pose.get("orientation", {})
            if not all(axis in position for axis in ("x", "y", "z")):
                raise ValueError("airmouse pose has no complete position")
            if not all(axis in orientation for axis in ("x", "y", "z", "w")):
                raise ValueError("airmouse pose has no complete orientation")
            return {
                "time": sim_time(message, pose),
                "x": float(position["x"]),
                "y": float(position["y"]),
                "z": float(position["z"]),
                "qx": float(orientation["x"]),
                "qy": float(orientation["y"]),
                "qz": float(orientation["z"]),
                "qw": float(orientation["w"]),
            }
    return None


def messages_from_stream(process):
    """Yield JSON objects from gz topic's possibly pretty-printed JSON stream."""
    decoder = json.JSONDecoder()
    buffer = ""
    fd = process.stdout.fileno()
    selector = selectors.DefaultSelector()
    selector.register(fd, selectors.EVENT_READ)
    while True:
        if not selector.select(timeout=0.25):
            yield None
            continue
        chunk = os.read(fd, 8192).decode("utf-8", errors="replace")
        if not chunk:
            break
        buffer += chunk
        while buffer.strip():
            start = len(buffer) - len(buffer.lstrip())
            buffer = buffer[start:]
            try:
                value, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                # Discard a non-JSON diagnostic line, but keep incomplete JSON.
                if buffer.startswith(("[", "{")):
                    break
                newline = buffer.find("\n")
                if newline < 0:
                    break
                buffer = buffer[newline + 1:]
                continue
            yield value
            buffer = buffer[end:]


def publish_command(gz, values):
    vector = ", ".join(f"{value:.9g}" for value in values)
    command = [
        gz, "topic", "-t", MOTOR_TOPIC, "-m", "gz.msgs.Actuators",
        "-p", f"velocity: [{vector}]",
    ]
    result = subprocess.run(command, text=True, capture_output=True, timeout=5)
    if result.returncode:
        raise RuntimeError(f"motor command failed: {result.stderr.strip()}")


def write_csv(path, samples):
    columns = ("time", "x", "y", "z", "qx", "qy", "qz", "qw")
    with Path(path).open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("motor_speed", nargs="?", type=float, default=500.0,
                        help="commanded angular speed for each rotor in rad/s (default: 500)")
    parser.add_argument("--duration", type=float, default=2.0,
                        help="measurement interval in simulation seconds (default: 2)")
    parser.add_argument("--csv", metavar="PATH",
                        help="optionally save every matched pose sample as CSV")
    args = parser.parse_args()
    if args.duration <= 0 or args.motor_speed < 0:
        parser.error("duration must be positive and motor speed must be nonnegative")
    gz = shutil.which("gz")
    if not gz:
        parser.error("gz was not found on PATH; use normal macOS Terminal with Gazebo installed")

    print(f"Listening to {POSE_TOPIC}; waiting for the exact model name 'airmouse'.", flush=True)
    echo = subprocess.Popen(
        [gz, "topic", "-e", "-t", POSE_TOPIC, "--json-output"],
        stdout=subprocess.PIPE, stderr=None, text=False, bufsize=0,
    )
    samples = []
    command_sent = False
    start_time = None
    deadline = time.monotonic() + 15.0
    finish_deadline = None
    try:
        for message in messages_from_stream(echo):
            if message is None:
                current_deadline = finish_deadline if command_sent else deadline
                if time.monotonic() > current_deadline:
                    if command_sent:
                        raise RuntimeError("simulation time did not advance to the requested interval; is the world paused?")
                    raise RuntimeError("No exact 'airmouse' pose received within 15 seconds; check the running world and topic")
                continue
            pose = airframe_pose(message)
            if pose is None:
                continue
            if pose["time"] is None:
                raise RuntimeError("Pose_V has no simulation timestamp; cannot time a simulation-second interval")
            samples.append(pose)
            if not command_sent:
                start_time = pose["time"]
                publish_command(gz, [args.motor_speed] * 4)
                command_sent = True
                finish_deadline = time.monotonic() + args.duration * 10.0 + 15.0
                print(f"Sent one motor command: [{args.motor_speed:g}, {args.motor_speed:g}, "
                      f"{args.motor_speed:g}, {args.motor_speed:g}] rad/s", flush=True)
            elif pose["time"] - start_time >= args.duration:
                break
        else:
            raise RuntimeError("Pose topic ended before the measurement interval completed")
    finally:
        echo.terminate()
        try:
            echo.wait(timeout=2)
        except subprocess.TimeoutExpired:
            echo.kill()
            echo.wait()

    if len(samples) < 2:
        raise RuntimeError("Fewer than two pose samples received")
    first, last = samples[0], samples[-1]
    elapsed = last["time"] - first["time"]
    if elapsed <= 0:
        raise RuntimeError("Simulation timestamps did not advance")
    delta_z = last["z"] - first["z"]
    if args.csv:
        write_csv(args.csv, samples)

    print("\nMeasured samples (simulation time, z):")
    print("time (s)       z (m)")
    print(f"{first['time']:10.4f}  {first['z']: .6f}  initial")
    print(f"{last['time']:10.4f}  {last['z']: .6f}  final")
    print(f"\nMeasured initial z: {first['z']:.6f} m")
    print(f"Measured final z:   {last['z']:.6f} m")
    print(f"Measured delta z:   {delta_z:+.6f} m")
    print(f"Measured interval:  {elapsed:.4f} s (simulation time)")
    print(f"Measured mean vertical rate: {delta_z / elapsed:+.6f} m/s")
    print("Measured initial position (m): "
          f"x={first['x']:.6f}, y={first['y']:.6f}, z={first['z']:.6f}")
    print("Measured final position (m):   "
          f"x={last['x']:.6f}, y={last['y']:.6f}, z={last['z']:.6f}")
    print("Measured initial orientation (x,y,z,w): "
          f"{first['qx']:.6f}, {first['qy']:.6f}, {first['qz']:.6f}, {first['qw']:.6f}")
    print("Measured final orientation (x,y,z,w):   "
          f"{last['qx']:.6f}, {last['qy']:.6f}, {last['qz']:.6f}, {last['qw']:.6f}")
    if args.csv:
        print(f"Recorded {len(samples)} exact-name pose samples in {args.csv}")
    print("Calculated values: none; all reported position, interval, and rate values are from the pose stream.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Measurement failed: {error}", file=sys.stderr)
        sys.exit(1)
