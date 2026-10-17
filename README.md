# hand_tracked_robot_arm

Teleoperation of a robot arm inside an **isolated experiment box** (glovebox,
biosafety cabinet, anaerobic chamber) by **tracking the operator's bare hand**:
a camera watches the hand, and the arm inside the box mimics the motion.

Because control is vision-based, there is no leader arm and no need to reach
into the box — and since all electronics except the arm can live outside the
box, the hardware stays out of the sterilization problem.

## Status

**M2 — UR5e + Robotiq 2F-85 in Gazebo with MoveIt Servo ✅**
The simulated cell comes up headless or with GUIs, the gripper takes
open/close goals, and MoveIt Servo follows Cartesian twists streamed by
`scripts/servo_twist.py`. See "Run the simulated arm" below.

**M1 — hand tracking ROS 2 node ✅**
`hand_tracking` publishes `/hand/state` from the webcam: 21 raw landmarks,
One-Euro-filtered palm position/orientation, a pinch signal, and a strict
`detected` contract for downstream safety logic. Real hand motion can be
recorded into rosbags for deterministic replay. No arm in the loop yet (M2).

## Quickstart

Prerequisites: Ubuntu 24.04 with ROS 2 Jazzy and a webcam.

```bash
scripts/setup.sh      # one-time: apt packages + venv + mediapipe model
scripts/build.sh      # build the ROS 2 workspace (re-run after src/ changes)
```

Run the tracking node (local preview window: add `show_window:=true`):

```bash
scripts/run.sh ros2 launch hand_tracking hand_tracking.launch.py
```

Watch the data land:

```bash
scripts/run.sh ros2 topic echo /hand/state --once
scripts/run.sh ros2 topic hz /hand/state
```

### Run the simulated arm (M2)

Gazebo + RViz + MoveIt Servo for the UR5e with a Robotiq 2F-85:

```bash
scripts/run.sh ros2 launch arm_bringup servo_sim.launch.py
```

In a second terminal — select the twist input once per session, then stream a
stamped twist for 4 s:

```bash
scripts/run.sh ros2 service call /servo_node/switch_command_type \
    moveit_msgs/srv/ServoCommandType "{command_type: 1}"
scripts/run.sh python scripts/servo_twist.py --linear 0.05 0 0 --duration 4
```

Gripper open (0.0) / close (0.8):

```bash
scripts/run.sh ros2 action send_goal /robotiq_gripper_controller/gripper_cmd \
    control_msgs/action/ParallelGripperCommand \
    "{command: {name: [robotiq_85_left_knuckle_joint], position: [0.8]}}"
```

Twists must carry a fresh timestamp: `ros2 topic pub` sends stamp 0, which
Servo (Jazzy) silently drops as stale — use `scripts/servo_twist.py`.

Record 30 s of your hand motion for offline tests:

```bash
scripts/record_handbag.sh 30
```

The M0 webcam skeleton demo still works without ROS: `scripts/run.sh`.

## Interfaces (M1)

| Topic | Type | Contents |
|---|---|---|
| `/hand/state` | `arm_teleop_interfaces/HandState` | `detected`, `confidence`, raw `landmarks[63]`, filtered `palm_center`, `palm_orientation`, `pinch` |
| `/hand/debug_image` | `sensor_msgs/Image` (bgr8) | annotated camera frame, throttled to 10 Hz |

Contract: when `detected` is false all numeric fields are zeroed (quaternion =
identity) and MUST be ignored; consumers must also treat stale header stamps
as "no hand" (watchdog). All coordinates are in mirrored (selfie) image space.
Details live in the `.msg` comments.

## Target architecture

Three swappable layers connected by ROS 2 topics:

```
  INPUT  (swappable)
  webcam ──▶ hand_tracking ──▶ /hand/state   (landmarks, pinch, confidence)
                                  ▲
  future: VR runtime ─────────────┘          (same topic; nothing downstream changes)

  MAPPING
  teleop_mapping: relative/delta mode, deadband, workspace clamp,
  pinch → gripper, "clutch" pose, watchdog ──▶ /teleop/target_pose

  ARM  (swappable)
  MoveIt Servo ──▶ ros2_control ──▶ Gazebo (UR5e + Robotiq 2F-85)
  later: a real arm replaces only the ros2_control hardware interface
```

## Milestones

- [x] **M0** — environment, repo scaffold, webcam hand-skeleton demo
- [x] **M1** — `hand_tracking` node publishing `/hand/state` + rosbag capture/replay
- [x] **M2** — UR5e + Robotiq live in Gazebo (controllers, gripper, Servo-stamped twists)
- [ ] **M3** — `teleop_mapping` node: wave hand → arm moves (watchdog + clamps verified)
- [ ] **M4** — tests (pytest + bag replay), docs, demo GIF
- [ ] **M5** — VR input (OpenXR) publishing the same `/hand/state` interface

## Testing

Unit tests (pure Python — no camera, no ROS needed):

```bash
scripts/run.sh python -m pytest src/hand_tracking/test/test_filters.py \
    src/hand_tracking/test/test_hand_math.py -v
```

Bag-replay invariants (needs a recorded bag; skips otherwise):

```bash
scripts/record_handbag.sh 30
scripts/run.sh python -m pytest src/hand_tracking/test/test_bag_replay.py -v
```

## Docs

- [docs/environment.md](docs/environment.md) — the two-Python-environments setup and why it looks like that

## License

[MIT](LICENSE)
