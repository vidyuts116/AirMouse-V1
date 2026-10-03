#!/usr/bin/env python3
"""Generate AirMouse Phase 2 test worlds from the current baseline SDF.

Every world is the baseline world file (same vehicle, physics, sensors and
world name) plus one static `maze` model made of axis-aligned wall boxes, with
the vehicle spawn pose replaced. A JSON sidecar records the exact wall boxes,
the spawn pose and the baseline SHA-256 so LiDAR readings can be verified by
ray casting (tools/verify_world_lidar.py).

Worlds: empty, wall, corridor, junction, room, small_maze, nidar_maze.
The NIDAR maze is parameterised (default 15x15 cells of 2.0 m); the official
NIDAR arena dimensions have NOT been verified.
"""

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "simulation" / "airmouse_quadrotor.sdf"
OUT = ROOT / "simulation" / "worlds"
WALL_H = 2.0
WALL_T = 0.1
SPAWN_Z = 0.1


def box_x(x0, x1, y):
    """Wall running along x from x0 to x1 whose centre line is y (thickness WALL_T)."""
    return [(x0 + x1) / 2, y, abs(x1 - x0), WALL_T]


def box_y(y0, y1, x):
    return [x, (y0 + y1) / 2, WALL_T, abs(y1 - y0)]


def world_empty():
    return [], (0.0, 0.0, 0.0), {}


def world_wall():
    # Single wall, face at x = 3.0 m.
    return [[3.0 + WALL_T / 2, 0.0, WALL_T, 4.0]], (0.0, 0.0, 0.0), {"wall_face_x": 3.0}


def world_corridor():
    # 2 m wide (inner faces at y = +/-1.0), 20 m long, open ends.
    h = 1.0 + WALL_T / 2
    return [box_x(-4, 16, h), box_x(-4, 16, -h)], (0.0, 0.0, 0.0), {"inner_width": 2.0, "length": 20.0}


def world_junction():
    # 4-way junction of two 2 m wide corridors crossing at the origin; arms 6 m long, open ends.
    w, h, arm = 1.0, 1.0 + WALL_T / 2, 6.0
    walls = []
    for sy in (1, -1):
        walls += [box_x(-arm, -w, sy * h), box_x(w, arm, sy * h)]        # also closes the corner squares
    for sx in (1, -1):
        walls += [box_y(-arm, -w - WALL_T, sx * h), box_y(w + WALL_T, arm, sx * h)]
    return walls, (-3.0, 0.0, 0.0), {"inner_width": 2.0, "arm_length": arm}


def world_room():
    # Closed 6 m x 4 m room (inner faces), vehicle off-centre.
    ix, iy = 3.0, 2.0
    hx, hy = ix + WALL_T / 2, iy + WALL_T / 2
    walls = [box_x(-hx - WALL_T / 2, hx + WALL_T / 2, hy), box_x(-hx - WALL_T / 2, hx + WALL_T / 2, -hy),
             box_y(-iy, iy, hx), box_y(-iy, iy, -hx)]
    return walls, (1.0, 0.5, 0.0), {"inner_size": [2 * ix, 2 * iy]}


