"""Time-based signal filters for hand tracking.

The One-Euro filter (Casiez, Roussel & Vogel, CHI 2012) is the workhorse: an
adaptive low-pass filter designed exactly for noisy interactive signals such
as hand landmarks. It smooths strongly when the signal moves slowly (kills
tremor while the hand rests) and weakly when the signal moves fast (keeps lag
small during deliberate motion).

Pure Python on purpose: no ROS, no numpy -> unit-testable anywhere.
"""
from __future__ import annotations


class OneEuroFilter:
    """One-Euro filter for a single scalar signal."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 4.0,
                 d_cutoff: float = 1.0) -> None:
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x_prev: float | None = None
        self._dx_prev = 0.0
        self._t_prev: float | None = None

    def reset(self) -> None:
        """Drop state; the next sample passes through unfiltered."""
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * 3.141592653589793 * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x: float, t: float) -> float:
        """Filter sample ``x`` taken at monotonic timestamp ``t`` (seconds)."""
        x = float(x)
        if self._t_prev is None:
            self._t_prev, self._x_prev = t, x
            return x
        dt = t - self._t_prev
        if dt <= 0.0:
            dt = 1e-6  # guard against non-monotonic timestamps
        dx = (x - self._x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1.0 - a_d) * self._dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1.0 - a) * self._x_prev
        self._t_prev, self._x_prev, self._dx_prev = t, x_hat, dx_hat
        return x_hat


class VectorOneEuro:
    """One-Euro filter applied channel-wise to a fixed-size vector."""

    def __init__(self, size: int, **kwargs) -> None:
        self._filters = [OneEuroFilter(**kwargs) for _ in range(size)]

    def reset(self) -> None:
        for f in self._filters:
            f.reset()

    def __len__(self) -> int:
        return len(self._filters)

    def __call__(self, values, t: float) -> list[float]:
        values = list(values)
        if len(values) != len(self._filters):
            raise ValueError(
                f"expected {len(self._filters)} values, got {len(values)}")
        return [f(v, t) for f, v in zip(self._filters, values)]
