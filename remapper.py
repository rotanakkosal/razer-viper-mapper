"""
Button Remapping Engine for Razer Viper Mini
Simulates macOS keyboard shortcuts via AppleScript (System Events),
which reliably triggers system-level shortcuts like Switch Space
that CGEventPost cannot on newer macOS versions.
"""

import subprocess


# macOS virtual key codes (subset of commonly used keys)
# Full reference: /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/
#   System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/
#   HIToolbox.framework/Versions/A/Headers/Events.h
KEY_CODES = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04,
    "g": 0x05, "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09,
    "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E, "r": 0x0F,
    "y": 0x10, "t": 0x11, "1": 0x12, "2": 0x13, "3": 0x14,
    "4": 0x15, "6": 0x16, "5": 0x17, "9": 0x19, "7": 0x1A,
    "8": 0x1C, "0": 0x1D, "o": 0x1F, "u": 0x20, "i": 0x22,
    "p": 0x23, "l": 0x25, "j": 0x26, "k": 0x28, "n": 0x2D,
    "m": 0x2E,
    "return": 0x24, "tab": 0x30, "space": 0x31, "delete": 0x33,
    "escape": 0x35, "backspace": 0x33,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76,
    "f5": 0x60, "f6": 0x61, "f7": 0x62, "f8": 0x64,
    "f9": 0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
    "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
    "home": 0x73, "end": 0x77, "pageup": 0x74, "pagedown": 0x79,
    "[": 0x21, "]": 0x1E, "\\": 0x2A, ";": 0x29, "'": 0x27,
    ",": 0x2B, ".": 0x2F, "/": 0x2C, "`": 0x32, "-": 0x1B,
    "=": 0x18,
}

MODIFIER_TO_APPLESCRIPT = {
    "cmd": "command down",
    "command": "command down",
    "shift": "shift down",
    "option": "option down",
    "alt": "option down",
    "ctrl": "control down",
    "control": "control down",
}

# Predefined macOS shortcuts for easy selection in the UI
PRESET_SHORTCUTS = {
    "mission_control": {
        "label": "Mission Control",
        "key": "up",
        "modifiers": ["ctrl"],
        "description": "Show all windows and spaces",
    },
    "app_expose": {
        "label": "App Exposé",
        "key": "down",
        "modifiers": ["ctrl"],
        "description": "Show all windows of current app",
    },
    "show_desktop": {
        "label": "Show Desktop",
        "key": "f11",
        "modifiers": [],
        "description": "Reveal the desktop",
    },
    "launchpad": {
        "label": "Launchpad",
        "key": "f4",
        "modifiers": [],
        "description": "Open Launchpad",
    },
    "copy": {
        "label": "Copy",
        "key": "c",
        "modifiers": ["cmd"],
        "description": "Copy selected content",
    },
    "paste": {
        "label": "Paste",
        "key": "v",
        "modifiers": ["cmd"],
        "description": "Paste from clipboard",
    },
    "cut": {
        "label": "Cut",
        "key": "x",
        "modifiers": ["cmd"],
        "description": "Cut selected content",
    },
    "undo": {
        "label": "Undo",
        "key": "z",
        "modifiers": ["cmd"],
        "description": "Undo last action",
    },
    "redo": {
        "label": "Redo",
        "key": "z",
        "modifiers": ["cmd", "shift"],
        "description": "Redo last undone action",
    },
    "screenshot_full": {
        "label": "Screenshot (Full)",
        "key": "3",
        "modifiers": ["cmd", "shift"],
        "description": "Capture entire screen",
    },
    "screenshot_area": {
        "label": "Screenshot (Area)",
        "key": "4",
        "modifiers": ["cmd", "shift"],
        "description": "Capture selected area",
    },
    "screenshot_window": {
        "label": "Screenshot (Window)",
        "key": "5",
        "modifiers": ["cmd", "shift"],
        "description": "Screenshot toolbar",
    },
    "space_left": {
        "label": "Switch Space Left",
        "key": "left",
        "modifiers": ["ctrl"],
        "description": "Move to left desktop space",
    },
    "space_right": {
        "label": "Switch Space Right",
        "key": "right",
        "modifiers": ["ctrl"],
        "description": "Move to right desktop space",
    },
    "spotlight": {
        "label": "Spotlight Search",
        "key": "space",
        "modifiers": ["cmd"],
        "description": "Open Spotlight search",
    },
    "force_quit": {
        "label": "Force Quit Menu",
        "key": "escape",
        "modifiers": ["cmd", "option"],
        "description": "Open Force Quit dialog",
    },
    "tab_next": {
        "label": "Next Tab",
        "key": "tab",
        "modifiers": ["ctrl"],
        "description": "Switch to next tab",
    },
    "tab_prev": {
        "label": "Previous Tab",
        "key": "tab",
        "modifiers": ["ctrl", "shift"],
        "description": "Switch to previous tab",
    },
    "app_switch": {
        "label": "App Switcher",
        "key": "tab",
        "modifiers": ["cmd"],
        "description": "Switch between applications",
    },
    "close_window": {
        "label": "Close Window",
        "key": "w",
        "modifiers": ["cmd"],
        "description": "Close the current window",
    },
    "minimize": {
        "label": "Minimize Window",
        "key": "m",
        "modifiers": ["cmd"],
        "description": "Minimize the current window",
    },
    "zoom_in": {
        "label": "Zoom In",
        "key": "=",
        "modifiers": ["cmd"],
        "description": "Zoom in",
    },
    "zoom_out": {
        "label": "Zoom Out",
        "key": "-",
        "modifiers": ["cmd"],
        "description": "Zoom out",
    },
    "select_all": {
        "label": "Select All",
        "key": "a",
        "modifiers": ["cmd"],
        "description": "Select all content",
    },
    "find": {
        "label": "Find",
        "key": "f",
        "modifiers": ["cmd"],
        "description": "Open Find dialog",
    },
    "save": {
        "label": "Save",
        "key": "s",
        "modifiers": ["cmd"],
        "description": "Save current file",
    },
    "none": {
        "label": "No Action",
        "key": None,
        "modifiers": [],
        "description": "Pass through (no remap)",
    },
}


