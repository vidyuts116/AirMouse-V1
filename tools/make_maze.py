#!/usr/bin/env python3
"""Generate AirMouse Phase 2 test worlds from the current baseline SDF.

Every world is the baseline world file (same vehicle, physics, sensors and
world name) plus one static `maze` model made of axis-aligned wall boxes, with
the vehicle spawn pose replaced. A JSON sidecar records the exact wall boxes,
the spawn pose and the baseline SHA-256 so LiDAR readings can be verified by
ray casting (tools/verify_world_lidar.py).

Worlds: empty, wall, corridor, junction, room, small_maze, nidar_maze and
seeded NIDAR variants nidar_maze_s<seed> (unseen-environment testing).

NIDAR maze (all parameters are options): outer footprint 15 x 15 m measured
over the outer wall faces; 1.5 m cell pitch with 0.1 m walls (10 x 10 cells,
>= 1.0 m clear corridors); --rooms N open rooms of at least 2 x 2 m clear
carved into the grid; 2.44 m walls; a 0.61 x 0.61 m launch pad marked at the
entrance (vehicle spawns on it); up to 6 PROVISIONAL survivor placeholder
markers (static, visual-only, non-colliding) in rooms and dead ends; ground
plane enlarged if the maze plus margin exceeds it.
"""

import argparse
import hashlib
import json
import math
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


def adjacency(open_):
    adj = {}
    for pair in open_:
        a, b = tuple(pair)
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    return adj


def check_maze(n, open_, perfect):
    """Every cell reachable (and, for a perfect maze, exactly n*n - 1 passages). Returns the shortest
    entrance-to-exit path length in cells (cell (0,0) to cell (n-1,n-1))."""
    if perfect:
        assert len(open_) == n * n - 1, f"{len(open_)} passages, expected {n * n - 1}"
    adj = adjacency(open_)
    dist, frontier = {(0, 0): 0}, [(0, 0)]
    while frontier:                      # breadth-first: shortest path even when rooms add loops
        nxt = []
        for c in frontier:
            for m in adj.get(c, []):
                if m not in dist:
                    dist[m] = dist[c] + 1
                    nxt.append(m)
        frontier = nxt
    assert len(dist) == n * n, f"only {len(dist)} of {n * n} cells reachable"
    return dist[(n - 1, n - 1)] + 1


def grid_lines(n, cell, inset):
    """Wall centre-line positions 0..n. inset=True keeps the OUTER wall faces at +/- n*cell/2."""
    o = -n * cell / 2
    g = [o + k * cell for k in range(n + 1)]
    if inset:
        g[0] += WALL_T / 2
        g[-1] -= WALL_T / 2
    return g


def carve_rooms(n, cell, open_, rooms, room_size, rng, g):
    """Open k x k cell blocks (k chosen so the clear width >= room_size) away from the entrance/exit cells
    and at least one cell apart. Returns the room blocks as lists of cells."""
    k = 1
    while min(g[i + k] - g[i] for i in range(n - k + 1)) - WALL_T < room_size - 1e-9:
        k += 1
    blocks, tries = [], 0
    while len(blocks) < rooms:
        tries += 1
        if tries > 10000:
            raise SystemExit(f"could not place {rooms} rooms of {k}x{k} cells in a {n}x{n} grid")
        i, j = rng.randrange(0, n - k + 1), rng.randrange(0, n - k + 1)
        cells = [(i + a, j + b) for a in range(k) for b in range(k)]
        if (0, 0) in cells or (n - 1, n - 1) in cells:
            continue
        if any(abs(i - bi) < k + 1 and abs(j - bj) < k + 1 for bi, bj, _ in blocks):
            continue
        blocks.append((i, j, cells))
    for i, j, cells in blocks:
        for a in range(k):
            for b in range(k):
                if a + 1 < k:
                    open_.add(frozenset(((i + a, j + b), (i + a + 1, j + b))))
                if b + 1 < k:
                    open_.add(frozenset(((i + a, j + b), (i + a, j + b + 1))))
    return k, [cells for _, _, cells in blocks]


