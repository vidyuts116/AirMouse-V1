# Native Gazebo diagnostic — Phase 1

Date: 2026-10-03 (Asia/Kolkata)  
Machine: Apple M3, macOS 26.3 (build 25D125), ARM64  
Status: **FAIL — installation did not complete; Gazebo was not available for runtime diagnostics.**

## Release and documented installation path

The current official Gazebo installation documentation identifies **Gazebo Jetty** as the current long-term release. Its macOS binary instructions prescribe the OSRF Homebrew tap and `gz-jetty` formula:

```sh
brew tap osrf/simulation
brew trust osrf/simulation
brew install gz-jetty
```

Sources: [Jetty macOS binary installation](https://gazebosim.org/docs/latest/install_osx/) and [Jetty release/platform status](https://gazebosim.org/docs/latest/install/). The official page says the macOS binaries are available for Ventura and Sonoma. This host runs macOS 26.3, outside that documented range; macOS and ARM64 are best-effort platforms for this release.

Homebrew formula metadata checked before installation reported `gz-jetty` stable **1.0.0** (install candidate `1.0.0_1`), alias `gz-kura`. It declares 17 direct required Gazebo/library dependencies. Homebrew resolved the full dependency closure to **194 formulae**, including transitive GUI/rendering/physics libraries and four proposed upgrades (`ca-certificates`, `openssl@3`, `pcre2`, `python@3.14`). This is the formula manager's dependency closure, not a separately selected list. None of the formulae were successfully installed before the attempt was stopped.

## Commands run and installation state

Homebrew was present at `/opt/homebrew/bin/brew`, version **7.0.7**. No Gazebo formula was installed before this attempt. Project-local cache and logs were configured, and the documented tap/trust commands succeeded:

```sh
mkdir -p downloads/homebrew-cache logs/homebrew
export HOMEBREW_CACHE="$PWD/downloads/homebrew-cache"
export HOMEBREW_LOGS="$PWD/logs/homebrew"
brew tap osrf/simulation
brew trust osrf/simulation
brew info osrf/simulation/gz-jetty
brew install osrf/simulation/gz-jetty
```

The first install attempt failed fetching several bottles (connection errors to `ghcr.io` and `osrf-distributions.s3.amazonaws.com`). Single endpoint checks then returned HTTP responses, so one retry was made with `HOMEBREW_CURL_RETRIES=5`. It fetched most bottles but remained stuck downloading the OSRF `ogre1.9` bottle. After more than 14 minutes the partial file remained 1.2 MiB of the expected 4.1 MiB. A ranged request to that same URL returned 1 KiB at about 557 bytes/second. The install was interrupted rather than retried again.

Final checks:

- `command -v gz`: no result.
- `brew list --versions` and `/opt/homebrew/Cellar`: no installed Gazebo, OGRE, Qt, or SDFormat formulas.
- The installed formula inventory remained unrelated to Gazebo; checks found no Gazebo, OGRE, Qt, or SDFormat formulas. Homebrew had announced four potential upgrades during dependency resolution; the failed download phase prevented formula installation or those upgrades.
- Formula installation location: **none**. Intended Homebrew prefix: `/opt/homebrew`.
- Project-local bottle cache: `~/Drone/downloads/homebrew-cache` (about 1.9 GiB at inspection); project-local Homebrew logs directory: `~/Drone/logs/homebrew`.
- Available disk space at final inspection: about 36 GiB.

## Diagnostic world

Created the small gravity-and-contact test world at [`../simulation/diagnostic.sdf`](../simulation/diagnostic.sdf). It contains a ground plane and one 0.5 m box starting 1 m above the ground, with gravity enabled and the default physics system. This file was **not loaded** because `gz` was unavailable.

## Requested runtime checks

| Check | Result | Evidence |
|---|---|---|
| `command -v gz` | **FAIL** | No executable found after the installation attempt. |
| `gz sim --version` | **NOT RUN** | No `gz` executable. Installed version: none. Candidate formula metadata: Jetty 1.0.0. |
| GUI startup | **NOT RUN** | No Gazebo binary. |
| Native 3D rendering | **NOT RUN** | Metal hardware/API capability is not proof of Gazebo rendering; no rendering session occurred. |
| Diagnostic world load | **NOT RUN** | World created at `simulation/diagnostic.sdf`, but could not be opened in Gazebo. |
| Primitive/model visible | **NOT RUN** | The world defines a box, but no GUI was available to inspect it. |
| Physics/contact | **NOT RUN** | No simulation process ran. |
| Gravity | **NOT RUN** | No simulation process ran. |
| GUI responsiveness | **NOT RUN** | No GUI session occurred. |
| CPU/RAM during Gazebo | **NOT RUN** | No Gazebo process ran; host memory is 8 GiB per the Phase 0 audit. |
| Clean shutdown | **NOT RUN** | No Gazebo process started. The Homebrew install itself was interrupted with Ctrl-C (exit 130). |

## Warnings and failures

- Official macOS binary documentation names Ventura and Sonoma, not this macOS 26.3 host; support is best-effort.
- Homebrew warned that `freeimage` is deprecated due to outstanding CVEs and will be disabled on 2027-01-10.
- Bottle downloads encountered connection errors and extremely low throughput. The retry recovered some downloads but did not complete.
- No macOS security settings were changed. No Ubuntu, Docker, VMware, VM, ROS 2, or AirMouse UAV work was performed.

**Overall Phase 1 result: FAIL.** The official native installation was attempted, but the package installation and all Gazebo runtime diagnostics remain incomplete. No GUI, rendering, physics, gravity, responsiveness, resource-use, or clean Gazebo-shutdown pass is claimed.
