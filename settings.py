"""
Persistent Settings for Razer Viper Mini Button Mapper

Stores user preferences in settings.json so the app can restore its state
when launched in the background (e.g. by a LaunchAgent at login) with no
browser window open to click "Start Detection".

Remembered automatically whenever you change them in the UI:
  - remapping on/off, smooth scrolling on/off
  - scroll speed / glide
  - the active profile

Applied at launch only when autostart.enabled is True.
"""

import json
import os
import threading

SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "settings.json"
)

DEFAULTS = {
    "autostart": {
        # Start detection automatically at launch (the LaunchAgent needs this
        # ON, otherwise the app boots idle and waits for a browser click).
        "enabled": False,
        # Last-known runtime state, restored when autostart is enabled.
        "remapping": False,
        "smooth_scroll": False,
        "profile": None,
    },
    "scroll": {
        "speed": 1.0,
        "smoothness": 0.78,
    },
    "server": {
        # Loopback by default: the mapper can synthesize keystrokes, so it
        # should not be reachable from the local network. Set to "0.0.0.0"
        # only if you deliberately want to control it from another device.
        "host": "127.0.0.1",
        "port": 8080,
    },
}


def _merge_defaults(loaded: dict, defaults: dict) -> dict:
    """Recursively fill in missing keys so old settings files stay valid."""
    result = dict(defaults)
    for key, value in loaded.items():
        if key in defaults and isinstance(defaults[key], dict) and isinstance(value, dict):
            result[key] = _merge_defaults(value, defaults[key])
        else:
            result[key] = value
    return result


class Settings:
    """Loads/saves settings.json. Safe to call from socket handler threads."""

    def __init__(self, path: str = None):
        self.path = path or SETTINGS_PATH
        self._lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return json.loads(json.dumps(DEFAULTS))  # deep copy
        try:
            with open(self.path, "r") as f:
                return _merge_defaults(json.load(f), DEFAULTS)
        except Exception as e:
            print(f"[Settings] Could not read {self.path} ({e}) — using defaults.")
            return json.loads(json.dumps(DEFAULTS))

    def section(self, name: str) -> dict:
        """Get a settings section as a dict."""
        return self.data.get(name, {})

    def update(self, section: str, **values):
        """Update keys within a section and persist to disk."""
        self.data.setdefault(section, {}).update(values)
        self.save()

    def save(self):
        """Write settings to disk atomically."""
        with self._lock:
            try:
                tmp = self.path + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(self.data, f, indent=2)
                os.replace(tmp, self.path)
            except Exception as e:
                print(f"[Settings] Failed to save settings: {e}")