def maze_layout(n, cell, seed, inset=False, rooms=0, room_size=2.0, markers=0, marker_size=(0.4, 0.4)):
    """Walls (collinear segments merged), spawn, rooms and survivor markers.
    Entrance: south side of cell (0, 0); exit: north side of cell (n-1, n-1)."""
    open_ = perfect_maze(n, seed)
    rng = random.Random(f"{seed}-features")          # independent of the maze carving itself
    g = grid_lines(n, cell, inset)
    k, room_cells = carve_rooms(n, cell, open_, rooms, room_size, rng, g) if rooms else (0, [])
    path = check_maze(n, open_, perfect=not rooms)
    walls = []
    for j in range(n + 1):                            # walls along x on grid line j
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
                walls.append(box_x(g[run] - WALL_T / 2, g[i] + WALL_T / 2, g[j]))
                run = None
    for i in range(n + 1):                            # walls along y on grid line i
        run = None
        for j in range(n + 1):
            if j < n:
                wall = True if i in (0, n) else frozenset(((i - 1, j), (i, j))) not in open_
            else:
                wall = False
            if wall and run is None:
                run = j
            if not wall and run is not None:
                walls.append(box_y(g[run] - WALL_T / 2, g[j] + WALL_T / 2, g[i]))
                run = None
    centre = lambda c: ((g[c[0]] + g[c[0] + 1]) / 2, (g[c[1]] + g[c[1] + 1]) / 2)
    start = (*centre((0, 0)), 0.0)
    clear = [g[i + 1] - g[i] - WALL_T for i in range(n)]
    info = {"cells": n, "cell_size": cell, "seed": seed, "solution_path_cells": path,
            "entrance": "south side of cell (0,0)", "exit": f"north side of cell ({n - 1},{n - 1})"}
    if inset or rooms or markers:
        info.update({"footprint_outer_faces_m": round(g[-1] - g[0] + WALL_T, 6),
                     "corridor_clear_min_max_m": [round(min(clear), 6), round(max(clear), 6)]})
    room_info, marker_boxes = [], []
    if rooms:
        for cells in room_cells:
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            x0, x1, y0, y1 = g[min(xs)], g[max(xs) + 1], g[min(ys)], g[max(ys) + 1]
            room_info.append({"cells": [list(c) for c in cells], "centre": [(x0 + x1) / 2, (y0 + y1) / 2],
                              "clear_m": [round(x1 - x0 - WALL_T, 6), round(y1 - y0 - WALL_T, 6)]})
        info.update({"rooms": room_info, "room_block_cells": k, "room_size_min_m": room_size})
    if markers:
        adj = adjacency(open_)
        in_room = {c for cells in room_cells for c in cells}
        dead = [c for c in sorted(adj) if len(adj[c]) == 1 and c not in in_room and c not in ((0, 0), (n - 1, n - 1))]
        rng.shuffle(dead)
        spots = [(tuple(r["centre"]), "room") for r in room_info] + [(centre(c), f"dead end {c}") for c in dead]
        for (cx, cy), where in spots[:markers]:
            marker_boxes.append({"cx_cy_lx_ly": [cx, cy, marker_size[0], marker_size[1]], "where": where})
        info["survivor_markers"] = marker_boxes
    return walls, start, info


def world_maze(n, cell, seed, **features):
    walls, start, info = maze_layout(n, cell, seed, **features)
    return walls, start, info


