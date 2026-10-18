# Raw log manifest (files removed from Git history on 2026-10-04)

The raw binary logs below were produced by the AirMouse V1 SITL and diagnostic runs of 2026-10-03 and 2026-10-04. They were **removed from every commit** of this repository by a history rewrite, to keep the repository small; the shared team repo is pushed later. They are preserved outside Git, and this manifest keeps their provenance in Git.

- **Removed types:** `*.BIN` (ArduPilot dataflash), `*.tlog` (MAVProxy telemetry) and `*.ips` (macOS crash report). This is exactly the requested scope.
- **Kept in Git:** `*.tlog.raw`, `eeprom.bin`, `terrain/*.DAT`, all CSVs, summaries, run logs and docs.
- **Archive:** `/Users/arif_svii/AirMouse_raw_logs/airmouse_raw_logs_2026-10-03_04.zip` (stored on the author's Mac, outside the repository).
  - 14,990,742 bytes, SHA-256 `d05b62a4c53424ed3f482308bed7bfa5c245e6ff3e4c77af7236d314e76374e9`.
  - 25 files, with the paths below preserved inside the zip.
  - Every file was verified byte-identical against the working tree after zipping.
- **Additional local safety copy of the full pre-rewrite history:** `/Users/arif_svii/AirMouse_raw_logs/drone_pre_rewrite_20261004_014856.bundle` (18,746,796 bytes; `git bundle`).
- **Total size of the removed files:** 35,686,584 bytes (34.0 MB).
- **Restore one file:** `unzip <archive> '<path>'`, run from the repository root.

The analyses of these logs are already recorded in Git, in `docs/phase3-sitl.md` and `docs/research_log.md`, and summarised in each run's `run_*.log`.

| Path (repository-relative) | Type | Size (bytes) | SHA-256 |
|---|---|---:|---|
| `logs/phase3-2026-10-03/flight_empty_sitl_195644/arducopter_crash_195740.ips` | macOS crash report (contains device identifiers) | 13,005 | `f8afbb34bf79cabfee0addb4c046815c42813b4500f642902500195b5f9235bc` |
| `logs/phase3-2026-10-03/flight_empty_sitl_195644/logs/00000001.BIN` | ArduPilot dataflash log | 331,776 | `7f6e8a1fc9f3a8d2bfe3d3a1c60bdbf8ddd345e699483125c7dc211f48bfc3b7` |
| `logs/phase3-2026-10-03/flight_empty_sitl_195644/mav.tlog` | MAVProxy telemetry log | 262,116 | `1e61b322f7d2c8b1052e4fde058ee6b6a8bfde4fd22cca70e16a1f4017bd8f1b` |
| `logs/phase3-2026-10-03/flight_empty_sitl_210528/logs/00000001.BIN` | ArduPilot dataflash log | 2,715,648 | `c7e0c1839d8b1ecca771f615d76c616b33f670936ab62b2c4b7d259e907b01a2` |
| `logs/phase3-2026-10-03/flight_empty_sitl_210528/mav.tlog` | MAVProxy telemetry log | 393,168 | `e801f0cb0d737e57c33adff5fa77fbd5f292590d98478e94e53e1b4e72e5fe31` |
| `logs/phase3-2026-10-03/flight_nidar_maze_sitl_210844/logs/00000001.BIN` | ArduPilot dataflash log | 2,719,744 | `06a57f6b044c613ca68857181ebd0bcd59988a6de8691acbfeaa60367c9c5cfb` |
| `logs/phase3-2026-10-03/flight_nidar_maze_sitl_210844/mav.tlog` | MAVProxy telemetry log | 393,130 | `cf3063635140ac939d6dad92ebc81f67fb04ae6ee84e62162f47f351bcc908f9` |
| `logs/phase3-2026-10-03/motortest_192702/mav.tlog` | MAVProxy telemetry log | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `logs/phase3-2026-10-03/motortest_192929/mav.tlog` | MAVProxy telemetry log | 131,044 | `a131cb80b04e07cf9dae4ead5d222e2d2111594124c68d0bb18aed5f9baaef74` |
| `logs/phase3-2026-10-03/motortest_193027/mav.tlog` | MAVProxy telemetry log | 131,052 | `044cf6e8a9145d4b1e85f322b9dbcea20c395c43705b918373520497c21a0196` |
| `logs/phase3-2026-10-03/motortest_193134/logs/00000001.BIN` | ArduPilot dataflash log | 647,168 | `5e168210f6590b579641f955054c3e896a9eb67a4f84c46d35f4e548b34e8704` |
| `logs/phase3-2026-10-03/motortest_193134/mav.tlog` | MAVProxy telemetry log | 131,067 | `7682b4e9029df068ef412f139eae1c992070f629abce4aca8f6cd0563ef5b465` |
| `logs/phase3-2026-10-04/flight_empty_sitl_005532/logs/00000001.BIN` | ArduPilot dataflash log | 4,182,016 | `e2da90f1d4dd73fcdb4ea6da039a06059666eb05760533d1a50b89bdd8b5c41d` |
| `logs/phase3-2026-10-04/flight_empty_sitl_005532/mav.tlog` | MAVProxy telemetry log | 655,232 | `67c0acd21a86ac22594105fcadc139214221af36fadae2c4c93b430de1cb6d79` |
| `logs/phase3-2026-10-04/flight_empty_sitl_010554/logs/00000001.BIN` | ArduPilot dataflash log | 2,224,128 | `7d416d5711ac94ab7ae845486f7ce94a0252c9a57abefd46b320e6089a24ea88` |
| `logs/phase3-2026-10-04/flight_empty_sitl_010554/mav.tlog` | MAVProxy telemetry log | 393,164 | `e6eb0651d1df4309b69bd4a1cfb2c12681a82aa1f24e15f9e1ef671866917962` |
| `logs/phase3-2026-10-04/flight_empty_sitl_011343/mav.tlog` | MAVProxy telemetry log | 262,062 | `794f7cb682d28c38bb9400d32c0e9af74086b02a3cfbb0dbcde43b4d18883b03` |
| `logs/phase3-2026-10-04/flight_empty_sitl_011516/logs/00000001.BIN` | ArduPilot dataflash log | 3,801,088 | `9757b79f31ad62b347ef8abc4c60b9d42fd86958addf9b731c3d47fc1a0f9b49` |
| `logs/phase3-2026-10-04/flight_empty_sitl_011516/mav.tlog` | MAVProxy telemetry log | 1,048,032 | `2ebdb8fda0ce8b0e218ea15652f123aea70cfbadaed6705da00106b0852ba007` |
| `logs/phase3-2026-10-04/flight_empty_sitl_011710/logs/00000001.BIN` | ArduPilot dataflash log | 3,796,992 | `e82e96bf397c8c94b69209debd01ce6f0243189e32b4c3303e5dab34cbcf890f` |
| `logs/phase3-2026-10-04/flight_empty_sitl_011710/mav.tlog` | MAVProxy telemetry log | 1,047,956 | `89fe54cd8d36f33ccabb4ad29a32497792e5c86a5e0b3df7d4780bca4ea92487` |
| `logs/phase3-2026-10-04/flight_empty_sitl_011913/logs/00000001.BIN` | ArduPilot dataflash log | 3,805,184 | `2e50a7800fda24967ae51c52b049e386c1dd5021087fc54def2dda7d3d6a5cc5` |
| `logs/phase3-2026-10-04/flight_empty_sitl_011913/mav.tlog` | MAVProxy telemetry log | 1,048,122 | `503d48b08e1b64b8cb6da41ca5e414c3cbe441a22784d96ba01de8fea93b339d` |
| `logs/phase3-2026-10-04/flight_empty_sitl_012051/logs/00000001.BIN` | ArduPilot dataflash log | 4,636,672 | `f0856628b591e20025cdba607a22d2f41bf0be9cf723b8bb247472d7c20260cb` |
| `logs/phase3-2026-10-04/flight_empty_sitl_012051/mav.tlog` | MAVProxy telemetry log | 917,018 | `6bb049af9a233930ce4dcf50b9303f897c63b1a8afbc6fe9c64403c5a8526eee` |
