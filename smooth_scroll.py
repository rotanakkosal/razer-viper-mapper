"""
Smooth Scrolling Engine for Razer Viper Mini
Replaces the mouse wheel's discrete "notchy" scroll ticks with an animated,
momentum-based stream of pixel-precise scroll events — the same idea as
Mac Mouse Fix's smooth scrolling.

How it works:
  1. The CGEventTap suppresses each physical wheel tick (line-based, discrete).
  2. Each tick adds scroll distance to an animation target. Spinning the wheel
     quickly multiplies the distance (acceleration), which gives momentum.
  3. A 60 fps animation thread posts synthetic pixel-unit scroll events that
     ease out toward the target, so content glides instead of jumping.

Synthetic events are tagged via the event's user-data field so the event tap
can recognize and ignore them (no feedback loop).
"""

import threading
import time

from Quartz import (
    CGEventCreateScrollWheelEvent,
    CGEventSetIntegerValueField,
    CGEventPost,
    kCGScrollEventUnitPixel,
    kCGSessionEventTap,
    kCGScrollWheelEventIsContinuous,
    kCGEventSourceUserData,
)

# Marker written into synthetic events' user-data field ("RVSS" in hex)
SMOOTH_SCROLL_EVENT_TAG = 0x52565353

_FRAME_INTERVAL = 1.0 / 60.0
_BASE_PIXELS_PER_TICK = 45.0
# Ticks arriving faster than this (seconds apart) get an acceleration boost
_ACCEL_THRESHOLD = 0.09
_ACCEL_MAX = 4.0


class SmoothScroller:
    """
    Converts discrete wheel ticks into smooth, eased pixel scrolling.

    Args:
        speed: Multiplier on scroll distance per wheel tick (0.1 – 5.0).
        smoothness: Fraction of remaining distance kept each frame (0.3 – 0.95).
                    Higher = longer, floatier glide; lower = snappier.

    Usage (from the event tap callback, on a physical wheel tick):
        scroller.add_ticks(delta)   # delta: +1 scroll up, -1 scroll down
        # ...and suppress the original event.
    """

    def __init__(self, speed: float = 1.0, smoothness: float = 0.78):
        self.speed = speed
        self.smoothness = smoothness
        self._target = 0.0      # remaining pixels to scroll (signed)
        self._remainder = 0.0   # sub-pixel carry between frames
        self._last_tick_time = 0.0
        self._lock = threading.Lock()
        self._running = False

    def configure(self, speed: float = None, smoothness: float = None):
        """Update settings (values are clamped to sane ranges)."""
        if speed is not None:
            self.speed = max(0.1, min(5.0, float(speed)))
        if smoothness is not None:
            self.smoothness = max(0.3, min(0.95, float(smoothness)))

    def add_ticks(self, delta: int):
        """Feed one physical wheel event (delta = signed line count)."""
        now = time.monotonic()
        with self._lock:
            interval = now - self._last_tick_time
            self._last_tick_time = now

            accel = 1.0
            if 0 < interval < _ACCEL_THRESHOLD:
                accel = min(_ACCEL_MAX, _ACCEL_THRESHOLD / max(interval, 0.01))

            distance = delta * _BASE_PIXELS_PER_TICK * self.speed * accel

            # Direction reversal kills any leftover glide immediately
            if self._target * distance < 0:
                self._target = 0.0
                self._remainder = 0.0

            self._target += distance

            if not self._running:
                self._running = True
                threading.Thread(target=self._animate, daemon=True).start()

    def stop(self):
        """Cancel any in-flight glide."""
        with self._lock:
            self._target = 0.0
            self._remainder = 0.0

    def _animate(self):
        """60 fps ease-out animation loop. Exits when the glide settles."""
        while True:
            time.sleep(_FRAME_INTERVAL)
            with self._lock:
                step = self._target * (1.0 - self.smoothness)
                self._target -= step

                done = abs(self._target) < 0.5 and abs(step) < 0.5
                if done:
                    step += self._target
                    self._target = 0.0

                step += self._remainder
                pixels = int(step)
                self._remainder = step - pixels

                if done:
                    self._remainder = 0.0
                    self._running = False

            if pixels:
                self._post(pixels)
            if done:
                return

    def _post(self, pixels: int):
        """Post one synthetic pixel-unit scroll event (positive = up)."""
        event = CGEventCreateScrollWheelEvent(
            None, kCGScrollEventUnitPixel, 1, pixels
        )
        CGEventSetIntegerValueField(event, kCGScrollWheelEventIsContinuous, 1)
        CGEventSetIntegerValueField(event, kCGEventSourceUserData,
                                    SMOOTH_SCROLL_EVENT_TAG)
        CGEventPost(kCGSessionEventTap, event)
