"""Quick test: can a fresh event tap receive keyboard events?
Press any key or side button within 8 seconds."""
import time, threading
from Quartz import *

got_keyboard = []
got_mouse = []

def cb(proxy, etype, event, refcon):
    actual = CGEventGetType(event)
    if actual in (kCGEventKeyDown, kCGEventKeyUp):
        kc = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
        got_keyboard.append((actual, kc))
        print(f"  KEYBOARD: type={actual} keycode={kc}", flush=True)
    elif actual in (kCGEventLeftMouseDown, kCGEventLeftMouseUp):
        got_mouse.append(actual)
        print(f"  MOUSE: type={actual}", flush=True)
    return event

mask = ((1 << kCGEventKeyDown) | (1 << kCGEventKeyUp) |
        (1 << kCGEventLeftMouseDown) | (1 << kCGEventLeftMouseUp))

tap = CGEventTapCreate(kCGHIDEventTap, kCGHeadInsertEventTap,
                       kCGEventTapOptionListenOnly, mask, cb, None)
if not tap:
    print("FAILED to create tap")
else:
    print("Tap created. Press side button + any keyboard key within 8s...", flush=True)
    src = CFMachPortCreateRunLoopSource(None, tap, 0)
    loop = CFRunLoopGetCurrent()
    CFRunLoopAddSource(loop, src, kCFRunLoopCommonModes)
    CGEventTapEnable(tap, True)

    def stop():
        time.sleep(8)
        CFRunLoopStop(loop)
    threading.Thread(target=stop, daemon=True).start()
    CFRunLoopRun()

    print(f"\nResult: {len(got_keyboard)} keyboard events, {len(got_mouse)} mouse events")
    if not got_keyboard:
        print("CONFIRMED: System is blocking keyboard events from event taps")
    else:
        print("Keyboard events work fine — issue is in the Flask app")
