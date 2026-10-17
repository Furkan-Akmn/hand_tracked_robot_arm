# src/ — ROS 2 packages (colcon workspace)

Packages land here from milestone M1 onwards:

- `hand_tracking/` — webcam → MediaPipe → `/hand/state`
- `teleop_mapping/` — `/hand/state` → `/teleop/target_pose` (relative/delta control)
- `arm_bringup/` — launch files tying sim + MoveIt Servo + teleop together

Until then this directory intentionally stays empty.
