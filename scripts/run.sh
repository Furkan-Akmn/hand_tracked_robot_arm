#!/usr/bin/env bash
# Run anything inside the project environment (ROS 2 + project venv).
#
#   scripts/run.sh                    # webcam hand-skeleton demo
#   scripts/run.sh ros2 launch ...    # later milestones
#
# Sourcing order and the venv trick are explained in docs/environment.md.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

set +u
# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
set -u
# shellcheck disable=SC1091
source .venv/bin/activate

if [[ $# -eq 0 ]]; then
  set -- python tools/hand_skeleton_demo.py
fi
exec "$@"
