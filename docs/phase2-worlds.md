# AirMouse Phase 2: test worlds and LiDAR verification (2026-10-03)

**Result: all 12 worlds PASS (OBSERVED).** That is the 7 Phase 2 worlds plus 5 seeded NIDAR variants. Consolidated run: `logs/phase2-2026-10-03/run_184532.log`.

## How the worlds are built

`tools/make_maze.py <world …|all> [--variants N]` writes `simulation/worlds/<world>.sdf` and a `<world>.json` sidecar.

- **Source:** each world is the **current baseline** `simulation/airmouse_quadrotor.sdf`, SHA-256 `21626e644770873ed59aa6dce6b5ce2f47b11b7ab9e45b5fa1e4f764d3fea88f`. The vehicle, physics, sensors and world name `airmouse_physics` are unchanged.
- **What is added:** static geometry and a new vehicle spawn pose (z = 0.1 m). Physics parameters changed: none.
- **Sidecar:** records the exact wall boxes, markers, launch pad, spawn pose, ground-plane size and the baseline hash.
- **Regeneration:** run `make_maze.py all` after any baseline change. The verifier FAILs on worlds built from an older baseline.
- **Maze generation:** seeded randomised depth-first search builds the maze, and collinear wall segments are merged. Room and marker placement use a separate seeded generator, so they never change the underlying maze. The generator self-checks:
  - a maze without rooms is *perfect*, with N²−1 passages
  - every cell is reachable
  - it reports the shortest entrance-to-exit path

  The entrance is on the south side of cell (0, 0) and the exit on the north side of cell (N−1, N−1).

### NIDAR maze

These are the spec values from the request. Each is a `make_maze.py` option, and `nidar_maze` uses `--nidar-seed 2026`.

| Item | Value | Option |
|---|---|---|
| Outer footprint, over the outer wall faces | 15.0 × 15.0 m | `--nidar-footprint 15` |
| Cell pitch / wall thickness | 1.5 m / 0.1 m, so **10 × 10 cells** | `--nidar-cell-size 1.5` |
| Corridor clear width | interior 1.40 m, outer ring 1.35 m (≥ 1.0 m) | derived |
| Open rooms | 3 (spec 2–4), each ≥ 2 × 2 m clear | `--rooms N`, `--room-size 2.0` |
| Wall height | 2.44 m (8 ft) | `--nidar-wall-height 2.44` |
| Launch pad | 0.61 × 0.61 m (2 ft), 5 mm thick, visual only, centred in the entrance cell; vehicle spawns on it | `--pad-size 0.61` |
| Survivor markers | 6 (spec ≤ 6), each 0.4 × 0.4 × 0.5 m, static, **visual only (non-colliding), PROVISIONAL**; first in the rooms, then in random dead ends | `--survivors N` |
| Ground plane | enlarged only if the footprint plus margin exceeds the baseline plane | `--ground-margin 1.0` |
| Seed | 2026; variants `nidar_maze_s1…s5` use seeds 1–5 | `--nidar-seed`, `--variants 5` |

**How the spec was interpreted (INFERRED, please confirm):**

- **15 m footprint:** taken over the outer wall faces. The outer walls are therefore inset by half their thickness, which makes the outer ring of cells 1.35 m clear instead of 1.40 m.
- **2 × 2 m rooms:** a 2 × 2 m room does not fit the 1.5 m grid. Each room is the smallest cell block with at least 2 m clear, which is 2 × 2 cells, giving **2.85–2.90 m clear**. Rooms never include the entrance or exit cell, and are at least one cell apart. Carving rooms opens internal walls, so the NIDAR mazes contain loops.
- **Ground plane:** the 15 m maze plus 1 m margin each side needs 17 m. The baseline plane is already 20 × 20 m, so **no enlargement was needed**, and the generated files keep 20 m.
- **Survivor markers:** these are rendered geometry, so the GPU LiDAR and the RGB camera see them, even though they don't collide. The verifier includes them in the LiDAR ray cast.

| World | Seed | Wall boxes | Rooms (first cell) | Markers in dead ends | Entrance→exit path |
|---|---|---|---|---|---|
| nidar_maze | 2026 | 40 | (2,7) (6,7) (6,3) | (8,4) (1,8) (7,2) | 57 cells |
| nidar_maze_s1 | 1 | 52 | (3,7) (4,4) (7,8) | (5,7) (4,9) (9,1) | 33 cells |
| nidar_maze_s2 | 2 | 53 | (1,5) (8,3) (2,0) | (3,2) (8,7) (7,1) | 31 cells |
| nidar_maze_s3 | 3 | 40 | (8,5) (0,3) (6,8) | (4,3) (0,5) (4,7) | 39 cells |
| nidar_maze_s4 | 4 | 41 | (6,1) (6,6) (1,0) | (3,9) (4,0) (7,4) | 49 cells |
| nidar_maze_s5 | 5 | 44 | (2,2) (1,6) (6,2) | (5,7) (0,3) (3,0) | 25 cells |

