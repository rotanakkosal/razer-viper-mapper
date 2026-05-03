"""
Mouse Detection Module for Razer Viper Mini
Uses macOS CGEventTap at the HID level to intercept all mouse button events.

The Razer Viper Mini 4 firmware sends side buttons as keyboard events
(Page Up / Page Down) rather than standard mouse button 4/5 events.
This module handles both standard mouse buttons and these keyboard-mapped
side buttons.

Requires Accessibility + Input Monitoring permissions:
  System Preferences → Privacy & Security → Accessibility
  System Preferences → Privacy & Security → Input Monitoring
"""

import threading
import time
from typing import Callable, Optional

import Quartz
from Quartz import (
    CGEventTapCreate,
    CGEventTapEnable,
    CGEventGetIntegerValueField,
    CGEventGetType,
    CFMachPortCreateRunLoopSource,
    CFRunLoopGetCurrent,
    CFRunLoopAddSource,
    CFRunLoopRun,
    CFRunLoopStop,
    kCGHIDEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionDefault,
    kCGEventTapOptionListenOnly,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGEventRightMouseDown,
    kCGEventRightMouseUp,
    kCGEventOtherMouseDown,
    kCGEventOtherMouseUp,
    kCGEventScrollWheel,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGMouseEventButtonNumber,
    kCGScrollWheelEventDeltaAxis1,
    kCGKeyboardEventKeycode,
)


_CGEVENT_TAP_DISABLED_BY_TIMEOUT = 0xFFFFFFFE
_CGEVENT_TAP_DISABLED_BY_USER = 0xFFFFFFFF

BUTTON_LEFT = "left_click"
BUTTON_RIGHT = "right_click"
BUTTON_MIDDLE = "middle_click"
BUTTON_SIDE_BACK = "side_back"
BUTTON_SIDE_FORWARD = "side_forward"
BUTTON_SCROLL_UP = "scroll_up"
BUTTON_SCROLL_DOWN = "scroll_down"

BUTTON_NAMES = {
    BUTTON_LEFT: "Left Click",
    BUTTON_RIGHT: "Right Click",
    BUTTON_MIDDLE: "Middle Click (Scroll Wheel)",
    BUTTON_SIDE_BACK: "Side Button (Back)",
    BUTTON_SIDE_FORWARD: "Side Button (Forward)",
    BUTTON_SCROLL_UP: "Scroll Up",
    BUTTON_SCROLL_DOWN: "Scroll Down",
}

REMAPPABLE_BUTTONS = [
    BUTTON_MIDDLE,
    BUTTON_SIDE_BACK,
    BUTTON_SIDE_FORWARD,
    BUTTON_SCROLL_UP,
    BUTTON_SCROLL_DOWN,
]

ALL_BUTTONS = [
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_MIDDLE,
    BUTTON_SIDE_BACK,
    BUTTON_SIDE_FORWARD,
    BUTTON_SCROLL_UP,
    BUTTON_SCROLL_DOWN,
]

# Razer Viper Mini 4 sends side buttons as keyboard keycodes.
# keycode 116 = Page Up (Back), keycode 121 = Page Down (Forward)
SIDE_BUTTON_KEYCODES = {
    116: BUTTON_SIDE_FORWARD,
    121: BUTTON_SIDE_BACK,
}


