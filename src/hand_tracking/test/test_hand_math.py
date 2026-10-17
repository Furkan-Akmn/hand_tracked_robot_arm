"""Unit tests for hand_tracking.hand_math (pure Python, no ROS, no camera)."""
import math

from hand_tracking import hand_math as hm


def make_hand(wrist=(0.5, 0.9, 0.0), index_mcp=(0.40, 0.60, 0.0),
              middle_mcp=(0.50, 0.55, 0.0), ring_mcp=(0.58, 0.60, 0.0),
              pinky_mcp=(0.64, 0.64, 0.0),
              thumb_tip=(0.45, 0.70, 0.0), index_tip=(0.55, 0.70, 0.0)):
    """Build a 21-point synthetic hand with the given landmark positions."""
    pts = [(0.5, 0.5, 0.0)] * 21
    pts[hm.WRIST] = wrist
    pts[hm.INDEX_MCP] = index_mcp
    pts[hm.MIDDLE_MCP] = middle_mcp
    pts[hm.RING_MCP] = ring_mcp
    pts[hm.PINKY_MCP] = pinky_mcp
    pts[hm.THUMB_TIP] = thumb_tip
    pts[hm.INDEX_TIP] = index_tip
    return pts


def test_pinch_ratio_open_vs_closed():
    closed = make_hand(thumb_tip=(0.50, 0.65, 0.0), index_tip=(0.51, 0.65, 0.0))
    open_hand = make_hand(thumb_tip=(0.35, 0.50, 0.0), index_tip=(0.65, 0.50, 0.0))
    r_closed = hm.pinch_ratio(closed)
    r_open = hm.pinch_ratio(open_hand)
    assert r_closed < 0.2
    assert r_open > 0.6
    assert r_open > r_closed


def test_pinch_ratio_degenerate_hand_is_zero():
    pts = [(0.5, 0.5, 0.0)] * 21  # everything identical
    assert hm.pinch_ratio(pts) == 0.0


def test_palm_center_is_average_of_palm_landmarks():
    pts = make_hand()
    cx, cy, cz = hm.palm_center(pts)
    n = len(hm.PALM_INDICES)
    manual_x = sum(pts[i][0] for i in hm.PALM_INDICES) / n
    assert abs(cx - manual_x) < 1e-12
    xs = [pts[i][0] for i in hm.PALM_INDICES]
    assert min(xs) <= cx <= max(xs)


def test_palm_frame_known_configuration_is_180deg_about_z():
    # wrist -> middle points up (-y), pinky -> index points left (-x).
    pts = make_hand(wrist=(0.5, 0.9, 0.0), middle_mcp=(0.5, 0.5, 0.0),
                    index_mcp=(0.4, 0.6, 0.0), pinky_mcp=(0.6, 0.6, 0.0))
    q = hm.palm_frame(pts)
    assert abs(q[0]) < 1e-6 and abs(q[1]) < 1e-6
    assert abs(q[2] - 1.0) < 1e-6 and abs(q[3]) < 1e-6


def test_palm_frame_is_unit_quaternion_across_poses():
    for i in range(8):
        angle = i * math.pi / 8.0
        pts = make_hand(
            wrist=(0.5, 0.9, 0.0),
            middle_mcp=(0.5 + 0.2 * math.cos(angle),
                        0.5 + 0.2 * math.sin(angle), 0.0),
            index_mcp=(0.4, 0.6, 0.1 * i),
            pinky_mcp=(0.6, 0.6, -0.1 * i),
        )
        q = hm.palm_frame(pts)
        norm = math.sqrt(sum(c * c for c in q))
        assert abs(norm - 1.0) < 1e-9


def test_palm_frame_degenerate_points_give_identity():
    pts = [(0.5, 0.5, 0.0)] * 21
    assert hm.palm_frame(pts) == (0.0, 0.0, 0.0, 1.0)


def test_flatten_layout_matches_message():
    pts = [(0.1 * i, 0.2 * i, 0.3 * i) for i in range(21)]
    flat = hm.flatten(pts)
    assert len(flat) == 63
    assert flat[0:3] == [0.0, 0.0, 0.0]
    assert flat[60:63] == [2.0, 4.0, 6.0]
