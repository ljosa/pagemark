Pagemark — a distraction-free terminal word processor
=====================================================

Pagemark is a keyboard‑driven word processor for the terminal.

## Features:
 - Word wrapping in paragraphs.
 - Fixed max 65-character line length, as was standard in the typewriter days.
 - Prints in postscript format to CUPS printers (standard on Mac and Linux)
 - Bold and underline
 - Print preview
 - Optional double-sided and double-spaced printing
 - Shows where a new page begins
 - Page numbers on page 2+ (always on)
 - Undo and redo
 - Stores plain .txt files (with bold and underline, if you use them, represented by ^H overstrikes)
 - Navigation and edit behavior that will feel natural to emacs users.
 - Incremental search

## Installing and running
- Install via uv tool (global shim):
  - `uv tool install --from https://github.com/ljosa/pagemark.git pagemark`
- Run: `pagemark [filename]`

## About uv
- uv is a fast Python package and project manager by Astral. It’s a drop‑in replacement for pip/pipx/venv that installs tools as isolated shims.
- Learn more and install uv: https://docs.astral.sh/uv/

## System requirements
- Python 3.9+
- A terminal with a valid `TERM` (xterm‑256color, etc.)
- macOS/iTerm2: set Option to “Esc+” for Alt key behavior
- You may have to configure your terminal emulator to send through some keys that otherwise have special meaning to the emulator or operating system
