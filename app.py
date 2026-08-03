"""
Razer Viper Mini Button Mapper — Flask Backend
Serves the web UI and provides WebSocket communication for real-time mouse events.

Usage:
    python app.py

Then open http://localhost:8080 in your browser.
"""

import os
import sys
import threading
import time

from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit

from mouse_detector import (
    MouseDetector, ALL_BUTTONS, BUTTON_NAMES, REMAPPABLE_BUTTONS,
)
from remapper import Remapper, PRESET_SHORTCUTS, KEY_CODES
from smooth_scroll import SmoothScroller
from profiles import ProfileManager
from settings import Settings

# ── Flask app setup ──────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = "razer-viper-mini-mapper"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Core components ──────────────────────────────────────────────
settings = Settings()
remapper = Remapper()
profile_manager = ProfileManager()
scroller = SmoothScroller(
    speed=settings.section("scroll").get("speed", 1.0),
    smoothness=settings.section("scroll").get("smoothness", 0.78),
)
detector: MouseDetector = None
detection_active = False
remapping_active = False
smooth_scroll_active = False

# Minimum interval between shortcut executions for scroll-mapped buttons,
# so fast wheel spins don't fire dozens of osascript processes.
_SCROLL_EXEC_INTERVAL = 0.15
_last_scroll_exec: dict = {}


def _status_payload() -> dict:
    """Common status dict sent to the UI."""
    return {
        "detection_active": detection_active,
        "remapping_active": remapping_active,
        "smooth_scroll_active": smooth_scroll_active,
        "autostart_enabled": settings.section("autostart").get("enabled", False),
        "scroll_settings": {
            "speed": scroller.speed,
            "smoothness": scroller.smoothness,
        },
        "current_profile": profile_manager.current_profile_name,
    }


def _persist_runtime_state():
    """Remember the current mode + profile for the next background launch."""
    settings.update(
        "autostart",
        remapping=remapping_active,
        smooth_scroll=smooth_scroll_active,
        profile=profile_manager.current_profile_name,
    )


def _spawn_detector():
    """(Re)create and start the detector with the current mode flags."""
    global detector, detection_active
    listen_only = not (remapping_active or smooth_scroll_active)
    detector = MouseDetector(
        on_button_press=on_button_press,
        listen_only=listen_only,
        on_intercept=on_intercept if not listen_only else None,
        smooth_scroller=scroller if (smooth_scroll_active and not listen_only) else None,
    )
    detector.start()
    detection_active = detector.is_running


def _restart_detector_if_active():
    """Apply new mode flags by restarting a running detector."""
    global detector, detection_active
    if detection_active and detector:
        detector.stop()
        detection_active = False
        _spawn_detector()


def apply_autostart():
    """
    Restore saved state at launch so the app is useful with no browser open.
    Called once at startup — this is what makes background/LaunchAgent
    operation actually work.
    """
    global remapping_active, smooth_scroll_active
    auto = settings.section("autostart")

    profile_name = auto.get("profile")
    if profile_name:
        profile = profile_manager.load_profile(profile_name)
        if profile:
            remapper.load_mappings(profile.mappings)
            print(f"[App] Restored profile '{profile.name}'")
        else:
            print(f"[App] Saved profile '{profile_name}' not found — skipping")

    # Always mirror the saved modes into memory, even when autostart is off.
    # Otherwise the first UI toggle would persist these as False and quietly
    # forget your setup, and "Start Detection" would run without remapping.
    remapping_active = bool(auto.get("remapping"))
    smooth_scroll_active = bool(auto.get("smooth_scroll"))

    if not auto.get("enabled"):
        print("[App] Autostart off — idle until you start detection in the UI.")
        return

    _spawn_detector()

    if detection_active:
        modes = []
        if remapping_active:
            modes.append("remapping")
        if smooth_scroll_active:
            modes.append("smooth scrolling")
        print(f"[App] Autostart: detection running ({', '.join(modes) or 'detect only'})")
    else:
        print(
            "[App] Autostart FAILED to start detection.\n"
            "      Grant Accessibility + Input Monitoring to the binary that\n"
            "      launched this app, then restart it."
        )


