Pagemark — a simple terminal word processor
=========================================

Pagemark is a keyboard‑driven text editor/word processor for the terminal, with sane word wrapping, page breaks, printing support, and Emacs‑style navigation (including Alt+←/→ for word movement).

Install (recommended: uv)
- Install via uv tool (global shim):
  - `uv tool install --from https://github.com/ljosa/pagemark.git pagemark`
- Run: `pagemark [filename]`

About uv
- uv is a fast Python package and project manager by Astral. It’s a drop‑in replacement for pip/pipx/venv that installs tools as isolated shims.
- Learn more and install uv: https://docs.astral.sh/uv/

Basics
- Launch: `pagemark` or `pagemark path/to/file.txt`
- Save/Quit: Ctrl‑S / Ctrl‑Q
- Navigation: arrows; Alt‑←/→ move by word; Ctrl‑A/Ctrl‑E to visual line start/end
- Printing: Ctrl‑P opens print dialog (printer or PostScript)

Requirements
- Python 3.9+
- A terminal with a valid `TERM` (xterm‑256color, etc.)
- macOS/iTerm2: set Option to “Esc+” for Alt key behavior

Notes
- The app installs a `pagemark` console command. You can also run `python -m pagemark` from a checkout.
- If the terminal is too narrow (<65 cols), Pagemark shows a friendly prompt to resize.