class MouseDetector:
    """
    Detects Razer Viper Mini mouse button presses using macOS CGEventTap
    at the HID (hardware) level.

    Handles both standard mouse buttons AND keyboard-mapped side buttons
    (Razer Viper Mini 4 sends side buttons as Page Up/Page Down keycodes).

    Args:
        on_button_press: Callback function(button_id: str, event_type: str)
        listen_only: If True, events pass through unmodified (for detection UI).
                     If False, events can be intercepted/suppressed for remapping.
        on_intercept: Optional callback for remapping mode. Returns True to suppress
                      the original event, False to let it pass through.
    """

    def __init__(
        self,
        on_button_press: Callable[[str, str], None],
        listen_only: bool = True,
        on_intercept: Optional[Callable[[str, str], bool]] = None,
    ):
        self.on_button_press = on_button_press
        self.listen_only = listen_only
        self.on_intercept = on_intercept
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._run_loop = None
        self._tap = None
        # Razer Viper Mini 4 sends a phantom left click alongside side button
        # keyboard events. Track side button timestamps to suppress these.
        self._last_side_button_time: float = 0
        self._side_button_debounce_ms: float = 100

    def _event_callback(self, proxy, event_type, event, refcon):
        """CGEventTap callback — called for every event at the HID level."""
        actual_type = CGEventGetType(event)
        if actual_type != event_type:
            event_type = actual_type

        # macOS disables taps that respond too slowly. Re-enable immediately.
        if event_type == _CGEVENT_TAP_DISABLED_BY_TIMEOUT:
            print("[MouseDetector] Tap was disabled by timeout — re-enabling...")
            if self._tap:
                CGEventTapEnable(self._tap, True)
            return event

        if event_type in (kCGEventKeyDown, kCGEventKeyUp):
            kc = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            print(f"[DEBUG] Keyboard event_type={event_type} keycode={kc}")

        button_id = None
        ev_type = "down"
        suppress = False

        if event_type in (kCGEventLeftMouseDown, kCGEventLeftMouseUp):
            elapsed = (time.time() - self._last_side_button_time) * 1000
            if elapsed < self._side_button_debounce_ms:
                return None if not self.listen_only else event
            button_id = BUTTON_LEFT
            ev_type = "down" if event_type == kCGEventLeftMouseDown else "up"

        elif event_type in (kCGEventRightMouseDown, kCGEventRightMouseUp):
            button_id = BUTTON_RIGHT
            ev_type = "down" if event_type == kCGEventRightMouseDown else "up"

        elif event_type in (kCGEventOtherMouseDown, kCGEventOtherMouseUp):
            btn_number = CGEventGetIntegerValueField(event, kCGMouseEventButtonNumber)
            ev_type = "down" if event_type == kCGEventOtherMouseDown else "up"

            if btn_number == 2:
                button_id = BUTTON_MIDDLE
            elif btn_number in (3, 5):
                button_id = BUTTON_SIDE_BACK
            elif btn_number in (4, 6):
                button_id = BUTTON_SIDE_FORWARD

        elif event_type == kCGEventScrollWheel:
            delta = CGEventGetIntegerValueField(event, kCGScrollWheelEventDeltaAxis1)
            if delta > 0:
                button_id = BUTTON_SCROLL_UP
            elif delta < 0:
                button_id = BUTTON_SCROLL_DOWN
            ev_type = "scroll"

        elif event_type in (kCGEventKeyDown, kCGEventKeyUp):
            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            if keycode in SIDE_BUTTON_KEYCODES:
                button_id = SIDE_BUTTON_KEYCODES[keycode]
                ev_type = "down" if event_type == kCGEventKeyDown else "up"
                self._last_side_button_time = time.time()
                # Always suppress both KeyDown and KeyUp for side button keycodes
                # when remapping is active, to prevent the original Page Up/Down
                # from interfering with the mapped shortcut.
                if not self.listen_only:
                    suppress = True

        if button_id:
            try:
                self.on_button_press(button_id, ev_type)
            except Exception as e:
                print(f"[MouseDetector] Callback error: {e}")

            if not self.listen_only and self.on_intercept:
                try:
                    intercept_result = self.on_intercept(button_id, ev_type)
                    suppress = suppress or intercept_result
                except Exception as e:
                    print(f"[MouseDetector] Intercept error: {e}")

        if suppress:
            return None
        return event

    def _run_tap(self):
        """Run the event tap in a background thread."""
        event_mask = (
            (1 << kCGEventLeftMouseDown)
            | (1 << kCGEventLeftMouseUp)
            | (1 << kCGEventRightMouseDown)
            | (1 << kCGEventRightMouseUp)
            | (1 << kCGEventOtherMouseDown)
            | (1 << kCGEventOtherMouseUp)
            | (1 << kCGEventScrollWheel)
            | (1 << kCGEventKeyDown)
            | (1 << kCGEventKeyUp)
        )

        tap_option = (
            kCGEventTapOptionListenOnly if self.listen_only
            else kCGEventTapOptionDefault
        )

        self._tap = CGEventTapCreate(
            kCGHIDEventTap,
            kCGHeadInsertEventTap,
            tap_option,
            event_mask,
            self._event_callback,
            None,
        )

        if self._tap is None:
            print(
                "\n[MouseDetector] ERROR: Failed to create event tap!\n"
                "Make sure you have granted Accessibility + Input Monitoring permissions:\n"
                "  System Settings → Privacy & Security → Accessibility\n"
                "  System Settings → Privacy & Security → Input Monitoring\n"
            )
            self._running = False
            return

        source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        self._run_loop = CFRunLoopGetCurrent()
        CFRunLoopAddSource(self._run_loop, source, Quartz.kCFRunLoopCommonModes)

        CGEventTapEnable(self._tap, True)

        print("[MouseDetector] HID event tap started. Listening for mouse + keyboard events...")
        self._running = True

        CFRunLoopRun()

        print("[MouseDetector] Event tap stopped.")

    def start(self):
        """Start listening for mouse events in a background thread."""
        if self._running:
            print("[MouseDetector] Already running.")
            return

        self._thread = threading.Thread(target=self._run_tap, daemon=True)
        self._thread.start()

        time.sleep(0.5)
        if not self._running:
            print("[MouseDetector] Failed to start. Check permissions.")

    def stop(self):
        """Stop listening for mouse events."""
        if not self._running:
            return

        self._running = False
        if self._tap:
            CGEventTapEnable(self._tap, False)
        if self._run_loop:
            CFRunLoopStop(self._run_loop)
        if self._thread:
            self._thread.join(timeout=2.0)

        print("[MouseDetector] Stopped.")

    @property
    def is_running(self):
        return self._running
