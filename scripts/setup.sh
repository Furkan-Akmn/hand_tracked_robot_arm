#!/usr/bin/env bash
# Idempotent one-shot setup for hand_tracked_robot_arm.
# Safe to re-run: it only does what is missing.
# Shows download progress and keeps the window open when run interactively.
set -euo pipefail

# --- keep the terminal open at the end (also on failure) -------------------------
trap 'code=$?; echo; if [[ -t 0 && -t 1 ]]; then
  if [[ $code -eq 0 ]]; then
    echo "==> Setup finished successfully. Press Enter to close."
  else
    echo "==> SETUP FAILED (exit code $code). Scroll up to read the error, then press Enter to close."
  fi
  read -r _ || true
fi; exit $code' EXIT

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

echo "==============================================================="
echo " hand_tracked_robot_arm - environment setup"
echo "   ROS 2 distro : $ROS_DISTRO"
echo "   venv         : $VENV_DIR (--system-site-packages, for mediapipe)"
echo "   model        : $MODEL_FILE"
echo "==============================================================="

# --- 1/5 ROS 2 ---------------------------------------------------------------------
echo
echo "[1/5] Checking ROS 2 installation..."
if [[ ! -f "/opt/ros/$ROS_DISTRO/setup.bash" ]]; then
  echo "ERROR: ROS 2 '$ROS_DISTRO' not found in /opt/ros." >&2
  echo "Install ROS 2 Jazzy first: https://docs.ros.org/en/jazzy/Installation.html" >&2
  exit 1
fi
echo "      found /opt/ros/$ROS_DISTRO"

# --- 2/5 apt packages ----------------------------------------------------------------
echo
echo "[2/5] Checking ROS 2 apt packages..."
missing=()
for pkg in "${APT_PACKAGES[@]}"; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if ((${#missing[@]} > 0)); then
  echo "      ${#missing[@]} package(s) missing - download progress below"
  echo "      (sudo may ask for your password)"
  echo
  sudo apt update
  sudo apt install -y "${missing[@]}"
else
  echo "      all ${#APT_PACKAGES[@]} packages already installed - skipping"
fi

# --- 3/5 Python venv -------------------------------------------------------------------
echo
echo "[3/5] Python venv..."
# --system-site-packages is essential: the venv must be able to import rclpy,
# which only exists inside /opt/ros (it is not pip-installable). See
# docs/environment.md for the full explanation.
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "      creating $VENV_DIR (this takes a few seconds)"
  python3 -m venv --system-site-packages "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
else
  echo "      $VENV_DIR already exists"
fi

# --- 4/5 Python dependencies -------------------------------------------------------------
echo
echo "[4/5] Python dependencies (pip shows download progress below)..."
"$VENV_DIR/bin/pip" install -r requirements.txt

# --- 5/5 MediaPipe model + verification ----------------------------------------------------
echo
echo "[5/5] MediaPipe hand-landmarker model..."
mkdir -p "$MODEL_DIR"
if [[ ! -s "$MODEL_FILE" ]]; then
  echo "      downloading hand_landmarker.task (~7 MB, progress below)"
  curl -fL --retry 3 --progress-bar -o "$MODEL_FILE" "$MODEL_URL"
  echo
else
  echo "      $MODEL_FILE already present"
fi
echo "      model size: $(du -h "$MODEL_FILE" | cut -f1)"

echo
echo "      verifying environment..."
"$VENV_DIR/bin/python" - <<'PY'
import cv2
import mediapipe
import numpy

print(f"      venv imports OK: mediapipe {mediapipe.__version__}, "
      f"opencv {cv2.__version__}, numpy {numpy.__version__}")
PY

set +u
# shellcheck disable=SC1091
source "/opt/ros/$ROS_DISTRO/setup.bash"
set -u
"$VENV_DIR/bin/python" -c "import rclpy; print('      venv can also import rclpy (both worlds in one interpreter)')"

cat <<'EOF'

===============================================================
 Setup complete.
 Next: run the webcam skeleton demo:

     scripts/run.sh

 Press q or Esc in the demo window to quit.
===============================================================
EOF
