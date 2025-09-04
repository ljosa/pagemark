"""Constants and configuration for the pagemark editor."""

class EditorConstants:
    """Central configuration constants for the editor."""
    
    # Document layout
    DOCUMENT_WIDTH = 65  # Standard width for word processing documents
    LINES_PER_PAGE = 54  # Lines per printed page (US letter)
    PAGE_BREAK_LINE = "-" * 76  # Visual separator between pages
    
    # Keyboard timing
    ESCAPE_SEQUENCE_TIMEOUT = 0.01  # Timeout for collecting multi-character escape sequences (seconds)
    ALT_KEY_TIMEOUT = 0.01  # Timeout for detecting Alt+key combinations (seconds)
    
    # Terminal requirements
    MIN_TERMINAL_WIDTH = 65  # Minimum terminal width required for display
    
    # Printing defaults
    DEFAULT_DUPLEX_MODE = True  # Default to double-sided printing
    
    # File operations
    ATOMIC_SAVE_PREFIX = "."  # Prefix for temporary save files
    ATOMIC_SAVE_SUFFIX = ".tmp"  # Suffix for temporary save files
    
    # Resize handling
    RESIZE_PIPE_MARKER = b'R'  # Byte written to pipe to signal resize
    
    # Status messages
    TERMINAL_TOO_NARROW_MESSAGE = "Terminal too narrow! Need at least {} columns."
    CURRENT_WIDTH_MESSAGE = "Current width: {} columns."