def perfect_maze(n, seed):
    """Randomised DFS perfect maze. Returns sets of open passages between adjacent cells."""
    rng = random.Random(seed)
    seen, stack, open_ = {(0, 0)}, [(0, 0)], set()
    while stack:
        c = stack[-1]
        nbrs = [(c[0] + dx, c[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        nbrs = [m for m in nbrs if 0 <= m[0] < n and 0 <= m[1] < n and m not in seen]
        if not nbrs:
            stack.pop()
            continue
        m = rng.choice(nbrs)
        open_.add(frozenset((c, m)))
        seen.add(m)
        stack.append(m)
    return open_


def check_perfect(n, open_):
    """A perfect maze is a spanning tree: n*n - 1 passages, every cell reachable. Returns the
    entrance-to-exit path length in cells (cell (0,0) to cell (n-1,n-1))."""
    assert len(open_) == n * n - 1, f"{len(open_)} passages, expected {n * n - 1}"
    adj = {}
    for pair in open_:
        a, b = tuple(pair)
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    dist, frontier = {(0, 0): 0}, [(0, 0)]
    while frontier:
        c = frontier.pop()
        for m in adj.get(c, []):
            if m not in dist:
                dist[m] = dist[c] + 1
                frontier.append(m)
    assert len(dist) == n * n, f"only {len(dist)} of {n * n} cells reachable"
    return dist[(n - 1, n - 1)] + 1


def maze_walls(n, cell, seed):
    """Walls on the cell grid (centred at the origin), collinear segments merged.
    Entrance: south side of cell (0, 0); exit: north side of cell (n-1, n-1)."""
    open_ = perfect_maze(n, seed)
    maze_walls.path_cells = check_perfect(n, open_)
    o = -n * cell / 2
    walls = []
    # Horizontal walls (running along x) on grid line j = 0..n.
    for j in range(n + 1):
        run = None
        for i in range(n + 1):
            if i < n:
                if j in (0, n):
                    wall = not ((j == 0 and i == 0) or (j == n and i == n - 1))
                else:
                    wall = frozenset(((i, j - 1), (i, j))) not in open_
            else:
                wall = False
            if wall and run is None:
                run = i
            if not wall and run is not None:
                walls.append(box_x(o + run * cell - WALL_T / 2, o + i * cell + WALL_T / 2, o + j * cell))
                run = None
    # Vertical walls (running along y) on grid line i = 0..n.
    for i in range(n + 1):
        run = None
        for j in range(n + 1):
            if j < n:
                wall = True if i in (0, n) else frozenset(((i - 1, j), (i, j))) not in open_
            else:
                wall = False
            if wall and run is None:
                run = j
            if not wall and run is not None:
                walls.append(box_y(o + run * cell - WALL_T / 2, o + j * cell + WALL_T / 2, o + i * cell))
                run = None
    start = (o + cell / 2, o + cell / 2, 0.0)
    return walls, start


def world_maze(n, cell, seed):
    walls, start = maze_walls(n, cell, seed)
    return walls, start, {"cells": n, "cell_size": cell, "seed": seed, "solution_path_cells": maze_walls.path_cells,
                          "entrance": "south side of cell (0,0)", "exit": f"north side of cell ({n - 1},{n - 1})"}


def render(name, walls, spawn, meta, baseline_text, baseline_sha):
    s = baseline_text
    s, k = re.subn(r'(<model name="airmouse"[^>]*>\s*<pose>)[^<]*(</pose>)',
                   rf"\g<1>{spawn[0]:.6g} {spawn[1]:.6g} {SPAWN_Z} 0 0 {spawn[2]:.6g}\g<2>", s, count=1)
    if k != 1:
        raise SystemExit("could not find the airmouse model pose in the baseline")
    if walls:
        parts = [f'    <!-- Phase 2 world "{name}": generated by tools/make_maze.py from baseline {baseline_sha[:8]}. -->\n'
                 '    <model name="maze"><static>true</static><link name="walls">']
        for k, (cx, cy, lx, ly) in enumerate(walls):
            geo = f"<geometry><box><size>{lx:.6g} {ly:.6g} {WALL_H}</size></box></geometry>"
            pose = f"<pose>{cx:.6g} {cy:.6g} {WALL_H / 2} 0 0 0</pose>"
            parts.append(f'<collision name="c{k}">{pose}{geo}</collision>'
                         f'<visual name="v{k}">{pose}{geo}<material><ambient>0.7 0.7 0.65 1</ambient>'
                         f'<diffuse>0.7 0.7 0.65 1</diffuse></material></visual>')
        parts.append("</link></model>\n")
        assert s.count("  </world>") == 1
        s = s.replace("  </world>", "".join(parts) + "  </world>")
    return s


WORLDS = ["empty", "wall", "corridor", "junction", "room", "small_maze", "nidar_maze"]


def build(name, args):
    if name == "small_maze":
        return world_maze(args.small_cells, args.cell_size, args.small_seed)
    if name == "nidar_maze":
        return world_maze(args.nidar_cells, args.cell_size, args.nidar_seed)
    return globals()[f"world_{name}"]()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("worlds", nargs="+", choices=WORLDS + ["all"])
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--cell-size", type=float, default=2.0, help="maze cell size in m (default 2.0)")
    parser.add_argument("--small-cells", type=int, default=5)
    parser.add_argument("--small-seed", type=int, default=7)
    parser.add_argument("--nidar-cells", type=int, default=15)
    parser.add_argument("--nidar-seed", type=int, default=2026)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    text = BASELINE.read_text()
    sha = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
    for name in (WORLDS if "all" in args.worlds else args.worlds):
        walls, spawn, meta = build(name, args)
        sdf = out / f"{name}.sdf"
        sdf.write_text(render(name, walls, spawn, meta, text, sha))
        info = {"world": name, "baseline_sha256": sha, "wall_height": WALL_H, "wall_thickness": WALL_T,
                "spawn": {"x": spawn[0], "y": spawn[1], "z": SPAWN_Z, "yaw": spawn[2]},
                "walls_cx_cy_lx_ly": walls, "params": meta}
        (out / f"{name}.json").write_text(json.dumps(info, indent=1) + "\n")
        extra = f"; perfect maze, entrance->exit path {meta['solution_path_cells']} cells" if "cells" in meta else ""
        print(f"{sdf.relative_to(ROOT)}: {len(walls)} wall boxes, spawn ({spawn[0]:g}, {spawn[1]:g}){extra}")


if __name__ == "__main__":
    main()