def simulate_key_press(key: str, modifiers: list[str] = None):
    """
    Simulate a keyboard shortcut via AppleScript (System Events).
    This reliably triggers system-level shortcuts on modern macOS.
    """
    if key is None:
        return

    key_code = KEY_CODES.get(key.lower())
    if key_code is None:
        print(f"[Remapper] Unknown key: {key}")
        return

    mod_parts = []
    if modifiers:
        for mod in modifiers:
            as_mod = MODIFIER_TO_APPLESCRIPT.get(mod.lower())
            if as_mod:
                mod_parts.append(as_mod)

    if mod_parts:
        using_clause = " using {" + ", ".join(mod_parts) + "}"
    else:
        using_clause = ""

    script = f'tell application "System Events" to key code {key_code}{using_clause}'
    subprocess.Popen(["osascript", "-e", script],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Remapper:
    """
    Manages button-to-shortcut mappings and executes remaps.

    Usage:
        remapper = Remapper()
        remapper.set_mapping("side_back", "mission_control")  # Use preset
        remapper.set_custom_mapping("side_forward", "v", ["cmd"])  # Custom shortcut

        # In the mouse detector intercept callback:
        if remapper.should_intercept(button_id):
            remapper.execute(button_id)
            return True  # Suppress original event
    """

    def __init__(self):
        # {button_id: {preset: str, key: str, modifiers: list, label: str}}
        self._mappings: dict = {}

    def set_mapping(self, button_id: str, preset_name: str):
        """Assign a preset shortcut to a button."""
        preset = PRESET_SHORTCUTS.get(preset_name)
        if not preset:
            print(f"[Remapper] Unknown preset: {preset_name}")
            return False

        self._mappings[button_id] = {
            "preset": preset_name,
            "key": preset["key"],
            "modifiers": preset["modifiers"],
            "label": preset["label"],
            "description": preset["description"],
        }
        print(f"[Remapper] {button_id} → {preset['label']}")
        return True

    def set_custom_mapping(self, button_id: str, key: str, modifiers: list[str],
                           label: str = "Custom"):
        """Assign a custom key combination to a button."""
        if key and key.lower() not in KEY_CODES:
            print(f"[Remapper] Unknown key: {key}")
            return False

        mod_label = "+".join(m.capitalize() for m in modifiers)
        full_label = f"{mod_label}+{key.upper()}" if mod_label else key.upper()

        self._mappings[button_id] = {
            "preset": "custom",
            "key": key,
            "modifiers": modifiers,
            "label": label or full_label,
            "description": f"Custom: {full_label}",
        }
        print(f"[Remapper] {button_id} → {full_label}")
        return True

    def remove_mapping(self, button_id: str):
        """Remove a button mapping (return to default behavior)."""
        if button_id in self._mappings:
            del self._mappings[button_id]
            print(f"[Remapper] {button_id} → default")

    def should_intercept(self, button_id: str) -> bool:
        """Check if a button press should be intercepted for remapping."""
        mapping = self._mappings.get(button_id)
        if not mapping:
            return False
        # Don't intercept "none" preset
        if mapping.get("preset") == "none":
            return False
        return True

    def execute(self, button_id: str):
        """Execute the mapped shortcut for a button press."""
        mapping = self._mappings.get(button_id)
        if not mapping or mapping.get("key") is None:
            return

        simulate_key_press(mapping["key"], mapping["modifiers"])

    def get_mapping(self, button_id: str) -> dict:
        """Get the current mapping for a button, or None."""
        return self._mappings.get(button_id)

    def get_all_mappings(self) -> dict:
        """Get all current button mappings."""
        return dict(self._mappings)

    def load_mappings(self, mappings: dict):
        """Load mappings from a dict (e.g., from a profile)."""
        self._mappings = {}
        for button_id, config in mappings.items():
            if config.get("preset") and config["preset"] != "custom":
                self.set_mapping(button_id, config["preset"])
            else:
                self.set_custom_mapping(
                    button_id,
                    config.get("key", ""),
                    config.get("modifiers", []),
                    config.get("label", "Custom"),
                )

    def clear_all(self):
        """Remove all mappings."""
        self._mappings.clear()