def render(name, walls, spawn, meta, baseline_text, baseline_sha, wall_h=WALL_H, pad=None, markers=(),
           marker_h=0.5, ground_size=None):
    s = baseline_text
    s, k = re.subn(r'(<model name="airmouse"[^>]*>\s*<pose>)[^<]*(</pose>)',
                   rf"\g<1>{spawn[0]:.6g} {spawn[1]:.6g} {SPAWN_Z} 0 0 {spawn[2]:.6g}\g<2>", s, count=1)
    if k != 1:
        raise SystemExit("could not find the airmouse model pose in the baseline")
    if ground_size:
        gm = re.search(r'<model name="ground_plane">.*?</model>', s, flags=re.S)
        new, k = re.subn(r"<size>[^<]*</size>", f"<size>{ground_size:g} {ground_size:g}</size>", gm.group(0))
        assert k == 2, "ground plane collision + visual sizes expected"
        s = s[:gm.start()] + new + s[gm.end():]
    if walls:
        parts = [f'    <!-- Phase 2 world "{name}": generated by tools/make_maze.py from baseline {baseline_sha[:8]}. -->\n'
                 '    <model name="maze"><static>true</static><link name="walls">']
        for k, (cx, cy, lx, ly) in enumerate(walls):
            geo = f"<geometry><box><size>{lx:.6g} {ly:.6g} {wall_h}</size></box></geometry>"
            pose = f"<pose>{cx:.6g} {cy:.6g} {wall_h / 2} 0 0 0</pose>"
            parts.append(f'<collision name="c{k}">{pose}{geo}</collision>'
                         f'<visual name="v{k}">{pose}{geo}<material><ambient>0.7 0.7 0.65 1</ambient>'
                         f'<diffuse>0.7 0.7 0.65 1</diffuse></material></visual>')
        parts.append("</link></model>\n")
        if pad:
            px, py, size = pad
            parts.append('    <!-- Launch pad marker (visual only, 5 mm thick, below the LiDAR plane). -->\n'
                         f'    <model name="launch_pad"><static>true</static><pose>{px:.6g} {py:.6g} 0.0025 0 0 0</pose>'
                         f'<link name="pad"><visual name="v"><geometry><box><size>{size:g} {size:g} 0.005</size></box>'
                         '</geometry><material><ambient>1 0.55 0 1</ambient><diffuse>1 0.55 0 1</diffuse></material>'
                         '</visual></link></model>\n')
        for k, m in enumerate(markers):
            cx, cy, lx, ly = m["cx_cy_lx_ly"]
            parts.append(f'    <!-- PROVISIONAL survivor placeholder {k} ({m["where"]}): static, visual only, '
                         'non-colliding; visible to cameras and LiDAR. -->\n'
                         f'    <model name="survivor_{k}_PROVISIONAL"><static>true</static>'
                         f'<pose>{cx:.6g} {cy:.6g} {marker_h / 2:g} 0 0 0</pose><link name="marker"><visual name="v">'
                         f'<geometry><box><size>{lx:g} {ly:g} {marker_h:g}</size></box></geometry><material>'
                         '<ambient>0.9 0.1 0.1 1</ambient><diffuse>0.9 0.1 0.1 1</diffuse></material></visual>'
                         '</link></model>\n')
        assert s.count("  </world>") == 1
        s = s.replace("  </world>", "".join(parts) + "  </world>")
    return s


WORLDS = ["empty", "wall", "corridor", "junction", "room", "small_maze", "nidar_maze"]


def nidar_features(args):
    n = round(args.nidar_footprint / args.nidar_cell_size)
    if abs(n * args.nidar_cell_size - args.nidar_footprint) > 1e-9:
        raise SystemExit("--nidar-footprint must be a whole number of --nidar-cell-size cells")
    if not 0 <= args.survivors <= 6:
        raise SystemExit("--survivors must be 0..6")
    return n, {"inset": True, "rooms": args.rooms, "room_size": args.room_size, "markers": args.survivors}


