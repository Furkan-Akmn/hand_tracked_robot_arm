#!/usr/bin/env bash
# Record a /hand/state rosbag - the project's deterministic hand-motion input.
#
#   scripts/record_handbag.sh [seconds]      # default: 30
#
# Starts the tracking node, records while you wave your hand, stops cleanly,
# then prints how to inspect / replay / test with the bag.
set -euo pipefail

node_pid=""

# SIGINT first (let the node shut down cleanly), then escalate.
stop_process() {
  local pid=$1
  kill -INT "$pid" 2>/dev/null || return 0
  for _ in $(seq 1 50); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.1
  done
  echo "warning: process $pid ignored SIGINT, sending SIGTERM" >&2
  kill -TERM "$pid" 2>/dev/null || true
  sleep 1
  kill -9 "$pid" 2>/dev/null || true
}

cleanup() {
  local code=$?
  if [[ -n "$node_pid" ]]; then
    stop_process "$node_pid"
  fi
  echo
  if [[ -t 0 && -t 1 ]]; then
    if [[ $code -eq 0 ]]; then
      echo "==> Done. Press Enter to close."
    else
      echo "==> FAILED (exit code $code). Scroll up for details, then press Enter to close."
    fi
    read -r _ || true
  fi
  exit "$code"
}
trap cleanup EXIT

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -f install/setup.bash ]]; then
  echo "ERROR: workspace not built yet. Run scripts/build.sh first." >&2
  exit 1
fi

DURATION="${1:-30}"
BAG_DIR="bags/hand_$(date +%Y%m%d_%H%M%S)"

set +u
# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
set -u
# shellcheck disable=SC1091
source .venv/bin/activate
VENV_SITE="$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
export PYTHONPATH="${VENV_SITE}${PYTHONPATH:+:${PYTHONPATH}}"
set +u
# shellcheck disable=SC1091
source install/setup.bash
set -u

mkdir -p bags
echo "==> Starting hand_tracking node in the background"
echo "    (log: /tmp/hand_tracking_node.log)"
# Run the module directly (not via `ros2 run`) so SIGINT reaches the node.
python -m hand_tracking.landmark_node > /tmp/hand_tracking_node.log 2>&1 &
node_pid=$!
sleep 3  # camera open + model warm-up

echo "==> Recording /hand/state for ${DURATION}s -> $BAG_DIR"
echo "    (wave your hand in front of the camera!)"
# Foreground `timeout` delivers a clean SIGINT to the recorder at expiry.
# (A plain `ros2 bag record ... &` would ignore SIGINT: non-interactive shells
# start background jobs with SIGINT set to SIG_IGN, which Python preserves.)
timeout --signal=INT --kill-after=5 "$DURATION" ros2 bag record -s sqlite3 -o "$BAG_DIR" /hand/state || true

echo
if [[ -f "$BAG_DIR/metadata.yaml" ]]; then
  echo "==> Bag saved: $BAG_DIR ($(du -sh "$BAG_DIR" | cut -f1))"
else
  echo "WARNING: $BAG_DIR/metadata.yaml is missing - the recording did not finalize cleanly." >&2
fi
echo "    Inspect: ros2 bag info $BAG_DIR"
echo "    Replay : ros2 bag play $BAG_DIR"
echo "    Test   : HAND_BAG_DIR=$BAG_DIR scripts/run.sh python -m pytest src/hand_tracking/test/test_bag_replay.py -v"
