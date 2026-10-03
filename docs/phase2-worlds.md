# AirMouse Phase 2: test worlds and LiDAR verification (2026-10-03)

**Result: all seven worlds PASS (OBSERVED).** Final consolidated run: `logs/phase2-2026-10-03/run_183429.log`. Each world was also verified and committed individually, one commit per world.

## How the worlds are built

`tools/make_maze.py <world|all>` writes `simulation/worlds/<world>.sdf` and a `<world>.json` sidecar.

- **Source:** each world is the **current baseline** `simulation/airmouse_quadrotor.sdf`, SHA-256 `21626e644770873ed59aa6dce6b5ce2f47b11b7ab9e45b5fa1e4f764d3fea88f`. The vehicle, physics, sensors and world name `airmouse_physics` are byte-identical to the baseline.
- **What is added:** one static `maze` model of axis-aligned wall boxes (height 2.0 m, thickness 0.1 m) and a new vehicle spawn pose (z = 0.1 m).
- **Sidecar:** records the exact wall boxes, the spawn pose and the baseline hash used. Physics parameters changed: none.
- **Regeneration:** if the baseline changes, run `python3 tools/make_maze.py all`. The verifier FAILs on any world built from an older baseline.
- **Maze generation:** a seeded randomised depth-first search builds a *perfect* maze, with collinear wall segments merged. The generator self-checks the result: N²−1 passages, every cell reachable, and it reports the entrance-to-exit path length. The entrance is on the south side of cell (0, 0) and the exit on the north side of cell (N−1, N−1). The vehicle starts in cell (0, 0).

| World | Geometry | Spawn (x, y) | Wall boxes |
|---|---|---|---|
| empty | baseline only | (0, 0) | 0 |
| wall | one wall, face at x = 3.000 m, 4 m wide | (0, 0) | 1 |
| corridor | 2.0 m wide (faces y = ±1.0), 20 m long, open ends | (0, 0) | 2 |
| junction | 4-way crossing of two 2.0 m corridors, 6 m arms | (−3, 0) | 8 |
| room | closed, 6 × 4 m inside | (1.0, 0.5) | 4 |
| small_maze | 5 × 5 cells × 2.0 m, seed 7; path 11 cells | (−4, −4) | 15 |
| nidar_maze | 15 × 15 cells × 2.0 m (30 × 30 m), seed 2026; path 135 cells | (−14, −14) | 107 |

**NIDAR dimensions are NOT VERIFIED.** The official NIDAR arena and maze specification was not available. The 15 × 15 grid follows the request, but the 2.0 m cell, 2.0 m wall height and 0.1 m wall thickness are assumptions. Regenerate with `--nidar-cells`, `--cell-size` and `--nidar-seed` once the rules are known.

Cell size was chosen from the vehicle footprint (ANALYTICAL): rotor tips reach 0.393 m from the centre along each axis, so the vehicle is about 0.79 m wide. That leaves about 0.6 m clearance per side in a 2.0 m cell.

## How LiDAR is verified

`tools/verify_world_lidar.py <world|all>` runs the following steps for each world:

1. Check that the world was generated from the current baseline, and run `gz sdf -k`.
2. Boot the world with `GZ_IP=127.0.0.1` and wait until the vehicle is at rest.
3. Record 2 s of scans.
4. Ray-cast every beam in 2D from the **measured** rest pose (x, y, yaw) against the sidecar wall boxes, over the configured range of 0.1–12 m.

The script stops at the first FAIL.

| Check | Criterion |
|---|---|
| LiDAR rate (sim time) | 10 Hz ±10 % |
| Beams within the ray-cast band | ≥ 98 %. The band is the ray cast over ±½ beam step (±0.50°), ±5 cm; a no-return beam must be no-return in the band. |
| Range bias | \|bias\| ≤ 5 mm, on well-conditioned beams (band ≤ ±1 cm) |
| Single-scan noise | 0.5–2.0× the configured σ = 10 mm, on well-conditioned beams |

**Why the angle band is needed.** The first corridor check, with a plain ±5 cm per beam, failed at 333/360 beams (OBSERVED). Every miss was a grazing, near-axis beam. At grazing incidence the range is extremely sensitive to the beam angle: dr/dθ = r·cot(incidence), about 33 m/rad at 10° from a wall 1 m away. Across all worlds, the measured grazing-beam ranges imply a beam-angle error of at most 0.43° (INFERRED from the per-beam best-fit offset). This is consistent with the GPU LiDAR's finite render-texture angular resolution (INFERRED). It is not a physics effect, and on well-conditioned beams the bias is below 0.5 mm. Per-beam data are saved as `logs/phase2-2026-10-03/<world>_beams.csv`.

## Results (consolidated run, OBSERVED)

| World | Result | Beams in band | Returns expected | Bias, well-conditioned beams | Single-scan noise | Grazing implied angle error (max) | LiDAR rate |
|---|---|---|---|---|---|---|---|
| empty | PASS | 360/360 | 0 | — | — | — | 10.30 Hz |
| wall | PASS | 360/360 | 68 | −0.06 mm | 10.4 mm | ≤ 0.03° | 10.15 Hz |
| corridor | PASS | 360/360 | 322 | −0.44 mm | 9.9 mm | 0.43° | 10.26 Hz |
| junction | PASS | 360/360 | 310 | −0.47 mm | 10.0 mm | 0.38° | 10.31 Hz |
| room | PASS | 360/360 | 360 | +0.23 mm | 10.3 mm | 0.33° | 10.08 Hz |
| small_maze | PASS | 360/360 | 276 | −0.02 mm | 10.2 mm | 0.37° | 10.24 Hz |
| nidar_maze | PASS | 360/360 | 276 | −0.05 mm | 10.2 mm | 0.35° | 10.16 Hz |

The "Returns expected" and maximum-angle-error columns come from the individual per-world runs. The other columns come from the consolidated run.

In every world, the vehicle came to rest exactly at its spawn (x, y), at z = 0.0400 m with yaw 0.000° (OBSERVED).

## Limitations

- **LiDAR coverage:** the check covers what the LiDAR can see from the start cell only. In the mazes, that is the local walls near the start, not the whole maze. The wall geometry itself is exact by construction, because the SDF and the sidecar are written from the same box list.
- **Ground plane visual:** the baseline's ground-plane visual is 20 × 20 m, but the NIDAR maze spans 30 × 30 m. The collision plane is an infinite plane, so this does not affect physics (INFERRED). An RGB image near the maze edge would show the visual's boundary. The baseline was not changed for this.
- **Depth camera:** still a KNOWN ISSUE (see `docs/uav-physics-baseline.md`). It is not used in Phase 2.
