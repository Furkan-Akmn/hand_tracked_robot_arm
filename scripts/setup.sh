#!/usr/bin/env bash
# Idempotent one-shot setup for hand_tracked_robot_arm.
# Safe to re-run: it only does what is missing.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ROS_DISTRO="${ROS_DISTRO:-jazzy}"
VENV_DIR=".venv"
MODEL_DIR="models"
MODEL_FILE="$MODEL_DIR/hand_landmarker.task"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

APT_PACKAGES=(
  ros-jazzy-ur-simulation-gz
  ros-jazzy-ur-moveit-config
  ros-jazzy-robotiq-description
  ros-jazzy-robotiq-controllers
  ros-jazzy-moveit
  ros-jazzy-moveit-servo
  ros-jazzy-gz-ros2-control
  ros-jazzy-xacro
)

# --- 1. ROS 2 ------------------------------------------------------------------
if [[ ! -f "/opt/ros/$ROS_DISTRO/setup.bash" ]]; then
  echo "ERROR: ROS 2 '$ROS_DISTRO' not found in /opt/ros." >&2
  echo "Install ROS 2 Jazzy first: https://docs.ros.org/en/jazzy/Installation.html" >&2
  exit 1
fi

missing=()
for pkg in "${APT_PACKAGES[@]}"; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if ((${#missing[@]} > 0)); then
  echo "==> Installing missing apt packages: ${missing[*]}"
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
else
  echo "==> All ROS 2 apt packages already installed"
fi

# --- 2. Python venv --------------------------------------------------------------
# --system-site-packages is essential: the venv must be able to import rclpy,
# which only exists inside /opt/ros (it is not pip-installable). See
# docs/environment.md for the full explanation.
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "==> Creating venv at $VENV_DIR (--system-site-packages)"
  python3 -m venv --system-site-packages "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
else
  echo "==> venv already exists"
fi

echo "==> Installing Python dependencies"
"$VENV_DIR/bin/pip" install --quiet -r requirements.txt

# --- 3. MediaPipe model -----------------------------------------------------------
mkdir -p "$MODEL_DIR"
if [[ ! -s "$MODEL_FILE" ]]; then
  echo "==> Downloading hand_landmarker.task"
  curl -fL --retry 3 -o "$MODEL_FILE" "$MODEL_URL"
else
  echo "==> hand_landmarker.task already present"
fi

# --- 4. Verify ---------------------------------------------------------------------
echo "==> Verifying environment"
"$VENV_DIR/bin/python" - <<'PY'
import cv2
import mediapipe
import numpy

print(f"    venv imports OK: mediapipe {mediapipe.__version__}, "
      f"opencv {cv2.__version__}, numpy {numpy.__version__}")
PY

set +u
# shellcheck disable=SC1091
source "/opt/ros/$ROS_DISTRO/setup.bash"
set -u
"$VENV_DIR/bin/python" -c "import rclpy; print('    venv can also import rclpy (ROS 2 in the same interpreter)')"

cat <<'EOF'

Setup complete.
Try the webcam skeleton demo:
    scripts/run.sh
EOF
