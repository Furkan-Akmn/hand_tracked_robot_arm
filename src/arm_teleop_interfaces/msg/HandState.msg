# One tracked hand, from the webcam, in mirrored image space.
#
# Contract for consumers (teleop_mapping, watchdog logic, future VR adapters):
#  - When `detected` is false, all numeric fields are zeroed (quaternion =
#    identity) and MUST be ignored. Consumers must also treat stale header
#    stamps as "no hand" (watchdog).
#  - Only check `detected` and the header stamp; nothing else is guaranteed.

std_msgs/Header header

# True when a hand is currently tracked.
bool detected

# MediaPipe handedness score of the tracked hand (0..1).
float32 confidence

# Raw MediaPipe landmarks: 21 * (x, y, z) normalized to the image, index-major.
# Mirrored space: x grows rightward on screen (0..1), y downward (0..1).
# z is MediaPipe's relative depth (roughly the same scale as x/y).
float32[63] landmarks

# Filtered palm position (One-Euro), normalized mirrored image coordinates.
geometry_msgs/Point palm_center

# Filtered palm orientation as a unit quaternion, roughly aligned with the
# camera axes (+x right, +y down, +z away from the camera).
geometry_msgs/Quaternion palm_orientation

# Pinch signal: thumb-tip to index-tip distance normalized by palm size
# (~0.05 = fingers touching, ~0.8+ = fully open hand). NOT a boolean -
# the mapping layer applies thresholds and hysteresis.
float32 pinch
