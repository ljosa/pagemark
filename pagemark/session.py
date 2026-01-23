"""Session state management for the pagemark editor.

This module provides a centralized way to manage session state
that persists across different components and dialog instances.
Settings are automatically persisted to disk when changed.
"""

from typing import Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session state across the application.
    
    This singleton class maintains session state that needs to persist
    across different components, such as font selection and spacing
    preferences in the print dialog.
    
    Settings are automatically loaded from disk when a document is loaded
    and saved to disk when they are changed.
    """
    
    _instance: Optional['SessionManager'] = None
    
    def __new__(cls) -> 'SessionManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._state = {}
            cls._instance._document_path: Optional[str] = None
            cls._instance._persistence_enabled = True
        return cls._instance
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a session value.
        
        Args:
            key: The session key
            default: Default value if key not found
            
        Returns:
            The session value or default
        """
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a session value and persist to disk if enabled.
        
        Args:
            key: The session key
            value: The value to store
        """
        self._state[key] = value
        # Auto-save to disk if persistence is enabled and we have a document path
        if self._persistence_enabled and self._document_path:
            self._save_to_disk()
    
    def clear(self) -> None:
        """Clear all session state."""
        self._state.clear()
    
    def clear_key(self, key: str) -> None:
        """Clear a specific session key.
        
        Args:
            key: The session key to clear
        """
        self._state.pop(key, None)
    
    @property
    def state(self) -> Dict[str, Any]:
        """Get a copy of the current state.
        
        Returns:
            Copy of the session state dictionary
        """
        return self._state.copy()
    
    def load_document_settings(self, document_path: Optional[str]) -> None:
        """Load settings for a specific document from disk.
        
        Args:
            document_path: Path to the document being edited.
        """
        from .settings_persistence import get_persistence
        
        self._document_path = document_path
        
        if not document_path or not self._persistence_enabled:
            return
        
        persistence = get_persistence()
        saved_settings = persistence.load_settings(document_path)
        
        # Validate and apply each setting
        for key, value in saved_settings.items():
            if persistence.validate_setting(key, value):
                self._state[key] = value
            else:
                logger.warning(f"Ignoring invalid setting {key}={value} for document {document_path}")
    
    def _save_to_disk(self) -> None:
        """Save current settings to disk for the current document."""
        if not self._document_path or not self._persistence_enabled:
            return
        
        from .settings_persistence import get_persistence
        
        persistence = get_persistence()
        # Only save settings that should be persisted
        persistable_settings = {
            key: value for key, value in self._state.items()
            if key in SessionKeys.PERSISTABLE_KEYS
        }
        persistence.save_settings(self._document_path, persistable_settings)
    
    def set_persistence_enabled(self, enabled: bool) -> None:
        """Enable or disable persistence to disk.
        
        Args:
            enabled: True to enable persistence, False to disable.
        """
        self._persistence_enabled = enabled


# Session keys used across the application
class SessionKeys:
    """Constants for session state keys."""
    
    # Print dialog settings
    FONT_NAME = "print_font_name"
    DOUBLE_SPACING = "double_spacing"
    LINE_LENGTH = "line_length"  # Text width in characters
    PRINTER_NAME = "printer_name"  # Selected printer
    PDF_FILENAME = "pdf_filename"  # Filename for PDF export
    DUPLEX_PRINTING = "duplex_printing"  # Double-sided printing
    
    # Editor settings
    LAST_SAVE_PATH = "last_save_path"
    
    # Keys that should be persisted to disk
    PERSISTABLE_KEYS = {
        FONT_NAME,
        DOUBLE_SPACING,
        LINE_LENGTH,
        PRINTER_NAME,
        PDF_FILENAME,
        DUPLEX_PRINTING,
    }


# Convenience functions
def get_session() -> SessionManager:
    """Get the session manager instance.
    
    Returns:
        The singleton SessionManager instance
    """
    return SessionManager()