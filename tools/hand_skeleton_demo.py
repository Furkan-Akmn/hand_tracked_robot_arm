#!/usr/bin/env python3
"""Live hand-skeleton demo -- the M0 smoke test for this project.

Opens the laptop webcam, runs the MediaPipe *Tasks* HandLandmarker in VIDEO
mode, and draws the 21-point hand skeleton with OpenCV.

Deliberately has no ROS dependency: it proves camera + mediapipe + venv work
before any ROS 2 code exists. Run it through the project wrapper:

    scripts/run.sh                                    # windowed
    scripts/run.sh python tools/hand_skeleton_demo.py --headless 90
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = REPO_ROOT / "models" / "hand_landmarker.task"

# 21-landmark hand topology (MediaPipe convention).
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="camera index (default: 0)")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL,
                        help="path to hand_landmarker.task")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--headless", type=int, default=0, metavar="N",
                        help="process N frames without a window (smoke test / CI)")
    parser.add_argument("--save-frame", type=Path, default=None, metavar="PATH",
                        help="save an annotated frame as JPEG (handy with --headless)")
    return parser.parse_args()


def draw_hand(frame, landmarks) -> None:
    """Draw the 21 landmarks and their connections onto a BGR frame (in place)."""
    h, w = frame.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], BONE_COLOR, 2, cv2.LINE_AA)
    for p in pts:
        cv2.circle(frame, p, 4, JOINT_COLOR, -1, cv2.LINE_AA)
        cv2.circle(frame, p, 4, BONE_COLOR, 1, cv2.LINE_AA)


def main() -> None:
    args = parse_args()
    if not args.model.exists():
        raise SystemExit(f"model not found: {args.model}\nRun scripts/setup.sh first.")

    print(f"hand_skeleton_demo | camera={args.camera} at {args.width}x{args.height} "
          f"| model={args.model.name}")
    if args.headless == 0:
        print("A window will open - press q or Esc there to quit.")
    else:
        print(f"Headless mode: processing {args.headless} frames.")

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(args.model)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"could not open camera {args.camera}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    frame = None
    for _ in range(10):  # cameras often return garbage on the first reads after open
        ok, frame = cap.read()
        if ok:
            break

    frames = detections = 0
    saved = False
    start = last_fps = time.monotonic()
    fps = 0.0

    with vision.HandLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("warning: camera read failed")
                break

            frame = cv2.flip(frame, 1)  # mirror, so moving right moves right on screen
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(mp_image, int(time.monotonic() * 1000))

            frames += 1
            if result.hand_landmarks:
                detections += 1
                for hand in result.hand_landmarks:
                    draw_hand(frame, hand)

            now = time.monotonic()
            if now - last_fps >= 1.0:
                fps = frames / (now - start)
                last_fps = now

            n_lm = len(result.hand_landmarks[0]) if result.hand_landmarks else 0
            label = f"hand: {n_lm}/21 landmarks   {fps:4.1f} fps"
            cv2.putText(frame, label, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (50, 50, 255), 2, cv2.LINE_AA)

            if args.save_frame is not None and not saved and result.hand_landmarks:
                cv2.imwrite(str(args.save_frame), frame)
                saved = True

            if args.headless > 0:
                if frames >= args.headless:
                    break
            else:
                cv2.imshow("hand tracking (M0 demo) - press q to quit", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break

    elapsed = time.monotonic() - start
    cap.release()
    if args.headless == 0:
        cv2.destroyAllWindows()
    if args.save_frame is not None and not saved and frames:
        cv2.imwrite(str(args.save_frame), frame)

    if frames == 0:
        print("no frames captured")
        return
    print(f"frames={frames}  detection_rate={detections / frames:.0%}  "
          f"avg_fps={frames / elapsed:.1f}")
    if detections == 0:
        print("hint: no hand was detected - make sure a hand is visible in the "
              "camera and well lit.")


if __name__ == "__main__":
    main()
