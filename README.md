# hand_tracked_robot_arm

Teleoperation of a robot arm inside an **isolated experiment box** (glovebox,
biosafety cabinet, anaerobic chamber) by **tracking the operator's bare hand**:
a camera watches the hand, and the arm inside the box mimics the motion.

Because control is vision-based, there is no leader arm and no need to reach
into the box — and since all electronics except the arm can live outside the
box, the hardware stays out of the sterilization problem.

## Status

**M0 — environment + scaffold ✅**
The webcam → MediaPipe → skeleton pipeline runs locally. No ROS 2 nodes yet.

## Quickstart (M0)

Prerequisites: Ubuntu 24.04 with ROS 2 Jazzy and a webcam.

```bash
scripts/setup.sh   # one-time: apt packages + venv + mediapipe model
scripts/run.sh     # live demo: 21-point hand skeleton on your webcam feed
```

Press `q` (or Esc) to quit the demo window.

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
- [ ] **M1** — `hand_tracking` ROS 2 node publishing `/hand/state` + rosbag capture/replay
- [ ] **M2** — UR5e + Robotiq live in Gazebo, MoveIt Servo bring-up
- [ ] **M3** — `teleop_mapping` node: wave hand → arm moves (watchdog + clamps verified)
- [ ] **M4** — tests (pytest + bag replay), docs, demo GIF
- [ ] **M5** — VR input (OpenXR) publishing the same `/hand/state` interface

## Design principles

- **Input abstraction** — webcam today, VR headset later; both publish the same interface.
- **Simulation-first** — the full pipeline is validated in Gazebo before any hardware exists.
- **Safety by construction** — watchdog on tracking loss, workspace clamping, rate limiting from day one.

## Docs

- [docs/environment.md](docs/environment.md) — the two-Python-environments setup and why it looks like that

## License

[MIT](LICENSE)
