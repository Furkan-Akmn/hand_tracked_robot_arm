"""Integration test over a recorded /hand/state rosbag.

A bag is the project's deterministic memory of real hand motion: record one
with ``scripts/record_handbag.sh`` (or point ``HAND_BAG_DIR`` at one), and
every downstream change can be validated against identical input.

Skips automatically when there is no bag and/or no built interface package.
"""
import math
import os
from pathlib import Path

import pytest

rosbag2_py = pytest.importorskip("rosbag2_py")
pytest.importorskip("rclpy.serialization")

from rclpy.serialization import deserialize_message  # noqa: E402

try:
    from arm_teleop_interfaces.msg import HandState  # noqa: E402
except ImportError:
    pytest.skip("arm_teleop_interfaces not built/sourced - run scripts/build.sh",
                allow_module_level=True)


def _bag_dir() -> Path:
    env = os.environ.get("HAND_BAG_DIR")
    if env:
        return Path(env)
    repo_root = Path(__file__).resolve().parents[3]
    bags = sorted((repo_root / "bags").glob("hand_*"))
    if not bags:
        pytest.skip("no bag found - record one with scripts/record_handbag.sh")
    return bags[-1]


def _load_states() -> list:
    path = _bag_dir()
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(path), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions(input_serialization_format="cdr",
                                    output_serialization_format="cdr"),
    )
    states = []
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic == "/hand/state":
            states.append(deserialize_message(data, HandState))
    return states


def test_bag_contains_state_messages():
    assert _load_states(), "bag has no /hand/state messages"


def test_message_invariants():
    states = _load_states()
    detected_count = 0
    for s in states:
        assert len(s.landmarks) == 63
        if s.detected:
            detected_count += 1
            q = s.palm_orientation
            norm = math.sqrt(q.x ** 2 + q.y ** 2 + q.z ** 2 + q.w ** 2)
            assert 0.9 < norm < 1.1
            assert 0.0 <= s.confidence <= 1.0
            assert -0.5 <= s.pinch <= 3.0
            assert -0.5 <= s.palm_center.x <= 1.5
            assert -0.5 <= s.palm_center.y <= 1.5
        else:
            # contract: zeroed fields, identity quaternion
            assert s.confidence == 0.0
            assert s.palm_center.x == 0.0 and s.palm_center.y == 0.0
            assert s.palm_orientation.w == 1.0
    print(f"detection rate in this bag: {detected_count / len(states):.0%}")


def test_timestamps_are_monotonic():
    stamps = []
    for s in _load_states():
        stamps.append(s.header.stamp.sec + s.header.stamp.nanosec * 1e-9)
    assert all(b >= a for a, b in zip(stamps, stamps[1:]))
