"""Settings persistence for per-document user preferences.

This module provides persistent storage for user settings indexed by document path.
Settings are stored in an OS-appropriate location and survive application restarts.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import platformdirs

logger = logging.getLogger(__name__)


class SettingsPersistence:
    """Manages persistent storage of per-document settings.
    
    Settings are stored in a JSON file in the user's config directory,
    indexed by the absolute path of the document being edited.
    """
    
    def __init__(self):
        """Initialize settings persistence."""
        # Get platform-appropriate config directory
        self._config_dir = Path(platformdirs.user_config_dir("pagemark", "ljosa"))
        self._settings_file = self._config_dir / "settings.json"
        self._settings_cache: Optional[Dict[str, Dict[str, Any]]] = None
    
    def _ensure_config_dir(self) -> None:
        """Ensure the config directory exists."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not create config directory {self._config_dir}: {e}")
    
    def _load_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Load all settings from disk.
        
        Returns:
            Dictionary mapping document paths to their settings.
            Returns empty dict if file doesn't exist or can't be read.
        """
        if self._settings_cache is not None:
            return self._settings_cache
        
        if not self._settings_file.exists():
            self._settings_cache = {}
            return self._settings_cache
        
        try:
            with open(self._settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Validate that it's a dict
            if not isinstance(data, dict):
                logger.warning("Settings file has invalid format (not a dict), ignoring")
                self._settings_cache = {}
                return self._settings_cache
            
            self._settings_cache = data
            return self._settings_cache
            
        except (json.JSONDecodeError, OSError, PermissionError) as e:
            logger.warning(f"Could not load settings from {self._settings_file}: {e}")
            self._settings_cache = {}
            return self._settings_cache
    
    def _save_all_settings(self, settings: Dict[str, Dict[str, Any]]) -> bool:
        """Save all settings to disk atomically.
        
        Args:
            settings: Dictionary mapping document paths to their settings.
            
        Returns:
            True if save was successful, False otherwise.
        """
        self._ensure_config_dir()
        
        # Use atomic write pattern (temp file + rename)
        # Similar to autosave.py
        temp_file = self._settings_file.with_suffix('.tmp')
        
        try:
            # Write to temp file
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            
            # Atomic rename
            temp_file.replace(self._settings_file)
            
            # Update cache
            self._settings_cache = settings
            return True
            
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not save settings to {self._settings_file}: {e}")
            # Clean up temp file if it exists
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except OSError:
                pass
            return False
    
    def load_settings(self, document_path: Optional[str]) -> Dict[str, Any]:
        """Load settings for a specific document.
        
        Args:
            document_path: Absolute path to the document. If None, returns empty dict.
            
        Returns:
            Dictionary of settings for the document. Empty dict if no settings exist
            or document_path is None.
        """
        if document_path is None:
            return {}
        
        # Normalize path to absolute
        try:
            abs_path = os.path.abspath(document_path)
        except (OSError, ValueError):
            logger.warning(f"Invalid document path: {document_path}")
            return {}
        
        all_settings = self._load_all_settings()
        doc_settings = all_settings.get(abs_path, {})
        
        # Validate that doc_settings is a dict
        if not isinstance(doc_settings, dict):
            logger.warning(f"Settings for {abs_path} are not a dict, ignoring")
            return {}
        
        return doc_settings.copy()
    
    def save_settings(self, document_path: Optional[str], settings: Dict[str, Any]) -> bool:
        """Save settings for a specific document.
        
        Args:
            document_path: Absolute path to the document. If None, returns False.
            settings: Dictionary of settings to save.
            
        Returns:
            True if save was successful, False otherwise.
        """
        if document_path is None:
            return False
        
        # Normalize path to absolute
        try:
            abs_path = os.path.abspath(document_path)
        except (OSError, ValueError):
            logger.warning(f"Invalid document path: {document_path}")
            return False
        
        # Load all settings
        all_settings = self._load_all_settings()
        
        # Update settings for this document
        all_settings[abs_path] = settings
        
        # Save back to disk
        return self._save_all_settings(all_settings)
    
    def validate_setting(self, key: str, value: Any, available_options: Optional[list] = None) -> bool:
        """Validate a setting value.
        
        Args:
            key: Setting key name.
            value: Setting value to validate.
            available_options: Optional list of valid options for this setting.
            
        Returns:
            True if setting is valid, False otherwise.
        """
        # Basic type checking
        if value is None:
            return True  # None is valid (means "not set")
        
        # String settings (printer_name, pdf_filename, font_name, print_font_name)
        if key in ('printer_name', 'pdf_filename', 'font_name', 'print_font_name'):
            if not isinstance(value, str):
                return False
            if key == 'printer_name' and available_options:
                return value in available_options
            return True
        
        # Boolean settings (double_spacing, duplex_printing)
        if key in ('double_spacing', 'duplex_printing'):
            return isinstance(value, bool)
        
        # Integer settings (line_length)
        if key == 'line_length':
            if not isinstance(value, int):
                return False
            # Reasonable range for line length
            return 40 <= value <= 120
        
        # Unknown settings are considered valid (forward compatibility)
        return True
    
    def clear_cache(self) -> None:
        """Clear the in-memory cache of settings."""
        self._settings_cache = None


# Global instance
_persistence: Optional[SettingsPersistence] = None


def get_persistence() -> SettingsPersistence:
    """Get the global settings persistence instance.
    
    Returns:
        The singleton SettingsPersistence instance.
    """
    global _persistence
    if _persistence is None:
        _persistence = SettingsPersistence()
    return _persistence
