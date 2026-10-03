#!/usr/bin/env python3
"""Reset AirMouse to an airborne start, then measure one motor-speed interval."""

import argparse
import csv
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from measure_airmouse import airframe_pose, messages_from_stream, publish_command


POSE_TOPIC = "/world/airmouse_physics/pose/info"
SET_POSE_SERVICE = "/world/airmouse_physics/set_pose"
DEFAULT_Z = 2.0
DEFAULT_DURATION = 5.0
START_Z_TOLERANCE = 0.05


def reset_pose(gz, pose, target_z):
    """Set only the experiment's initial condition through Gazebo's world service."""
    # Keep observed x/y, while beginning upright at the requested height.
    request = (
        f'name: "airmouse", position: {{x: {pose["x"]:.9g}, y: {pose["y"]:.9g}, z: {target_z:.9g}}}, '
        "orientation: {x: 0, y: 0, z: 0, w: 1}"
    )
    result = subprocess.run(
        [gz, "service", "-s", SET_POSE_SERVICE,
         "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
         "--timeout", "3000", "--req", request],
        text=True, capture_output=True, timeout=5,
    )
    if result.returncode:
        raise RuntimeError(f"Gazebo set_pose service failed: {result.stderr.strip() or result.stdout.strip()}")
    if not re.search(r"\bdata\s*:\s*true\b", result.stdout, re.IGNORECASE):
        raise RuntimeError(f"Gazebo did not confirm the pose reset: {result.stdout.strip()}")


def save_csv(path, samples):
    fields = ("time", "x", "y", "z", "qx", "qy", "qz", "qw")
    with Path(path).open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(samples)


def fmt_pose(label, sample):
    print(f"{label} x,y (m): {sample['x']:.6f}, {sample['y']:.6f}")
    print(f"{label} orientation (x,y,z,w): "
          f"{sample['qx']:.6f}, {sample['qy']:.6f}, {sample['qz']:.6f}, {sample['qw']:.6f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("motor_speed", type=float,
                        help="equal commanded rotor speed in rad/s, e.g. 580")
    parser.add_argument("--initial-z", type=float, default=DEFAULT_Z,
                        help="requested airborne start altitude in m (default: 2.0)")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION,
                        help="measurement interval in Gazebo simulation seconds (default: 5)")
    parser.add_argument("--csv", metavar="PATH",
                        help="save all exact-name pose samples to CSV")
    args = parser.parse_args()
    if args.motor_speed < 0 or args.initial_z <= 0 or args.duration <= 0:
        parser.error("motor speed must be nonnegative; initial-z and duration must be positive")
    gz = shutil.which("gz")
    if not gz:
        parser.error("gz was not found on PATH; include /opt/homebrew/bin in PATH")

    print(f"Subscribing to {POSE_TOPIC}; selecting only pose name exactly 'airmouse'.", flush=True)
    print(f"Setup action: Gazebo set_pose to z={args.initial_z:g} m, preserving x/y and setting upright orientation.", flush=True)
    print("Measurement begins at the first observed pose at the requested height, immediately before the motor command.", flush=True)
    echo = subprocess.Popen(
        [gz, "topic", "-e", "-t", POSE_TOPIC, "--json-output"],
        stdout=subprocess.PIPE, stderr=None, text=False, bufsize=0,
    )
    phase = "wait_first_pose"
    samples = []
    start_time = None
    wait_deadline = time.monotonic() + 15.0
    finish_deadline = None
    try:
        for message in messages_from_stream(echo):
            now = time.monotonic()
            if message is None:
                deadline = finish_deadline if phase == "measuring" else wait_deadline
                if now > deadline:
                    if phase == "measuring":
                        raise RuntimeError("simulation time stopped before the requested interval completed")
                    raise RuntimeError("Timed out waiting for a suitable AirMouse pose; check the running world")
                continue
            pose = airframe_pose(message)
            if pose is None:
                continue
            if pose["time"] is None:
                raise RuntimeError("pose message has no simulation timestamp")

            if phase == "wait_first_pose":
                # Clear any command left over from a prior manual trial before repositioning.
                publish_command(gz, [0.0] * 4)
                print("Setup action: sent zero speed to clear any prior motor command.", flush=True)
                reset_pose(gz, pose, args.initial_z)
                phase = "wait_reset_pose"
                wait_deadline = time.monotonic() + 10.0
                print("Gazebo confirmed the initial pose reset.", flush=True)
                continue

            if phase == "wait_reset_pose":
                if abs(pose["z"] - args.initial_z) > START_Z_TOLERANCE:
                    continue
                if abs(pose["qx"]) > 0.01 or abs(pose["qy"]) > 0.01 or abs(pose["qz"]) > 0.01 or abs(pose["qw"] - 1.0) > 0.01:
                    continue
                samples.append(pose)
                start_time = pose["time"]
                publish_command(gz, [args.motor_speed] * 4)
                phase = "measuring"
                finish_deadline = time.monotonic() + args.duration * 10.0 + 15.0
                print(f"Sent one equal motor command: [{args.motor_speed:g}, {args.motor_speed:g}, "
                      f"{args.motor_speed:g}, {args.motor_speed:g}] rad/s", flush=True)
                continue

            if phase == "measuring":
                samples.append(pose)
                if pose["time"] - start_time >= args.duration:
                    break
        else:
            raise RuntimeError("pose topic ended before the measurement interval completed")
    finally:
        echo.terminate()
        try:
            echo.wait(timeout=2)
        except subprocess.TimeoutExpired:
            echo.kill()
            echo.wait()

    if len(samples) < 2:
        raise RuntimeError("fewer than two exact-name poses were measured")
    initial, final = samples[0], samples[-1]
    elapsed = final["time"] - initial["time"]
    if elapsed <= 0:
        raise RuntimeError("simulation timestamp did not advance")
    delta_z = final["z"] - initial["z"]
    mean_rate = delta_z / elapsed
    if args.csv:
        save_csv(args.csv, samples)

    print("\nMEASURED DATA (from the Gazebo pose stream)")
    print(f"Motor command: [{args.motor_speed:g}, {args.motor_speed:g}, {args.motor_speed:g}, {args.motor_speed:g}] rad/s")
    print(f"Initial simulation time: {initial['time']:.6f} s")
    print(f"Final simulation time:   {final['time']:.6f} s")
    print(f"Initial z: {initial['z']:.6f} m")
    print(f"Final z:   {final['z']:.6f} m")
    print(f"\nCALCULATED FROM MEASURED DATA")
    print(f"Delta z (final - initial): {delta_z:+.6f} m")
    print(f"Mean vertical rate (delta z / elapsed time): {mean_rate:+.6f} m/s")
    print(f"Elapsed simulation time: {elapsed:.6f} s")
    print("\nMeasured pose endpoints:")
    fmt_pose("Initial", initial)
    fmt_pose("Final  ", final)
    print("No theoretical hover or thrust values are used in these results.")
    if args.csv:
        print(f"Saved {len(samples)} measured pose samples to {args.csv}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Airborne measurement failed: {error}", file=sys.stderr)
        sys.exit(1)
