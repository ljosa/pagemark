#!/usr/bin/env python3
"""Pagemark - A simple word processor with Emacs-style keybindings.

Usage:
    python main.py [filename]
    
Controls:
    Arrow keys: Navigate cursor
    Ctrl-S: Save file
    Ctrl-Q: Quit
    Ctrl-P: Print
    
    Emacs keybindings:
    Alt-b/Alt-f: Move backward/forward by word
    Alt-backspace: Delete word backward
    Ctrl-A/Ctrl-E: Beginning/end of line
    Ctrl-D: Delete character forward
    Ctrl-K: Kill to end of line
"""

import sys
from pagemark.editor_wrapper import TextualEditor


def main():
    """Entry point for the word processor."""
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    app = TextualEditor(filename=filename)
    app.run()


if __name__ == "__main__":
    main()