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

from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit

from mouse_detector import (
    MouseDetector, ALL_BUTTONS, BUTTON_NAMES, REMAPPABLE_BUTTONS,
)
from remapper import Remapper, PRESET_SHORTCUTS, KEY_CODES
from profiles import ProfileManager

# ── Flask app setup ──────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = "razer-viper-mini-mapper"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Core components ──────────────────────────────────────────────
remapper = Remapper()
profile_manager = ProfileManager()
detector: MouseDetector = None
detection_active = False
remapping_active = False


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
    Only intercepts on 'down' events (not 'up') to avoid stuck states.
    """
    if not remapping_active:
        return False
    if event_type != "down":
        return False
    if remapper.should_intercept(button_id):
        mapping = remapper.get_mapping(button_id)
        print(f"[App] Executing remap: {button_id} → {mapping.get('key')} + {mapping.get('modifiers')}")
        remapper.execute(button_id)
        return True
    print(f"[App] No mapping for {button_id}")
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
    """Get current app status."""
    return jsonify({
        "detection_active": detection_active,
        "remapping_active": remapping_active,
        "current_profile": profile_manager.current_profile_name,
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
    emit("status", {
        "detection_active": detection_active,
        "remapping_active": remapping_active,
        "current_profile": profile_manager.current_profile_name,
    })


@socketio.on("start_detection")
def handle_start_detection():
    """Start the mouse event detector."""
    global detector, detection_active
    if detection_active:
        emit("error", {"message": "Detection already active"})
        return

    listen_only = not remapping_active
    detector = MouseDetector(
        on_button_press=on_button_press,
        listen_only=listen_only,
        on_intercept=on_intercept if not listen_only else None,
    )
    detector.start()
    detection_active = detector.is_running

    emit("status", {
        "detection_active": detection_active,
        "remapping_active": remapping_active,
        "current_profile": profile_manager.current_profile_name,
    })

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

    emit("status", {
        "detection_active": detection_active,
        "remapping_active": remapping_active,
        "current_profile": profile_manager.current_profile_name,
    })
    print("[App] Mouse detection stopped")


@socketio.on("toggle_remapping")
def handle_toggle_remapping(data):
    """Enable or disable button remapping."""
    global remapping_active, detector, detection_active
    remapping_active = data.get("enabled", False)

    # Restart detector with new mode if currently active
    if detection_active and detector:
        detector.stop()
        detection_active = False

        listen_only = not remapping_active
        detector = MouseDetector(
            on_button_press=on_button_press,
            listen_only=listen_only,
            on_intercept=on_intercept if not listen_only else None,
        )
        detector.start()
        detection_active = detector.is_running

    emit("status", {
        "detection_active": detection_active,
        "remapping_active": remapping_active,
        "current_profile": profile_manager.current_profile_name,
    })
    print(f"[App] Remapping {'enabled' if remapping_active else 'disabled'}")


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
        emit("profile_loaded", {
            "name": profile.name,
            "mappings": remapper.get_all_mappings(),
        })
        emit("status", {
            "detection_active": detection_active,
            "remapping_active": remapping_active,
            "current_profile": profile.name,
        })
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
    print("=" * 60)
    print("  Razer Viper Mini Button Mapper")
    print("  Open http://localhost:8080 in your browser")
    print("=" * 60)
    print()

    profile_manager.create_default_profile()

    if sys.platform != "darwin":
        print("WARNING: This app requires macOS for mouse event detection.")
        print("The UI will load, but button detection won't work.")
        print()

    socketio.run(app, host="0.0.0.0", port=8080, debug=False)
