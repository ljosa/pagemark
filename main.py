#!/usr/bin/env python3
"""Pagemark - A simple word processor.

Usage:
    python main.py [filename]
    
Controls:
    Arrow keys: Navigate cursor (maintains column position)
    Ctrl-S: Save file
    Ctrl-Q: Quit (prompts to save if modified)
    Type to insert text
    Backspace: Delete character
    Enter: New paragraph
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