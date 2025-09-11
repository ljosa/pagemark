"""Session state management for the pagemark editor.

This module provides a centralized way to manage session state
that persists across different components and dialog instances.
"""

from typing import Optional, Any, Dict


class SessionManager:
    """Manages session state across the application.
    
    This singleton class maintains session state that needs to persist
    across different components, such as font selection and spacing
    preferences in the print dialog.
    """
    
    _instance: Optional['SessionManager'] = None
    
    def __new__(cls) -> 'SessionManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._state = {}
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
        """Set a session value.
        
        Args:
            key: The session key
            value: The value to store
        """
        self._state[key] = value
    
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


# Session keys used across the application
class SessionKeys:
    """Constants for session state keys."""
    
    # Print dialog settings
    FONT_NAME = "print_font_name"
    DOUBLE_SPACING = "double_spacing"
    LINE_LENGTH = "line_length"  # Text width in characters
    
    # Editor settings
    LAST_SAVE_PATH = "last_save_path"


# Convenience functions
def get_session() -> SessionManager:
    """Get the session manager instance.
    
    Returns:
        The singleton SessionManager instance
    """
    return SessionManager()