# Gazebo Harmonic installation attempt

Date: 2026-10-03  
Target: `osrf/simulation/gz-harmonic` 1.0.0, revision 5  
Platform: native macOS 26.3, ARM64, Apple M3, 8 GB RAM

## Result

**Installation did not start.** Homebrew was denied access to its trust lock file during preflight, before dependency planning, download, bottle pouring, or source compilation:

```text
Error: Operation not permitted @ rb_sysopen - /Users/arif_svii/.homebrew/trust.json.lock
```

The same error occurred once with `brew install --dry-run` and once with the actual `brew install`. No retry was made. No dependency was poured or built from source; there are no package-level installation failures to report because no formula installation began.

The command was configured for low resource use and project-local caching:

```text
HOMEBREW_CACHE=~/Drone/downloads/homebrew-cache
HOMEBREW_NO_AUTO_UPDATE=1
HOMEBREW_NO_INSTALL_CLEANUP=1
HOMEBREW_MAKE_JOBS=2
HOMEBREW_DOWNLOAD_CONCURRENCY=2
```

The execution environment permits writes in the project workspace and designated temporary locations, but not to `~/.homebrew` or `/opt/homebrew`. Homebrew could not acquire/create the trust lock in the home directory, so the install could not proceed. Rerun from a normal macOS Terminal or another environment that grants Homebrew its normal user-level write access and `/opt/homebrew` write access. No permission workaround was attempted here.

## Pre-install checks

| Check | Result |
|---|---|
| `df -h /` | 228 GiB total, 11 GiB used, **40 GiB available** (23% capacity) |
| `/opt/homebrew/var/homebrew/tmp/.cellar` | Empty: 0 entries, 0 B |
| `/opt/homebrew/Cellar` | 378 MiB |
| Registered formulas | Expected 32-formula inventory; unchanged after attempt |
| Target formula | `brew info` resolves to OSRF Harmonic 1.0.0 revision 5; not installed |
| Project cache | `~/Drone/downloads/homebrew-cache` exists; 1.9 GiB |

The current free-space reading was 40 GiB, one GiB below the supplied 41 GiB baseline. The required 10 GiB stop threshold was not approached.

## Post-attempt verification

- `brew list --formula`: same 32 formulas; `gz-harmonic` is not installed.
- `/opt/homebrew/var/homebrew/tmp/.cellar`: still empty.
- `/opt/homebrew/Cellar`: still 378 MiB.
- `df -h /`: still 40 GiB available.
- `~/Drone/downloads/homebrew-cache`: still present at 1.9 GiB.
- No `brew cleanup` was run. No unrelated caches, Wireshark files, Docker files, project environments, or permissions were changed.
- Gazebo is **not PASS**: executable, version, simulation command, and GUI smoke test were not available to verify because installation never started.
