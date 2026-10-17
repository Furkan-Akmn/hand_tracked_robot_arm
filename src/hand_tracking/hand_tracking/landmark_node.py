#!/usr/bin/env python3
"""ROS 2 node: webcam hand tracking -> arm_teleop_interfaces/HandState.

Pipeline:
  OpenCV capture -> horizontal mirror -> MediaPipe HandLandmarker (VIDEO mode)
  -> landmark math (palm center/orientation, pinch) -> One-Euro filtering
  -> /hand/state          control signals for teleop_mapping (M3)
  -> /hand/debug_image    annotated frame, throttled (for rqt / debugging)

This is the ONLY node in the project that needs MediaPipe. Everything
downstream consumes /hand/state, so the input source can later be swapped
(e.g. a VR runtime) without touching the mapping layer.
"""
from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp
import rclpy
from geometry_msgs.msg import Point, Quaternion
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image

from arm_teleop_interfaces.msg import HandState
from hand_tracking import hand_math
from hand_tracking.filters import OneEuroFilter, VectorOneEuro

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),          # index
    (5, 9), (9, 10), (10, 11), (11, 12),     # middle
    (9, 13), (13, 14), (14, 15), (15, 16),   # ring
    (13, 17), (17, 18), (18, 19), (19, 20),  # pinky
    (0, 17),                                 # palm base
]

BONE_COLOR = (80, 220, 80)
JOINT_COLOR = (255, 255, 255)
WINDOW_NAME = "hand_tracking (q or Esc to quit)"

# Overridable by scripts/run.sh; falls back to a repo-relative path.
DEFAULT_MODEL = os.environ.get("HAND_TRACKING_MODEL", "models/hand_landmarker.task")


def _draw_skeleton(frame, points) -> None:
    """Draw a 21-point skeleton (normalized coords) onto a BGR frame in place."""
    h, w = frame.shape[:2]
    pix = [(int(x * w), int(y * h)) for x, y, _ in points]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pix[a], pix[b], BONE_COLOR, 2, cv2.LINE_AA)
    for p in pix:
        cv2.circle(frame, p, 4, JOINT_COLOR, -1, cv2.LINE_AA)
        cv2.circle(frame, p, 4, BONE_COLOR, 1, cv2.LINE_AA)


