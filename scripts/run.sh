#!/usr/bin/env bash
# Run anything inside the project environment (ROS 2 + project venv).
#
#   scripts/run.sh                    # webcam hand-skeleton demo
#   scripts/run.sh ros2 launch ...    # later milestones
#
# Sourcing order and the venv trick are explained in docs/environment.md.
set -euo pipefail

# --- keep the terminal open at the end (also on failure / Ctrl+C) -----------------
trap 'code=$?; echo; if [[ -t 0 && -t 1 ]]; then
  if [[ $code -eq 0 ]]; then
    echo "==> Command finished. Press Enter to close."
  else
    echo "==> Command FAILED (exit code $code). Scroll up to read the error, then press Enter to close."
  fi
  read -r _ || true
fi; exit $code' EXIT

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -x .venv/bin/python ]]; then
  echo "ERROR: project venv (.venv) not found." >&2
  echo "Run scripts/setup.sh first." >&2
  exit 1
fi

set +u
# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
set -u
# shellcheck disable=SC1091
source .venv/bin/activate

if [[ $# -eq 0 ]]; then
  set -- python tools/hand_skeleton_demo.py
fi

echo "==> Running: $*"
echo

"$@"