# ── Mouse event callbacks ────────────────────────────────────────
def on_button_press(button_id: str, event_type: str):
    """Called when any mouse button is pressed. Streams to the UI via WebSocket."""
    socketio.emit("button_event", {
        "button_id": button_id,
        "event_type": event_type,
        "button_name": BUTTON_NAMES.get(button_id, button_id),
    })


def on_intercept(button_id: str, event_type: str) -> bool:
    """
    Called in remapping mode. Returns True to suppress the original event.
    Intercepts 'down' and 'scroll' events (not 'up') to avoid stuck states.
    """
    if not remapping_active:
        return False
    if event_type not in ("down", "scroll"):
        return False
    if remapper.should_intercept(button_id):
        if event_type == "scroll":
            now = time.time()
            if now - _last_scroll_exec.get(button_id, 0) < _SCROLL_EXEC_INTERVAL:
                return True  # suppress the tick, but don't re-fire the shortcut
            _last_scroll_exec[button_id] = now
        mapping = remapper.get_mapping(button_id)
        print(f"[App] Executing remap: {button_id} → {mapping.get('key')} + {mapping.get('modifiers')}")
        remapper.execute(button_id)
        return True
    return False


# ── Static file serving ──────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


# ── REST API endpoints ───────────────────────────────────────────
@app.route("/api/status")
def get_status():
    """Get current app status (same fields as the WebSocket 'status' event)."""
    return jsonify({
        **_status_payload(),
        "buttons": [
            {
                "id": bid,
                "name": BUTTON_NAMES.get(bid, bid),
                "remappable": bid in REMAPPABLE_BUTTONS,
                "mapping": remapper.get_mapping(bid),
            }
            for bid in ALL_BUTTONS
        ],
    })


@app.route("/api/presets")
def get_presets():
    """Get all available preset shortcuts."""
    return jsonify(PRESET_SHORTCUTS)


@app.route("/api/keycodes")
def get_keycodes():
    """Get all available key names for custom shortcuts."""
    return jsonify(sorted(KEY_CODES.keys()))


@app.route("/api/profiles", methods=["GET"])
def list_profiles():
    """List all saved profiles."""
    return jsonify(profile_manager.list_profiles())


@app.route("/api/profiles/<name>", methods=["GET"])
def get_profile(name):
    """Load a specific profile."""
    profile = profile_manager.load_profile(name)
    if profile:
        return jsonify(profile.to_dict())
    return jsonify({"error": "Profile not found"}), 404


@app.route("/api/profiles/<name>", methods=["DELETE"])
def delete_profile(name):
    """Delete a profile."""
    if profile_manager.delete_profile(name):
        return jsonify({"success": True})
    return jsonify({"error": "Profile not found"}), 404


# ── WebSocket event handlers ─────────────────────────────────────
@socketio.on("connect")
def handle_connect():
    print("[WebSocket] Client connected")
    emit("status", _status_payload())


@socketio.on("start_detection")
def handle_start_detection():
    """Start the mouse event detector."""
    if detection_active:
        emit("error", {"message": "Detection already active"})
        return

    _spawn_detector()
    emit("status", _status_payload())

    if detection_active:
        print("[App] Mouse detection started")
    else:
        emit("error", {
            "message": "Failed to start detection. Check Accessibility permissions."
        })


@socketio.on("stop_detection")
def handle_stop_detection():
    """Stop the mouse event detector."""
    global detector, detection_active
    if detector:
        detector.stop()
    detection_active = False
    scroller.stop()

    emit("status", _status_payload())
    print("[App] Mouse detection stopped")


@socketio.on("toggle_remapping")
def handle_toggle_remapping(data):
    """Enable or disable button remapping."""
    global remapping_active
    remapping_active = data.get("enabled", False)

    _restart_detector_if_active()
    _persist_runtime_state()
    emit("status", _status_payload())
    print(f"[App] Remapping {'enabled' if remapping_active else 'disabled'}")


