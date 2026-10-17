"""Pure landmark math: MediaPipe hand landmarks -> teleop control signals.

Input is a sequence of 21 ``(x, y, z)`` points in *mirrored* normalized image
coordinates (x: 0 left -> 1 right on screen, y: 0 top -> 1 bottom; z is
MediaPipe's relative depth, roughly the same scale as x/y).

No ROS and no numpy on purpose -> unit-testable anywhere.
"""
from __future__ import annotations

import math

# MediaPipe hand-landmark indices used here.
WRIST = 0
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_TIP = 8
MIDDLE_MCP = 9
RING_MCP = 13
PINKY_MCP = 17

# Landmarks averaged for the palm center.
PALM_INDICES = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def distance(a, b) -> float:
    """Euclidean distance between two 3D points."""
    return _norm(_sub(a, b))


def pinch_ratio(landmarks) -> float:
    """Thumb-tip to index-tip distance, normalized by palm size.

    Hand-scale invariant: ~0.05 when the fingers touch, ~0.8+ for a fully
    open hand. Not a gesture - the mapping layer applies thresholds.
    """
    scale = distance(landmarks[WRIST], landmarks[MIDDLE_MCP])
    if scale < 1e-6:
        return 0.0
    return distance(landmarks[THUMB_TIP], landmarks[INDEX_TIP]) / scale


def palm_center(landmarks):
    """Average of the wrist and the four MCP knuckles (a stable hand center)."""
    n = len(PALM_INDICES)
    x = sum(landmarks[i][0] for i in PALM_INDICES) / n
    y = sum(landmarks[i][1] for i in PALM_INDICES) / n
    z = sum(landmarks[i][2] for i in PALM_INDICES) / n
    return (x, y, z)


def quaternion_from_matrix(m):
    """Rotation matrix (row-major 3x3 iterable) -> unit quaternion (x,y,z,w)."""
    m00, m01, m02 = m[0]
    m10, m11, m12 = m[1]
    m20, m21, m22 = m[2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (m21 - m12) / s
        y = (m02 - m20) / s
        z = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s
    return normalize_quaternion((x, y, z, w))


def normalize_quaternion(q):
    """Return ``q`` scaled to unit length (identity for degenerate input)."""
    n = math.sqrt(sum(c * c for c in q))
    if n < 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def palm_frame(landmarks):
    """Palm orientation as a unit quaternion ``(x, y, z, w)``.

    Frame definition (roughly aligned with the camera axes):
      y: wrist -> middle MCP (up the hand)
      x: pinky MCP -> index MCP (across the palm, index side)
      z: x cross y

    Falls back to the identity quaternion for degenerate inputs.
    """
    vy = _sub(landmarks[MIDDLE_MCP], landmarks[WRIST])
    ny = _norm(vy)
    if ny < 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    vy = _scale(vy, 1.0 / ny)

    vx = _sub(landmarks[INDEX_MCP], landmarks[PINKY_MCP])
    vx = _sub(vx, _scale(vy, _dot(vx, vy)))  # Gram-Schmidt against y
    nx = _norm(vx)
    if nx < 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    vx = _scale(vx, 1.0 / nx)

    vz = _cross(vx, vy)
    # Columns are the frame axes expressed in camera coordinates.
    m = ((vx[0], vy[0], vz[0]),
         (vx[1], vy[1], vz[1]),
         (vx[2], vy[2], vz[2]))
    return quaternion_from_matrix(m)


def as_tuples(hand_landmarks):
    """MediaPipe NormalizedLandmark list -> plain ``(x, y, z)`` tuples."""
    return [(lm.x, lm.y, lm.z) for lm in hand_landmarks]


def flatten(landmarks) -> list[float]:
    """21 ``(x, y, z)`` points -> flat 63-float list (message layout)."""
    return [c for p in landmarks for c in p]