def build(name, args):
    if name == "small_maze":
        return world_maze(args.small_cells, args.cell_size, args.small_seed)
    if name == "nidar_maze" or re.fullmatch(r"nidar_maze_s\d+", name):
        seed = args.nidar_seed if name == "nidar_maze" else int(name.rsplit("_s", 1)[1])
        n, feat = nidar_features(args)
        return world_maze(n, args.nidar_cell_size, seed, **feat)
    return globals()[f"world_{name}"]()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("worlds", nargs="+", help=f"{', '.join(WORLDS)}, nidar_maze_s<seed>, or all")
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--cell-size", type=float, default=2.0, help="small_maze cell size in m (default 2.0)")
    parser.add_argument("--small-cells", type=int, default=5)
    parser.add_argument("--small-seed", type=int, default=7)
    g = parser.add_argument_group("NIDAR maze")
    g.add_argument("--nidar-footprint", type=float, default=15.0, help="outer footprint over wall faces, m (15)")
    g.add_argument("--nidar-cell-size", type=float, default=1.5, help="cell pitch, m (1.5 -> 10 x 10 cells)")
    g.add_argument("--nidar-seed", type=int, default=2026, help="seed for nidar_maze (variants use _s<seed>)")
    g.add_argument("--nidar-wall-height", type=float, default=2.44, help="wall height, m (2.44 = 8 ft)")
    g.add_argument("--rooms", type=int, default=3, help="open rooms carved into the grid (2-4 per spec)")
    g.add_argument("--room-size", type=float, default=2.0, help="minimum clear room size, m (2.0)")
    g.add_argument("--pad-size", type=float, default=0.61, help="launch pad side, m (0.61 = 2 ft)")
    g.add_argument("--survivors", type=int, default=6, help="PROVISIONAL survivor markers, 0-6")
    g.add_argument("--ground-margin", type=float, default=1.0,
                   help="ground plane must cover the footprint plus this margin on each side, m")
    g.add_argument("--variants", type=int, default=0, help="also generate nidar_maze_s1..sN")
    args = parser.parse_args()
    names = WORLDS if "all" in args.worlds else list(args.worlds)
    names += [f"nidar_maze_s{k}" for k in range(1, args.variants + 1) if f"nidar_maze_s{k}" not in names]
    for name in names:
        if name not in WORLDS and not re.fullmatch(r"nidar_maze_s\d+", name):
            parser.error(f"unknown world {name}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    text = BASELINE.read_text()
    sha = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
    base_ground = float(re.search(r'<model name="ground_plane">.*?<size>([\d.]+)', text, flags=re.S).group(1))
    for name in names:
        walls, spawn, meta = build(name, args)
        nidar = name.startswith("nidar_maze")
        extras, info_extra = {}, {}
        if nidar:
            need = args.nidar_footprint + 2 * args.ground_margin
            ground = need if need > base_ground else None
            markers = meta.get("survivor_markers", [])
            extras = {"wall_h": args.nidar_wall_height, "pad": (spawn[0], spawn[1], args.pad_size),
                      "markers": markers, "ground_size": ground}
            info_extra = {"launch_pad": {"x": spawn[0], "y": spawn[1], "size_m": args.pad_size, "visual_only": True},
                          "markers_cx_cy_lx_ly": [m["cx_cy_lx_ly"] for m in markers], "marker_height": 0.5,
                          "markers_status": "PROVISIONAL placeholders: static, visual-only (non-colliding)",
                          "ground_plane_size_m": ground or base_ground,
                          "ground_plane_enlarged": ground is not None}
        sdf = out / f"{name}.sdf"
        sdf.write_text(render(name, walls, spawn, meta, text, sha, **extras))
        info = {"world": name, "baseline_sha256": sha,
                "wall_height": args.nidar_wall_height if nidar else WALL_H, "wall_thickness": WALL_T,
                "spawn": {"x": spawn[0], "y": spawn[1], "z": SPAWN_Z, "yaw": spawn[2]},
                "walls_cx_cy_lx_ly": walls, "params": meta, **info_extra}
        (out / f"{name}.json").write_text(json.dumps(info, indent=1) + "\n")
        extra = ""
        if "cells" in meta:
            kind = "maze with rooms" if meta.get("rooms") else "perfect maze"
            extra = f"; {kind}, entrance->exit path {meta['solution_path_cells']} cells"
        if nidar:
            extra += (f"; footprint {meta['footprint_outer_faces_m']} m, corridors "
                      f"{meta['corridor_clear_min_max_m'][0]}-{meta['corridor_clear_min_max_m'][1]} m clear, "
                      f"{len(meta.get('rooms', []))} rooms, {len(info_extra['markers_cx_cy_lx_ly'])} markers, "
                      f"ground {info_extra['ground_plane_size_m']:g} m")
        print(f"{sdf.relative_to(ROOT)}: {len(walls)} wall boxes, spawn ({spawn[0]:g}, {spawn[1]:g}){extra}")


if __name__ == "__main__":
    main()
