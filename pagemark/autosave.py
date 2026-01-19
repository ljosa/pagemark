"""Autosave module for swap file management.

Provides vim-style swap file functionality to protect against data loss
from unexpected reboots or crashes.
"""

import os
import tempfile
from typing import Optional

from .constants import EditorConstants


def get_swap_path(filename: str) -> str:
    """Compute swap file path for a given document.

    For /path/to/document.txt returns /path/to/.document.txt.swp

    Args:
        filename: Path to the original document file.

    Returns:
        Path to the swap file.
    """
    dir_name = os.path.dirname(filename) or '.'
    base_name = os.path.basename(filename)
    swap_name = (
        EditorConstants.AUTOSAVE_SWAP_PREFIX
        + base_name
        + EditorConstants.AUTOSAVE_SWAP_SUFFIX
    )
    return os.path.join(dir_name, swap_name)


def write_swap_file(filename: str, content: str) -> bool:
    """Write content to swap file atomically.

    Args:
        filename: Path to the original document file.
        content: Content to write to the swap file.

    Returns:
        True if write succeeded, False otherwise.
    """
    swap_path = get_swap_path(filename)
    dir_name = os.path.dirname(swap_path) or '.'

    try:
        # Write to temp file first, then rename for atomicity
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=dir_name,
            suffix='.swp.tmp',
            delete=False
        ) as temp_file:
            temp_filename = temp_file.name
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        # Atomic rename
        os.replace(temp_filename, swap_path)
        return True

    except (OSError, IOError):
        # Clean up temp file if it exists
        if 'temp_filename' in locals():
            try:
                os.remove(temp_filename)
            except OSError:
                pass
        return False


def delete_swap_file(filename: str) -> None:
    """Delete swap file if it exists.

    Args:
        filename: Path to the original document file.
    """
    swap_path = get_swap_path(filename)
    try:
        os.remove(swap_path)
    except FileNotFoundError:
        pass
    except OSError:
        # Ignore other errors (permission, etc.) - best effort deletion
        pass


def swap_file_exists(filename: str) -> bool:
    """Check if a swap file exists for the given document.

    Args:
        filename: Path to the original document file.

    Returns:
        True if swap file exists, False otherwise.
    """
    swap_path = get_swap_path(filename)
    return os.path.exists(swap_path)


def read_swap_file(filename: str) -> Optional[str]:
    """Read swap file content.

    Args:
        filename: Path to the original document file.

    Returns:
        Content of the swap file, or None if doesn't exist or unreadable.
    """
    swap_path = get_swap_path(filename)
    try:
        with open(swap_path, 'r', encoding='utf-8') as f:
            return f.read()
    except (FileNotFoundError, IOError, OSError):
        return None
