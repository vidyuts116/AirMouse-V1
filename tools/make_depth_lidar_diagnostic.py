#!/usr/bin/env python3
"""Depth-camera fallback: a multi-row gpu_lidar on a DIAGNOSTIC copy of a world (baseline is never edited).

The baseline depth_camera crashes gz sim on Ogre2/Metal (KNOWN ISSUE). This writes
simulation/experimental/depth_lidar_diagnostic.sdf = a Phase 2 world (default `wall`) with an extra
`depth_lidar` gpu_lidar on base_link, mounted like the RGB camera (x +0.12 m, facing +x):
  64 x 16 beams, 60 deg x 30 deg (azimuth +/-30, elevation +/-15), range 0.1-12 m, sigma 0.01 m, 10 Hz,
  topic /airmouse/depth_lidar (gz.msgs.LaserScan, row-major) and /airmouse/depth_lidar/points (PointCloudPacked).
The vehicle is held fixed at --height m by a fixed joint (diagnostic only, never fly it), so the lower rows
hit the floor and the upper rows hit the wall. Verify with tools/verify_depth_lidar.py.
"""

import argparse
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "simulation" / "experimental" / "depth_lidar_diagnostic.sdf"


def sensor_xml(h, v, hfov, vfov, rmin, rmax, sigma, rate, x):
    a, e = math.radians(hfov) / 2, math.radians(vfov) / 2
    return (f'        <sensor name="depth_lidar" type="gpu_lidar"><pose>{x:g} 0 0 0 0 0</pose><always_on>true</always_on>'
            f"<update_rate>{rate:g}</update_rate><topic>/airmouse/depth_lidar</topic><lidar><scan>"
            f"<horizontal><samples>{h}</samples><resolution>1</resolution><min_angle>{-a:.8f}</min_angle>"
            f"<max_angle>{a:.8f}</max_angle></horizontal>"
            f"<vertical><samples>{v}</samples><resolution>1</resolution><min_angle>{-e:.8f}</min_angle>"
            f"<max_angle>{e:.8f}</max_angle></vertical></scan>"
            f"<range><min>{rmin:g}</min><max>{rmax:g}</max><resolution>0.01</resolution></range>"
            f"<noise><type>gaussian</type><mean>0</mean><stddev>{sigma:g}</stddev></noise></lidar></sensor>\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("world", nargs="?", default=str(ROOT / "simulation" / "worlds" / "wall.sdf"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--samples", default="64x16", help="HxV beams (64x16)")
    ap.add_argument("--fov", default="60x30", help="horizontal x vertical field of view, deg (60x30)")
    ap.add_argument("--range", default="0.1,12", help="min,max range, m")
    ap.add_argument("--sigma", type=float, default=0.01)
    ap.add_argument("--rate", type=float, default=10.0)
    ap.add_argument("--mount-x", type=float, default=0.12, help="forward offset from base_link, m (camera: 0.12)")
    ap.add_argument("--height", type=float, default=1.0, help="fixed hold height, m")
    args = ap.parse_args()
    h, v = (int(t) for t in args.samples.split("x"))
    hf, vf = (float(t) for t in args.fov.split("x"))
    rmin, rmax = (float(t) for t in args.range.split(","))
    src = Path(args.world).resolve()
    text = src.read_text()
    text, k = re.subn(r'(<model name="airmouse"[^>]*>\s*<pose>)([^<]*)(</pose>)',
                      lambda m: m.group(1) + " ".join(m.group(2).split()[:2]) + f" {args.height:g} 0 0 0" + m.group(3),
                      text, count=1)
    assert k == 1, "airmouse model pose not found"
    i = text.index('<link name="base_link">')
    j = text.index("      </link>", i)
    text = (text[:j] + "        <!-- DIAGNOSTIC (tools/make_depth_lidar_diagnostic.py): depth-camera fallback. -->\n"
            + sensor_xml(h, v, hf, vf, rmin, rmax, args.sigma, args.rate, args.mount_x) + text[j:])
    end = text.index("    </model>", text.index('<model name="airmouse"'))
    text = (text[:end] + "      <!-- DIAGNOSTIC ONLY: vehicle held fixed so floor and wall are both in view. -->\n"
            '      <joint name="depth_check_hold" type="fixed"><parent>world</parent><child>base_link</child></joint>\n'
            + text[end:])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: {h}x{v} beams, {hf:g}x{vf:g} deg, "
          f"{rmin:g}-{rmax:g} m, held at {args.height:g} m, from {src.name}")


if __name__ == "__main__":
    main()
