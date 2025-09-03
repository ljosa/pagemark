#!/usr/bin/env python3
"""Pagemark - A simple word processor.

Usage:
    python main.py [filename]
    
Controls:
    Arrow keys: Navigate cursor
    Ctrl-Q: Quit
    Type to insert text
    Backspace: Delete character
    Enter: New line
"""

import sys
from pagemark.editor import Editor


def main():
    """Entry point for the word processor."""
    editor = Editor()
    
    # Load file if provided
    if len(sys.argv) > 1:
        editor.load_file(sys.argv[1])
    
    # Run the editor
    editor.run()
    
    print("\nGoodbye!")


if __name__ == "__main__":
    main()