**The NIDAR rules themselves are NOT VERIFIED.** The values above come from the request; the official rule text was not available here.

### Other Phase 2 worlds

These are unchanged and regenerate byte-identically.

| World | Geometry | Spawn (x, y) | Wall boxes |
|---|---|---|---|
| empty | baseline only | (0, 0) | 0 |
| wall | one wall, face at x = 3.000 m, 4 m wide | (0, 0) | 1 |
| corridor | 2.0 m wide (faces y = ±1.0), 20 m long, open ends | (0, 0) | 2 |
| junction | 4-way crossing of two 2.0 m corridors, 6 m arms | (−3, 0) | 8 |
| room | closed, 6 × 4 m inside | (1.0, 0.5) | 4 |
| small_maze | perfect maze, 5 × 5 cells × 2.0 m, 2.0 m walls, seed 7; path 11 cells | (−4, −4) | 15 |

## How LiDAR is verified

`tools/verify_world_lidar.py <world …|all>` runs the following steps for each world, all with `GZ_IP=127.0.0.1`. It stops at the first FAIL.

1. **Provenance:** the world was generated from the current baseline, and `gz sdf -k` passes.
2. **Structure:** the number of maze collisions equals the number of wall boxes, and the launch pad and survivor markers have no collision.
3. **Ray cast:** with the vehicle at rest, record 2 s of scans. Ray-cast every beam in 2D from the **measured** pose against the wall boxes and the survivor markers, over 0.1–12 m.
4. **Room viewpoint (worlds with rooms):** `set_pose` the vehicle 0.9 m east of the first room's marker and repeat step 3. Also check that the beam toward the marker reads the marker face at 0.70 m.

| Check | Criterion |
|---|---|
| LiDAR rate (sim time) | 10 Hz ±10 % |
| Beams within the ray-cast band | ≥ 98 %. The band is the ray cast over ±½ beam step (±0.50°), ±5 cm; a no-return beam must be no-return in the band. |
| Range bias | \|bias\| ≤ 5 mm, on well-conditioned beams (band ≤ ±1 cm) |
| Single-scan noise | 0.5–2.0× the configured σ = 10 mm, on well-conditioned beams |
| Marker seen (room viewpoint) | 0.70 ± 0.05 m |

**Why the angle band is needed.** A plain ±5 cm per-beam check failed in the corridor at 333/360 beams (OBSERVED). All the misses were grazing beams, where dr/dθ = r·cot(incidence). Grazing beams imply a beam-angle error of at most 0.43° (INFERRED from the per-beam best-fit offset), consistent with the GPU LiDAR's finite render-texture angular resolution (INFERRED). It is not a physics effect. Per-beam data are saved as `logs/phase2-2026-10-03/<world>_<view>_beams.csv`.

## Results (consolidated run `run_184532.log`, OBSERVED)

| World | Result | Beams in band (start + room view) | Bias | Single-scan noise | Marker range (exp. 0.70 m) | LiDAR rate |
|---|---|---|---|---|---|---|
| empty | PASS | 360/360 | — | — | — | 10.43 Hz |
| wall | PASS | 360/360 | +0.46 mm | 10.5 mm | — | 10.21 Hz |
| corridor | PASS | 360/360 | −0.06 mm | 10.1 mm | — | 10.37 Hz |
| junction | PASS | 360/360 | −0.18 mm | 10.2 mm | — | 10.33 Hz |
| room | PASS | 360/360 | +0.41 mm | 10.4 mm | — | 10.21 Hz |
| small_maze | PASS | 360/360 | +0.10 mm | 10.3 mm | — | 10.21 Hz |
| nidar_maze | PASS | 360/360 + 360/360 | +0.32 mm | 10.1 mm | 0.6998 m | 10.11 Hz |
| nidar_maze_s1 | PASS | 360/360 + 360/360 | −0.08 mm | 10.0 mm | 0.6955 m | 10.06 Hz |
| nidar_maze_s2 | PASS | 360/360 + 360/360 | +0.02 mm | 9.9 mm | 0.6982 m | 10.08 Hz |
| nidar_maze_s3 | PASS | 360/360 + 360/360 | +0.05 mm | 10.0 mm | 0.7010 m | 10.09 Hz |
| nidar_maze_s4 | PASS | 360/360 + 360/360 | +0.06 mm | 10.1 mm | 0.6999 m | 10.07 Hz |
| nidar_maze_s5 | PASS | 360/360 + 360/360 | −0.06 mm | 10.2 mm | 0.7035 m | 10.11 Hz |

The bias and noise columns are for the start viewpoint. In every world the vehicle came to rest exactly at its spawn or teleport (x, y), at z = 0.0400 m with yaw 0.000°.

## Limitations

- **LiDAR coverage:** the check covers two viewpoints per NIDAR maze, not every cell. The full wall geometry is exact by construction, because the SDF and the sidecar are written from the same box list.
- **Spec interpretations to confirm:** the room size, the footprint convention and the marker size and shape (§NIDAR maze).
- **Depth camera:** still a KNOWN ISSUE (`docs/uav-physics-baseline.md`).
