#!/usr/bin/env python3
"""Verify the multi-row depth-fallback gpu_lidar (tools/make_depth_lidar_diagnostic.py) against exact ray casts.

Boots simulation/experimental/depth_lidar_diagnostic.sdf (vehicle held at a fixed pose over a floor, one wall box),
records scans from /airmouse/depth_lidar, casts every beam analytically against the floor plane and the wall box
from the known sensor pose, and checks (a) geometry/ordering, (b) range error and (c) rate. Reports the
vertical-angle sign and the scan ordering that match. Also checks that /airmouse/depth_lidar/points publishes.
Never edits any SDF.
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SDF = ROOT / "simulation" / "experimental" / "depth_lidar_diagnostic.sdf"


def read_json_stream(path):
    text, dec, i, out = Path(path).read_text(), json.JSONDecoder(), 0, []
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            return out
        obj, i = dec.raw_decode(text, i)
        out.append(obj)


def cast(origin, dirs, wall, rmin, rmax):
    """Nearest hit of unit rays against the z=0 floor and an axis-aligned wall box (xmin,xmax,ymin,ymax,zmin,zmax)."""
    t = np.full(len(dirs), np.inf)
    with np.errstate(divide="ignore", invalid="ignore"):
        tf = -origin[2] / dirs[:, 2]
        t = np.where(tf > 0, tf, t)
        lo = (np.array([wall[0], wall[2], wall[4]]) - origin) / dirs
        hi = (np.array([wall[1], wall[3], wall[5]]) - origin) / dirs
    near = np.minimum(lo, hi).max(axis=1)
    far = np.maximum(lo, hi).min(axis=1)
    hit = (far >= near) & (far > 0)
    tw = np.where(hit, np.maximum(near, 0), np.inf)
    t = np.minimum(t, tw)
    return np.where((t >= rmin) & (t <= rmax), t, np.inf)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sdf", default=str(SDF))
    ap.add_argument("--scans", type=int, default=20)
    ap.add_argument("--logdir", default=str(ROOT / "logs" / "sim-step3-depth-lidar"))
    args = ap.parse_args()
    os.environ["GZ_IP"] = "127.0.0.1"
    os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ["PATH"]
    log = Path(args.logdir)
    log.mkdir(parents=True, exist_ok=True)
    meta = json.loads((ROOT / "simulation" / "worlds" / "wall.json").read_text())
    x0, y0, lx, ly = meta["walls_cx_cy_lx_ly"][0]
    wall = (x0 - lx / 2, x0 + lx / 2, y0 - ly / 2, y0 + ly / 2, 0.0, meta["wall_height"])
    ok = True
    if subprocess.run(["pgrep", "-f", "gz sim"], capture_output=True).returncode == 0:
        sys.exit("a gz sim process is already running; stop it first")
    server = subprocess.Popen(["gz", "sim", "-s", "-r", args.sdf], stdout=open(log / "gz_server.log", "w"),
                              stderr=subprocess.STDOUT, start_new_session=True)
    try:
        time.sleep(10)
        pose = subprocess.run(["gz", "topic", "-e", "-t", "/world/airmouse_physics/pose/info", "-n", "1", "--json-output"],
                              capture_output=True, text=True).stdout
        p = [q for q in json.loads(pose)["pose"] if q["name"] == "airmouse"][0]["position"]
        base = np.array([p.get("x", 0.0), p.get("y", 0.0), p.get("z", 0.0)])
        sdf_text = Path(args.sdf).read_text()
        import re
        mx = float(re.search(r'<sensor name="depth_lidar".*?<pose>([\d.\-]+)', sdf_text, flags=re.S).group(1))
        origin = base + np.array([mx, 0, 0])
        with open(log / "scans.json", "w") as f:
            t0 = time.time()
            subprocess.run(["gz", "topic", "-e", "-t", "/airmouse/depth_lidar", "-n", str(args.scans), "--json-output"],
                           stdout=f, stderr=subprocess.DEVNULL)
            dt = time.time() - t0
        scans = read_json_stream(log / "scans.json")
        pts = subprocess.run(["gz", "topic", "-e", "-t", "/airmouse/depth_lidar/points", "-n", "1"], capture_output=True,
                             text=True, timeout=30).stdout
    finally:
        os.killpg(server.pid, 15)
        server.wait(timeout=10)

    def check(name, cond, measured, expected):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}: measured {measured} | expected {expected}")

    s = scans[-1]
    hc, vc = int(s["count"]), int(s["verticalCount"])
    check("beam grid", (hc, vc) == (64, 16), f"{hc} x {vc}", "64 x 16")
    check("horizontal FOV", abs(math.degrees(s["angleMax"] - s["angleMin"]) - 60) < 0.01,
          f"{math.degrees(s['angleMax'] - s['angleMin']):.3f} deg", "60 deg")
    check("vertical FOV", abs(math.degrees(s["verticalAngleMax"] - s["verticalAngleMin"]) - 30) < 0.01,
          f"{math.degrees(s['verticalAngleMax'] - s['verticalAngleMin']):.3f} deg", "30 deg")
    az = np.linspace(s["angleMin"], s["angleMax"], hc)
    el = np.linspace(s["verticalAngleMin"], s["verticalAngleMax"], vc)
    rmin, rmax = float(s["rangeMin"]), float(s["rangeMax"])
    allr = np.array([[np.inf if isinstance(r, str) else r for r in sc["ranges"]] for sc in scans])
    mean_r = np.where(np.isfinite(allr), allr, np.nan)
    mean_r = np.nanmean(mean_r, axis=0)
    mean_r = np.where(np.isfinite(allr).all(axis=0), mean_r, np.inf)
    best = None
    for order in ("row-major (vertical outer)", "column-major (horizontal outer)"):
        for sign in (+1, -1):
            A, E = np.meshgrid(az, sign * el)            # shape (vc, hc)
            if order.startswith("column"):
                A, E = A.T, E.T
            d = np.stack([np.cos(E) * np.cos(A), np.cos(E) * np.sin(A), np.sin(E)], axis=-1).reshape(-1, 3)
            exp = cast(origin, d, wall, rmin, rmax)
            both = np.isfinite(exp) & np.isfinite(mean_r)
            err = np.abs(exp[both] - mean_r[both])
            mism = (np.isfinite(exp) != np.isfinite(mean_r)).sum()
            cand = (mism, np.median(err) if len(err) else np.inf, order, sign, exp, both)
            if best is None or cand[:2] < best[:2]:
                best = cand
    mism, med, order, sign, exp, both = best
    print(f"  best match: ordering {order}, elevation sign {'+' if sign > 0 else '-'} (positive scan angle = beam "
          f"{'up' if sign > 0 else 'down'}); sensor at ({origin[0]:.3f}, {origin[1]:.3f}, {origin[2]:.3f}) m")
    err = np.abs(exp[both] - mean_r[both])
    sigma_mean = 0.01 / math.sqrt(len(scans))
    check("beams with a return agree with ray cast (|err| <= 0.03 m + 4 sigma/sqrt(n))",
          (err <= 0.03 + 4 * sigma_mean).mean() >= 0.98, f"{(err <= 0.03 + 4 * sigma_mean).mean() * 100:.1f} % of {both.sum()} "
          f"beams, median {np.median(err) * 1000:.1f} mm, max {err.max() * 1000:.1f} mm", ">= 98 %")
    check("return / no-return agreement", mism <= 0.02 * hc * vc, f"{mism} of {hc * vc} beams differ", "<= 2 %")
    rate = (len(scans) - 1) / dt if dt > 0 else float("nan")
    check("message rate", 8.0 <= rate <= 11.0, f"{rate:.1f} Hz (wall clock, RTF-dependent)", "~10 Hz")
    check("point cloud topic publishes", "width" in pts and "height" in pts, pts.split("\n")[0:4], "PointCloudPacked message")
    print(f"OVERALL: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
