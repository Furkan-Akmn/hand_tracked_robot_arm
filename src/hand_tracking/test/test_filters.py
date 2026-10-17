"""Unit tests for hand_tracking.filters (pure Python, no ROS, no camera)."""
import math
import random
import statistics

import pytest

from hand_tracking.filters import OneEuroFilter, VectorOneEuro


def test_first_sample_passes_through():
    f = OneEuroFilter()
    assert f(0.42, 0.0) == 0.42


def test_smoothing_reduces_noise_on_static_signal():
    f = OneEuroFilter(min_cutoff=1.0, beta=4.0)
    rng = random.Random(0)
    out = [f(0.5 + rng.uniform(-0.02, 0.02), i / 30.0) for i in range(300)]
    noise_std = 0.02 / math.sqrt(3.0)  # std of uniform(-0.02, 0.02)
    smoothed_std = statistics.pstdev(out[100:])
    assert smoothed_std < noise_std / 2.0


def test_low_lag_on_fast_motion():
    f = OneEuroFilter(min_cutoff=1.0, beta=4.0)
    for i in range(60):
        f(0.0, i / 30.0)  # hand at rest
    out = f(1.0, 2.0)     # sudden big jump
    assert out > 0.3      # already moved a good fraction toward the target


def test_non_monotonic_timestamps_are_safe():
    f = OneEuroFilter()
    f(0.1, 0.0)
    v1 = f(0.2, 0.0)      # dt == 0
    v2 = f(0.3, -0.5)     # dt < 0
    assert math.isfinite(v1) and math.isfinite(v2)


def test_reset_clears_state():
    f = OneEuroFilter()
    f(0.0, 0.0)
    f(1.0, 0.1)
    f.reset()
    assert f(0.7, 0.2) == 0.7


def test_vector_filter_is_channel_wise_and_size_checked():
    vf = VectorOneEuro(3)
    assert vf([1.0, 2.0, 3.0], 0.0) == [1.0, 2.0, 3.0]
    with pytest.raises(ValueError):
        vf([1.0], 0.1)
