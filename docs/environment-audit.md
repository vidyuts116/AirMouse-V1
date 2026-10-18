# AirMouse Native macOS Environment Audit

Audit date: 2026-10-03 (local time, Asia/Kolkata)  
Project root: `/Users/arif_svii/Drone`  
Scope: Phase 0 read-only audit. No software was installed or removed and no existing project content was replaced. This file is the only file created for this audit.

## Machine

| Check | Status | Finding |
|---|---|---|
| macOS version | VERIFIED | macOS 26.3, build 25D125 (`sw_vers`). |
| Architecture | VERIFIED | ARM64 (`uname -m`). |
| CPU | VERIFIED | Apple M3, 8 CPU cores (4 performance, 4 efficiency), from `system_profiler SPHardwareDataType`. |
| GPU | VERIFIED | Apple M3 integrated GPU, 10 cores; `system_profiler SPDisplaysDataType` reports Metal supported. Actual Gazebo/OGRE rendering is UNKNOWN until a GUI test. |
| RAM | VERIFIED | 8 GB LPDDR5. |
| Storage | VERIFIED | `df -h` reports 44 GiB available on the Data volume at audit time. This is current free space, not total project capacity. |

## Developer tools

| Check | Status | Finding |
|---|---|---|
| Homebrew | VERIFIED | `/opt/homebrew/bin/brew`, version 7.0.7. |
| Git | VERIFIED | `/usr/bin/git`, Apple Git 2.50.1. |
| Apple Clang | VERIFIED | Apple clang 17.0.0, target `arm64-apple-darwin25.3.0`. |
| Xcode Command Line Tools | VERIFIED | `xcode-select -p` returns `/Library/Developer/CommandLineTools`. Full Xcode installation was not checked and is NOT REQUIRED for this audit. |
| CMake | NOT INSTALLED | `cmake` is not on `PATH`; `cmake --version` returns command not found. |
| Python | VERIFIED | `python3` resolves to `/usr/bin/python3`, version 3.9.6. `python` resolves to `/opt/anaconda3/bin/python`; its version and environments were not inspected. Homebrew also lists `python@3.14`. Which Python should be used for project tooling remains UNKNOWN pending compatibility decisions. |
| Compilers | VERIFIED | Apple Clang is present. Other compiler toolchains were not exhaustively inventoried. |
| Python environments | UNKNOWN | Anaconda is present at `/opt/anaconda3/bin/python`; environment inventory was not collected. No project virtual environment appeared in the root directory listing. |
| Homebrew packages | VERIFIED | `brew list --versions` completed. Installed packages include `python@3.14` and dependencies; no `cmake`, ROS, or Gazebo formula appeared in the listing. Full package output was captured in the audit session, not copied here. Existing unrelated packages were left untouched. |

## Robotics and simulation software

| Check | Status | Finding |
|---|---|---|
| ROS 2 | NOT INSTALLED | `ros2` is not on `PATH`; common `/opt/ros` location is absent. Other nonstandard installations have not been ruled out. Native Jazzy compatibility was not evaluated in this inventory-only phase. |
| Gazebo | NOT INSTALLED | `gz` and `gazebo` are not on `PATH`; no Gazebo-named Homebrew package appeared in the installed package list. GUI, rendering, physics, world/model loading, and shutdown are therefore NOT TESTED. |
| Existing Gazebo versions | UNKNOWN | No executable was found through `PATH` or the checked common package locations. A complete disk-wide application search was not performed. |
| Running ROS/Gazebo processes | UNKNOWN | Process listing was denied by macOS privacy controls (`ps: operation not permitted`); no conclusion is drawn from it. |
| Metal capability | VERIFIED (hardware/API support only) | System Profiler reports Metal supported. Gazebo rendering through the eventual graphics backend is UNKNOWN until the Phase 1 diagnostic GUI test. |

## Existing AirMouse project work

| Check | Status | Finding |
|---|---|---|
| `~/Drone` contents | VERIFIED | The root contained `backups/`, `build/`, `docs/`, `downloads/`, `install/`, `logs/`, `src/`, and `tools/`, all empty at audit time. No `simulation/`, `models/`, `worlds/`, `plugins/`, `scripts/`, `config/`, or `tests/` directories existed. |
| Existing project files | VERIFIED | No README, SDF/world, CMake, package manifest, or AirMouse-named file was found in `~/Drone`. No Git repository was detected (`git status` reports that the directory is not a repository). |
| Other AirMouse copies | UNKNOWN | A search under `/Users/arif_svii` to depth 5 for paths named `AirMouse` or `air_mouse` returned no matches. This is not a complete search of all mounted volumes or paths outside the user's home. No migration or replacement was attempted. |

## Audit limitations and next gate

This audit confirms hardware and executable discovery only. It does not establish that Gazebo is available or compatible with macOS 26.3, that its GUI can render on Apple Metal, or that native ROS 2 Jazzy is supported. Those questions require source/package compatibility research and then a small diagnostic Gazebo test. Do not begin the AirMouse model until the diagnostic GUI, rendering, physics, world load, and clean shutdown checks pass as requested.
