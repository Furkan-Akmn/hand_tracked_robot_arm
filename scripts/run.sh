#!/usr/bin/env bash
# Run anything inside the project environment (ROS 2 + project venv + workspace).
#
#   scripts/run.sh                                        # M0 webcam skeleton demo
#   scripts/run.sh ros2 launch arm_bringup sim.launch.py
#   scripts/run.sh ros2 topic echo /hand/state --once
#   scripts/run.sh python -m pytest src/hand_tracking/test -v
#
# Why this script exists: see docs/environment.md.
#
# The command is started in its own process group, so Ctrl+C (or closing the
# terminal) shuts down everything it spawned - ros2 launch, gazebo,
# controller_manager, ... - instead of leaking processes into the next run.
set -euo pipefail

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

# Make mediapipe & friends visible even to entry points whose shebang points
# at the system python (colcon console scripts may end up that way).
VENV_SITE="$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
export PYTHONPATH="${VENV_SITE}${PYTHONPATH:+:${PYTHONPATH}}"

if [[ -f install/setup.bash ]]; then
  # colcon's setup.bash trips over `set -u` on unset variables
  set +u
  # shellcheck disable=SC1091
  source install/setup.bash
  set -u
fi

# --- warn about processes left over from an earlier (interrupted) run -------
# (a leftover parameter_bridge alone is enough to double-publish /clock, which
# makes every node see time jump backwards)
leftover_pattern='ros2 launch|gz sim|parameter_bridge|robot_state_publisher|move_group|servo_node|controller_manager'
leftovers="$(pgrep -af "$leftover_pattern" 2>/dev/null | grep -vE "scripts/run.sh|pgrep -af" || true)"
if [[ -n "$leftovers" ]]; then
  echo "==> NOTE: ROS/Gazebo processes are already running:" >&2
  echo "$leftovers" | sed 's/^/      /' >&2
  echo "    If these are leftovers from an interrupted run they will fight this" >&2
  echo "    one (shared topics, TF and /clock). Stop them with:" >&2
  echo "      pkill -f '$leftover_pattern'" >&2
  echo >&2
fi

if [[ $# -eq 0 ]]; then
  set -- python tools/hand_skeleton_demo.py
fi

echo "==> Running: $*"
echo

# --- run the command in its own process group and clean it up on exit -------
child_pid=""

# Is anything of the command's process group still alive? (The group, not just
# the leader: ros2 launch may be gone while a child it lost track of is not.)
group_alive() {
  [[ -n "$child_pid" ]] && kill -0 -- "-$child_pid" 2>/dev/null
}

forward_signal() {
  group_alive && kill -"$1" -- "-$child_pid" 2>/dev/null || true
}

# Wait up to $1 seconds for the process group to exit.
wait_group() {
  local i
  for ((i = 0; i < $1 * 4; i++)); do
    group_alive || return 0
    sleep 0.25
  done
}

# EXIT runs on normal exit, failure, Ctrl+C and terminal close.
# The SIGINT grace period is longer than ros2 launch's own escalation
# (SIGINT -> 5 s -> SIGTERM -> 5 s -> SIGKILL) and longer than the 5 s the
# gz sim launcher gives its server, so the clean shutdown path gets to finish.
trap 'code=$?
  forward_signal INT
  wait_group 15
  forward_signal TERM
  wait_group 3
  forward_signal KILL
  wait "$child_pid" 2>/dev/null || true
  echo
  if [[ -t 0 && -t 1 ]]; then
    if [[ $code -eq 0 ]]; then
      echo "==> Command finished. Press Enter to close."
    elif [[ $code -eq 130 || $code -eq 143 ]]; then
      echo "==> Interrupted. Press Enter to close."
    else
      echo "==> Command FAILED (exit code $code). Scroll up to read the error, then press Enter to close."
    fi
    read -r _ || true
  fi
  exit $code' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

set -m  # give the background command its own process group
# Reset SIGINT to its default before exec'ing the command. When run.sh itself
# is started as a background job of a non-interactive script, SIGINT arrives
# ignored and would stay ignored in ros2 launch - which then never sees the
# Ctrl+C / forwarded SIGINT and leaks its whole process tree.
python3 -c 'import os, signal, sys
signal.signal(signal.SIGINT, signal.SIG_DFL)
os.execvp(sys.argv[1], sys.argv[1:])' "$@" &
child_pid=$!
set +m  # process group is set; silences "[1]+ Terminated" job notices
if wait "$child_pid"; then
  exit 0
else
  exit $?
fi