class HandTrackingNode(Node):
    def __init__(self) -> None:
        super().__init__("hand_tracking")

        self.declare_parameter("camera", 0)
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("model_path", DEFAULT_MODEL)
        self.declare_parameter("show_window", False)
        self.declare_parameter("debug_image", True)
        self.declare_parameter("debug_image_rate", 10.0)
        self.declare_parameter("min_cutoff", 1.0)
        self.declare_parameter("beta", 4.0)
        self.declare_parameter("d_cutoff", 1.0)
        self.declare_parameter("hand_lost_reset_s", 0.5)

        self._camera = int(self.get_parameter("camera").value)
        self._width = int(self.get_parameter("width").value)
        self._height = int(self.get_parameter("height").value)
        self._show_window = bool(self.get_parameter("show_window").value)
        self._debug_enabled = bool(self.get_parameter("debug_image").value)
        debug_rate = float(self.get_parameter("debug_image_rate").value)
        self._debug_period = (1.0 / debug_rate) if debug_rate > 0.0 else 0.0
        self._hand_lost_reset_s = float(self.get_parameter("hand_lost_reset_s").value)

        model_path = Path(str(self.get_parameter("model_path").value))
        if not model_path.exists():
            raise RuntimeError(
                f"hand-landmarker model not found at '{model_path}' - run "
                "scripts/setup.sh, or pass model_path:=/path/to/hand_landmarker.task")

        smoothing = dict(
            min_cutoff=float(self.get_parameter("min_cutoff").value),
            beta=float(self.get_parameter("beta").value),
            d_cutoff=float(self.get_parameter("d_cutoff").value),
        )
        self._f_landmarks = VectorOneEuro(63, **smoothing)
        self._f_center = VectorOneEuro(3, **smoothing)
        self._f_orientation = VectorOneEuro(4, **smoothing)
        self._f_pinch = OneEuroFilter(**smoothing)

        self._pub_state = self.create_publisher(HandState, "hand/state", 10)
        self._pub_debug = self.create_publisher(
            Image, "hand/debug_image", qos_profile_sensor_data)

        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)

        self._cap = cv2.VideoCapture(self._camera)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open camera {self._camera}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        for _ in range(10):  # cameras often return garbage right after open
            ok, _ = self._cap.read()
            if ok:
                break

        self._last_seen: float | None = None
        self._last_debug = 0.0
        self._frames = 0
        self._detections = 0
        self._log_now = time.monotonic()
        self._quit = False

        self.get_logger().info(
            f"hand_tracking ready | camera={self._camera} "
            f"{self._width}x{self._height} | model={model_path} "
            f"| show_window={self._show_window}")

    # ------------------------------------------------------------------ helpers
    @property
    def quit_requested(self) -> bool:
        return self._quit

    def _reset_filters(self) -> None:
        self._f_landmarks.reset()
        self._f_center.reset()
        self._f_orientation.reset()
        self._f_pinch.reset()

    def _to_image_msg(self, frame, stamp) -> Image:
        msg = Image()
        msg.header.stamp = stamp
        msg.header.frame_id = "camera"
        msg.height, msg.width = frame.shape[:2]
        msg.encoding = "bgr8"
        msg.is_bigendian = 0
        msg.step = int(frame.shape[1] * 3)
        msg.data = frame.tobytes()
        return msg

    def _maybe_log(self, now: float) -> None:
        if now - self._log_now < 5.0:
            return
        dt = now - self._log_now
        rate = (self._detections / self._frames) if self._frames else 0.0
        self.get_logger().info(
            f"{self._frames / dt:.1f} fps | hand in {rate:.0%} of frames")
        self._frames = 0
        self._detections = 0
        self._log_now = now

    # --------------------------------------------------------------------- step
    def step(self) -> None:
        ok, frame = self._cap.read()
        if not ok:
            self.get_logger().error("camera read failed", throttle_duration_sec=5.0)
            return
        now = time.monotonic()
        self._frames += 1

        # Mirror so the operator's motion matches the on-screen motion
        # (selfie view); all published coordinates live in this space.
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_image, int(now * 1000))

        stamp = self.get_clock().now().to_msg()
        msg = HandState()
        msg.header.stamp = stamp
        msg.header.frame_id = "camera"

        viz_points = None
        if result.hand_landmarks:
            if self._last_seen is None or (now - self._last_seen) > self._hand_lost_reset_s:
                self._reset_filters()  # avoid a "catch-up" jump after re-acquisition
            self._last_seen = now
            self._detections += 1

            pts = hand_math.as_tuples(result.hand_landmarks[0])
            confidence = 1.0
            if result.handedness and result.handedness[0]:
                confidence = float(result.handedness[0][0].score)

            f_center = self._f_center(hand_math.palm_center(pts), now)
            f_quat = hand_math.normalize_quaternion(
                self._f_orientation(hand_math.palm_frame(pts), now))
            f_pinch = self._f_pinch(hand_math.pinch_ratio(pts), now)
            f_flat = self._f_landmarks(hand_math.flatten(pts), now)

            msg.detected = True
            msg.confidence = confidence
            msg.landmarks = [float(v) for v in hand_math.flatten(pts)]
            msg.palm_center = Point(
                x=float(f_center[0]), y=float(f_center[1]), z=float(f_center[2]))
            msg.palm_orientation = Quaternion(
                x=float(f_quat[0]), y=float(f_quat[1]),
                z=float(f_quat[2]), w=float(f_quat[3]))
            msg.pinch = float(f_pinch)
            viz_points = [(f_flat[i], f_flat[i + 1], f_flat[i + 2])
                          for i in range(0, 63, 3)]
        else:
            # detected=False: contract is "fields zeroed, quaternion identity".
            msg.detected = False
            msg.palm_orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)

        self._pub_state.publish(msg)

        need_debug = (self._debug_enabled
                      and (now - self._last_debug) >= self._debug_period)
        if need_debug or self._show_window:
            vis = frame.copy()
            if viz_points is not None:
                _draw_skeleton(vis, viz_points)
            label = (f"detected   pinch={msg.pinch:.2f}" if msg.detected
                     else "no hand")
            cv2.putText(vis, label, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (50, 50, 255), 2, cv2.LINE_AA)
            if need_debug:
                self._last_debug = now
                self._pub_debug.publish(self._to_image_msg(vis, stamp))
            if self._show_window:
                cv2.imshow(WINDOW_NAME, vis)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    self._quit = True

        self._maybe_log(now)

    def shutdown(self) -> None:
        self._cap.release()
        if self._show_window:
            cv2.destroyAllWindows()
        self._landmarker.close()


def main(args=None) -> None:
    # SignalHandlerOptions.NO: we handle SIGINT ourselves (plain KeyboardInterrupt)
    # so shutdown always runs to completion without being interrupted mid-way.
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    # POSIX shells start background jobs with SIGINT ignored, and Python keeps
    # an ignored SIGINT as-is at startup. Re-arm Ctrl+C explicitly so the node
    # also shuts down cleanly when started as a background job in a script.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        node = HandTrackingNode()
    except Exception as exc:  # startup problems should be loud, not a traceback wall
        print(f"[hand_tracking] startup failed: {exc}", file=sys.stderr)
        if rclpy.ok():
            rclpy.shutdown()
        raise SystemExit(1)

    try:
        while rclpy.ok() and not node.quit_requested:
            node.step()
            rclpy.spin_once(node, timeout_sec=0.0)
    except KeyboardInterrupt:
        print("[hand_tracking] SIGINT - shutting down", file=sys.stderr)
    finally:
        try:
            node.shutdown()
        except KeyboardInterrupt:
            # A second interrupt while releasing the camera (V4L2 streamoff can
            # block briefly). Exit cleanly anyway; the OS reclaims the device.
            print("[hand_tracking] shutdown interrupted; exiting", file=sys.stderr)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
