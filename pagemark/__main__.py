"""Pagemark CLI entry point.

Allows running via `python -m pagemark` and provides the console script
defined in `pyproject.toml`.
"""

from __future__ import annotations

import sys
from typing import Optional
from .version import get_version_string
from .autosave import swap_file_exists, read_swap_file, delete_swap_file, get_swap_path


def _escape_bytes(s: str) -> str:
    """Return a printable representation of raw key string."""
    # Represent control/escape characters visibly
    return s.encode('unicode_escape').decode('ascii')


def prompt_recovery(filename: str) -> Optional[str]:
    """Prompt user about swap file recovery.

    Args:
        filename: Path to the original document file.

    Returns:
        Content from swap file if user chose to recover,
        None if user chose to delete swap or abort,
        or raises SystemExit if user chose to abort.
    """
    import os
    swap_path = get_swap_path(filename)
    swap_basename = os.path.basename(swap_path)

    print(f"Swap file {swap_basename} found.")
    print("This may contain unsaved changes from a previous session.")
    print()
    print("[R]ecover from swap file")
    print("[D]elete swap file and open original")
    print("[A]bort")
    print()

    while True:
        try:
            choice = input("Choice: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)

        if choice == 'r':
            # Recover from swap file
            content = read_swap_file(filename)
            if content is None:
                print("Error: Could not read swap file.")
                sys.exit(1)
            return content
        elif choice == 'd':
            # Delete swap file and open original
            delete_swap_file(filename)
            return None
        elif choice == 'a':
            # Abort
            sys.exit(0)
        else:
            print("Please enter R, D, or A.")


def run_keyboard_test() -> None:
    """Run an interactive keyboard test using the editor's input stack.

    Uses TerminalInterface + KeyboardHandler; configures termios to deliver
    Ctrl-S/Ctrl-Q/Ctrl-C/Ctrl-V as input. Quit with ESC.
    """
    import termios, sys
    from .terminal import TerminalInterface
    from .keyboard import KeyboardHandler, KeyEvent, KeyType

    print("Keyboard test mode — press keys to see parsed events.")
    print("Quit with ESC.")

    term = TerminalInterface()
    term.setup()

    # Adjust termios flags to avoid flow control/signals
    old_settings = None
    try:
        old_settings = termios.tcgetattr(sys.stdin)
        new_settings = list(old_settings)
        new_settings[0] &= ~(termios.IXON | termios.IXOFF)
        if hasattr(termios, 'IEXTEN'):
            new_settings[3] &= ~(termios.ISIG | termios.IEXTEN)
        else:
            new_settings[3] &= ~termios.ISIG
        # Disable VLNEXT/DISCARD control chars if present
        try:
            cc = list(new_settings[6])
            if hasattr(termios, 'VLNEXT') and termios.VLNEXT < len(cc):
                cc[termios.VLNEXT] = b'\x00'[0]
            if hasattr(termios, 'VDISCARD') and termios.VDISCARD < len(cc):
                cc[termios.VDISCARD] = b'\x00'[0]
            new_settings[6] = bytes(cc)
        except (IndexError, TypeError, AttributeError):
            # Be resilient to platform-specific termios layouts
            pass
        termios.tcsetattr(sys.stdin, termios.TCSANOW, new_settings)
    except (termios.error, AttributeError, OSError):
        # Keyboard test should keep running even if termios tweaks fail
        pass

    kb = KeyboardHandler(term)

    try:
        while True:
            ev: KeyEvent | None = kb.get_key_event(timeout=None)
            if not ev:
                continue
            if ev.key_type == KeyType.SPECIAL and ev.value == 'escape':
                print("Exiting keyboard test.")
                break
            raw = _escape_bytes(ev.raw)
            parts = [f"type={ev.key_type.value}", f"value={ev.value}", f"raw='{raw}'"]
            flags = []
            if ev.is_alt:
                flags.append('alt')
            if ev.is_ctrl:
                flags.append('ctrl')
            if ev.is_shift:
                flags.append('shift')
            if ev.is_sequence:
                flags.append('seq')
            if flags:
                parts.append(f"flags={'+'.join(flags)}")
            if ev.code is not None:
                parts.append(f"code={ev.code}")
            print(' '.join(parts))
    finally:
        # Restore termios and cleanup terminal
        if old_settings is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSANOW, old_settings)
            except (termios.error, OSError):
                # Best-effort restore of terminal settings
                pass
        term.cleanup()


def main() -> None:
    # Very small arg parsing to support keyboard test mode, version, and optional filename
    args = sys.argv[1:]
    if args and args[0] in ("--version", "-V"):
        print(get_version_string())
        return
    if args and args[0] in ('--keytest', '--keyboard-test'):
        run_keyboard_test()
        return

    filename = args[0] if args else None
    recovered_content: Optional[str] = None

    # Check for swap file recovery before entering editor
    if filename and swap_file_exists(filename):
        recovered_content = prompt_recovery(filename)

    # Lazy import to avoid importing UI deps for --version
    from .editor import Editor
    editor = Editor()
    if filename:
        if recovered_content is not None:
            # Load recovered content from swap file
            editor.load_from_content(filename, recovered_content)
        else:
            # Load normal file
            editor.load_file(filename)
    editor.run()


if __name__ == "__main__":  # pragma: no cover
    main()