@socketio.on("toggle_smooth_scroll")
def handle_toggle_smooth_scroll(data):
    """Enable or disable Mac-Mouse-Fix-style smooth scrolling."""
    global smooth_scroll_active
    smooth_scroll_active = data.get("enabled", False)
    if not smooth_scroll_active:
        scroller.stop()

    _restart_detector_if_active()
    _persist_runtime_state()
    emit("status", _status_payload())
    print(f"[App] Smooth scrolling {'enabled' if smooth_scroll_active else 'disabled'}")


@socketio.on("set_scroll_settings")
def handle_set_scroll_settings(data):
    """Update smooth scrolling speed / glide settings."""
    scroller.configure(
        speed=data.get("speed"),
        smoothness=data.get("smoothness"),
    )
    settings.update("scroll", speed=scroller.speed, smoothness=scroller.smoothness)
    emit("status", _status_payload())


@socketio.on("set_autostart")
def handle_set_autostart(data):
    """Enable/disable restoring this state automatically at launch."""
    enabled = bool(data.get("enabled", False))
    settings.update("autostart", enabled=enabled)
    _persist_runtime_state()
    emit("status", _status_payload())
    print(f"[App] Autostart {'enabled' if enabled else 'disabled'}")


@socketio.on("set_mapping")
def handle_set_mapping(data):
    """Assign a shortcut to a mouse button."""
    button_id = data.get("button_id")
    preset = data.get("preset")
    key = data.get("key")
    modifiers = data.get("modifiers", [])
    label = data.get("label", "")

    if not button_id:
        emit("error", {"message": "No button_id provided"})
        return

    if preset and preset != "custom":
        success = remapper.set_mapping(button_id, preset)
    elif key:
        success = remapper.set_custom_mapping(button_id, key, modifiers, label)
    else:
        remapper.remove_mapping(button_id)
        success = True

    if success:
        emit("mapping_updated", {
            "button_id": button_id,
            "mapping": remapper.get_mapping(button_id),
        })
    else:
        emit("error", {"message": f"Failed to set mapping for {button_id}"})


@socketio.on("remove_mapping")
def handle_remove_mapping(data):
    """Remove a button mapping."""
    button_id = data.get("button_id")
    if button_id:
        remapper.remove_mapping(button_id)
        emit("mapping_updated", {
            "button_id": button_id,
            "mapping": None,
        })


@socketio.on("save_profile")
def handle_save_profile(data):
    """Save current mappings as a profile."""
    name = data.get("name", "Untitled")
    app_bundle_id = data.get("app_bundle_id")
    mappings = remapper.get_all_mappings()

    success = profile_manager.save_profile(name, mappings, app_bundle_id)
    if success:
        emit("profile_saved", {"name": name})
        emit("profiles_list", profile_manager.list_profiles())
    else:
        emit("error", {"message": f"Failed to save profile '{name}'"})


@socketio.on("load_profile")
def handle_load_profile(data):
    """Load a profile and apply its mappings."""
    name = data.get("name")
    profile = profile_manager.load_profile(name)

    if profile:
        remapper.load_mappings(profile.mappings)
        _persist_runtime_state()
        emit("profile_loaded", {
            "name": profile.name,
            "mappings": remapper.get_all_mappings(),
        })
        emit("status", _status_payload())
    else:
        emit("error", {"message": f"Profile '{name}' not found"})


@socketio.on("get_profiles")
def handle_get_profiles():
    """Get list of all profiles."""
    emit("profiles_list", profile_manager.list_profiles())


@socketio.on("get_mappings")
def handle_get_mappings():
    """Get current button mappings."""
    emit("all_mappings", remapper.get_all_mappings())


# ── Main entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    host = settings.section("server").get("host", "127.0.0.1")
    port = int(settings.section("server").get("port", 8080))
    ui_host = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host

    print("=" * 60)
    print("  Razer Viper Mini Button Mapper")
    print(f"  Open http://{ui_host}:{port} in your browser")
    print("=" * 60)
    print()

    profile_manager.create_default_profile()

    if sys.platform != "darwin":
        print("WARNING: This app requires macOS for mouse event detection.")
        print("The UI will load, but button detection won't work.")
        print()

    apply_autostart()

    socketio.run(app, host=host, port=port, debug=False,
                 allow_unsafe_werkzeug=True)
