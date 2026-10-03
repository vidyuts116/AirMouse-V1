# Gazebo Harmonic pre-install audit

Date: 2026-10-03  
Scope: Read-only pre-install audit for native macOS on the AirMouse machine. No software was installed, and no cache cleanup or permission change was performed.

## Machine and Homebrew

| Check | Result |
|---|---|
| `uname -m` | `arm64` |
| `sw_vers` | macOS 26.3, build 25D125 |
| `brew --prefix` | `/opt/homebrew` |
| `df -h /` | 228 GiB total; 11 GiB used; 41 GiB available; 22% capacity |
| Project cache | `~/Drone/downloads/homebrew-cache` exists; 1.9 GiB |
| `brew tap` | `osrf/simulation` |
| Installed formula count | 32 |

The installed formula inventory is unchanged from the prior report. `gz-harmonic` is not installed.

## Formula availability and requirements

Both `brew info gz-harmonic` and `brew info osrf/simulation/gz-harmonic` resolve to `osrf/simulation/gz-harmonic` in the `osrf/simulation` tap.

- Stable version: **1.0.0**, revision 5.
- Formula declares **17 required dependencies** (the list shown by `brew info`) and a CMake build dependency. Its recursive declared dependency closure contains **199 unique formulae**; 16 are already registered as installed: `abseil`, `brotli`, `c-ares`, `ca-certificates`, `fmt`, `highway`, `icu4c@78`, `lz4`, `mpdecimal`, `openssl@3`, `pcre2`, `python@3.14`, `readline`, `sqlite`, `xz`, and `zstd`.
- Homebrew's `brew info` does not report download or installed-size estimates for this formula. No size estimate is recorded here.
- Formula bottle metadata is empty and there are no bottle tags. Therefore **no ARM64 bottle is published for this formula**, including for this macOS environment.
- The formula downloads the `gz-harmonic-1.0.0.tar.bz2` source archive and runs CMake followed by `make install`. The top-level Gazebo Harmonic collection therefore **must build from source**. This audit did not assess whether each dependency has a bottle for macOS 26 ARM64.

The local formula metadata agrees with the upstream [OSRF Homebrew formula](https://github.com/osrf/homebrew-simulation/blob/master/Formula/gz-harmonic.rb).

## Audit constraints and notes

- No `brew install`, `brew cleanup`, or cache removal was run.
- `HOMEBREW_NO_AUTO_UPDATE=1` was used for Homebrew queries; no tap update was requested.
- While inspecting formula source, `brew cat` automatically enabled Homebrew developer mode. `brew developer off` was run immediately afterward; a follow-up confirmed developer mode is disabled. This restored the prior reported state; no other Homebrew configuration changes were made.
- The target Gazebo version for ROS 2 Jazzy remains Gazebo Harmonic, as requested. This report only covers package availability and installation requirements; it makes no compatibility or performance guarantee for the 8 GB MacBook Air.
