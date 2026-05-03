"""
Profile Manager for Razer Viper Mini Button Mapper
Saves/loads button mapping profiles as JSON files.
Supports per-application profiles with auto-switching.
"""

import json
import os
import time
from typing import Optional

# Default profiles directory (relative to app.py location)
PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")


def _ensure_profiles_dir():
    """Create profiles directory if it doesn't exist."""
    os.makedirs(PROFILES_DIR, exist_ok=True)


class Profile:
    """Represents a single button mapping profile."""

    def __init__(self, name: str, mappings: dict = None, app_bundle_id: str = None):
        self.name = name
        self.mappings = mappings or {}
        self.app_bundle_id = app_bundle_id  # e.g., "com.apple.Safari"
        self.created_at = time.time()
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "mappings": self.mappings,
            "app_bundle_id": self.app_bundle_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        profile = cls(
            name=data["name"],
            mappings=data.get("mappings", {}),
            app_bundle_id=data.get("app_bundle_id"),
        )
        profile.created_at = data.get("created_at", time.time())
        profile.updated_at = data.get("updated_at", time.time())
        return profile


class ProfileManager:
    """
    Manages saving, loading, and switching between profiles.

    Usage:
        pm = ProfileManager()
        pm.save_profile("Gaming", mappings={"side_back": {...}})
        profile = pm.load_profile("Gaming")
        profiles = pm.list_profiles()
    """

    def __init__(self, profiles_dir: str = None):
        self.profiles_dir = profiles_dir or PROFILES_DIR
        _ensure_profiles_dir()
        self._current_profile: Optional[str] = None

    def _profile_path(self, name: str) -> str:
        """Get file path for a profile name."""
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
        safe_name = safe_name.strip().replace(" ", "_").lower()
        return os.path.join(self.profiles_dir, f"{safe_name}.json")

    def save_profile(self, name: str, mappings: dict,
                     app_bundle_id: str = None) -> bool:
        """Save a profile to disk."""
        try:
            _ensure_profiles_dir()

            profile = Profile(
                name=name,
                mappings=mappings,
                app_bundle_id=app_bundle_id,
            )

            # If updating existing profile, preserve created_at
            existing = self._load_raw(name)
            if existing:
                profile.created_at = existing.get("created_at", time.time())

            profile.updated_at = time.time()

            path = self._profile_path(name)
            with open(path, "w") as f:
                json.dump(profile.to_dict(), f, indent=2)

            print(f"[ProfileManager] Saved profile: {name}")
            return True

        except Exception as e:
            print(f"[ProfileManager] Error saving profile '{name}': {e}")
            return False

    def load_profile(self, name: str) -> Optional[Profile]:
        """Load a profile from disk."""
        data = self._load_raw(name)
        if data:
            self._current_profile = name
            return Profile.from_dict(data)
        return None

    def _load_raw(self, name: str) -> Optional[dict]:
        """Load raw profile data from disk."""
        path = self._profile_path(name)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ProfileManager] Error loading profile '{name}': {e}")
            return None

    def delete_profile(self, name: str) -> bool:
        """Delete a profile from disk."""
        path = self._profile_path(name)
        if os.path.exists(path):
            os.remove(path)
            print(f"[ProfileManager] Deleted profile: {name}")
            if self._current_profile == name:
                self._current_profile = None
            return True
        return False

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """Rename a profile."""
        profile = self.load_profile(old_name)
        if not profile:
            return False

        profile.name = new_name
        profile.updated_at = time.time()

        # Save with new name
        new_path = self._profile_path(new_name)
        with open(new_path, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)

        # Remove old file
        old_path = self._profile_path(old_name)
        if os.path.exists(old_path) and old_path != new_path:
            os.remove(old_path)

        print(f"[ProfileManager] Renamed '{old_name}' → '{new_name}'")
        return True

    def list_profiles(self) -> list[dict]:
        """List all saved profiles with basic info."""
        _ensure_profiles_dir()
        profiles = []

        for filename in sorted(os.listdir(self.profiles_dir)):
            if not filename.endswith(".json"):
                continue
            try:
                path = os.path.join(self.profiles_dir, filename)
                with open(path, "r") as f:
                    data = json.load(f)
                profiles.append({
                    "name": data.get("name", filename[:-5]),
                    "app_bundle_id": data.get("app_bundle_id"),
                    "mapping_count": len(data.get("mappings", {})),
                    "updated_at": data.get("updated_at"),
                })
            except Exception:
                continue

        return profiles

    def get_profile_for_app(self, bundle_id: str) -> Optional[Profile]:
        """Find a profile assigned to a specific application."""
        _ensure_profiles_dir()

        for filename in os.listdir(self.profiles_dir):
            if not filename.endswith(".json"):
                continue
            try:
                path = os.path.join(self.profiles_dir, filename)
                with open(path, "r") as f:
                    data = json.load(f)
                if data.get("app_bundle_id") == bundle_id:
                    return Profile.from_dict(data)
            except Exception:
                continue

        return None

    @property
    def current_profile_name(self) -> Optional[str]:
        return self._current_profile

    def create_default_profile(self):
        """Create a default profile with no mappings."""
        if not self._load_raw("Default"):
            self.save_profile("Default", mappings={})
            print("[ProfileManager] Created default profile.")
