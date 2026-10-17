#!/usr/bin/env bash
# Build the colcon workspace. Re-run after any change in src/.
#
#   scripts/build.sh                              # build everything
#   scripts/build.sh --packages-select hand_tracking
set -euo pipefail

trap 'code=$?; echo; if [[ -t 0 && -t 1 ]]; then
  if [[ $code -eq 0 ]]; then
    echo "==> Done. Press Enter to close."
  else
    echo "==> BUILD FAILED (exit code $code). Scroll up for the error, then press Enter to close."
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

echo "==> colcon build --symlink-install $*"
colcon build --symlink-install "$@"

cat <<'EOF'

Build complete. Try:
    scripts/run.sh ros2 launch hand_tracking hand_tracking.launch.py
    scripts/record_handbag.sh 30
EOF
