#!/usr/bin/env bash
# One-command AirMouse simulation launch.
#
#   scripts/launch_sim.sh <world> [--sitl] [--gui] [--profile ideal|nominal|degraded] [--no-mavproxy]
#
#   <world>      a name in simulation/worlds (empty, wall, corridor, junction, room, small_maze, nidar_maze,
#                nidar_maze_s1..s5) or a path to an .sdf
#   --sitl       also start ArduCopter SITL (JSON backend) and MAVProxy; the world is regenerated first with
#                tools/make_sitl_world.py (adds ArduPilotPlugin, FRD IMU, ...)
#   --profile P  realism profile from config/sim_profiles.yaml (wind, IMU noise, LiDAR dropout); needs --sitl
#   --gui        also open the Gazebo GUI (separate `gz sim -g`; macOS GUI is NOT VERIFIED here)
#   --no-mavproxy  with --sitl: leave the MAVLink TCP port 5760 free for your own client
#
# Ctrl-C stops everything it started. Gazebo Transport is loopback-only (GZ_IP=127.0.0.1); ROS 2 nodes must
# use the same (see docs/interfaces/sim_to_ros.md). MAVLink: MAVProxy forwards to udp:127.0.0.1:14550 and
# udp:127.0.0.1:14551; without MAVProxy ArduCopter listens on tcp:127.0.0.1:5760.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
usage() { sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

WORLD="" SITL=0 GUI=0 PROFILE="" MAVPROXY=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sitl) SITL=1 ;;
    --gui) GUI=1 ;;
    --profile) PROFILE="${2:?--profile needs a name}"; shift ;;
    --no-mavproxy) MAVPROXY=0 ;;
    -h|--help) usage 0 ;;
    -*) echo "unknown option $1" >&2; usage 1 ;;
    *) [[ -z "$WORLD" ]] && WORLD="$1" || { echo "only one world allowed" >&2; usage 1; } ;;
  esac
  shift
done
[[ -n "$WORLD" ]] || usage 1
[[ -z "$PROFILE" || $SITL == 1 ]] || { echo "--profile needs --sitl (profiles are applied to the SITL world)" >&2; exit 1; }

export PATH="/opt/homebrew/bin:$PATH"
export GZ_IP=127.0.0.1
export GZ_SIM_SYSTEM_PLUGIN_PATH="$ROOT/src/airmouse_sitl_bridge/build${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
command -v gz >/dev/null || { echo "gz not found (brew install gz-harmonic)" >&2; exit 1; }

if [[ -f "$WORLD" ]]; then SRC="$(cd "$(dirname "$WORLD")" && pwd)/$(basename "$WORLD")"
elif [[ -f "simulation/worlds/$WORLD.sdf" ]]; then SRC="$ROOT/simulation/worlds/$WORLD.sdf"
else echo "world '$WORLD' not found (see simulation/worlds/*.sdf)" >&2; exit 1; fi
pgrep -f '^gz sim' >/dev/null && { echo "a gz sim process is already running; stop it first (pkill -f '^gz sim')" >&2; exit 1; }

LOGDIR="$ROOT/logs/launch-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOGDIR"
PIDS=()
cleanup() {
  trap - EXIT INT TERM
  echo; echo "stopping..."
  for p in "${PIDS[@]:-}"; do [[ -n "$p" ]] && kill "$p" 2>/dev/null || true; done
  sleep 1
  pkill -f '^gz sim' 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [[ $SITL == 1 ]]; then
  VENV="$ROOT/.venv-ardupilot/bin"
  ARDU="$ROOT/src/ardupilot/build/sitl/bin/arducopter"
  [[ -x "$ARDU" && -x "$VENV/python" ]] || { echo "SITL not built; see README 'Requirements' / 'Build ArduCopter SITL'" >&2; exit 1; }
  [[ -f "$ROOT/src/airmouse_sitl_bridge/build/libArduPilotPlugin.dylib" ]] || { echo "bridge plugins not built; see README" >&2; exit 1; }
  ARGS=("$SRC"); [[ -n "$PROFILE" ]] && ARGS+=(--profile "$PROFILE")
  "$VENV/python" tools/make_sitl_world.py "${ARGS[@]}"
  STEM="$(basename "$SRC" .sdf)_sitl${PROFILE:+_$PROFILE}"
  SIM_WORLD="$ROOT/simulation/sitl/$STEM.sdf"
else
  SIM_WORLD="$SRC"
fi

echo "world: $SIM_WORLD"
gz sim -s -r "$SIM_WORLD" > "$LOGDIR/gz_server.log" 2>&1 &
PIDS+=($!)
sleep 6
kill -0 "${PIDS[0]}" 2>/dev/null || { echo "gz sim exited; see $LOGDIR/gz_server.log" >&2; exit 1; }
if [[ $GUI == 1 ]]; then gz sim -g > "$LOGDIR/gz_gui.log" 2>&1 & PIDS+=($!); fi

if [[ $SITL == 1 ]]; then
  P="$ROOT/src/ardupilot/Tools/autotest/default_params/copter.parm"
  DEFAULTS="$P,$ROOT/simulation/sitl/airmouse_sitl.parm,$ROOT/simulation/sitl/airmouse_provisional_flight.parm"
  (cd "$LOGDIR" && exec "$ARDU" --model JSON --speedup 1 -w --defaults "$DEFAULTS" -I0 \
      --home -35.363261,149.165230,584,0 > arducopter.log 2>&1) &
  PIDS+=($!)
  echo "ArduCopter SITL started (params PROVISIONAL, simulation only; logs in $LOGDIR)"
  if [[ $MAVPROXY == 1 ]]; then
    sleep 3
    echo "MAVProxy: forwarding to udp:127.0.0.1:14550 and :14551 (type 'exit' or Ctrl-C to stop everything)"
    "$VENV/mavproxy.py" --master tcp:127.0.0.1:5760 --out udp:127.0.0.1:14550 --out udp:127.0.0.1:14551 \
        --state-basedir "$LOGDIR" || true
    exit 0
  fi
fi

echo "running; Ctrl-C to stop. Topics: gz topic -l"
wait "${PIDS[0]}"
