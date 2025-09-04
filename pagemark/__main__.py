"""Pagemark CLI entry point.

Allows running via `python -m pagemark` and provides the console script
defined in `pyproject.toml`.
"""

from __future__ import annotations

import sys
import termios
from typing import Optional

from .editor import Editor
from .terminal import TerminalInterface
from .keyboard import KeyboardHandler, KeyEvent


def _escape_bytes(s: str) -> str:
    """Return a printable representation of raw key string."""
    # Represent control/escape characters visibly
    return s.encode('unicode_escape').decode('ascii')


def run_keyboard_test() -> None:
    """Run a simple interactive keyboard test using the real input stack.

    - Uses TerminalInterface + KeyboardHandler (same path as the editor)
    - Press Ctrl-Q or ESC to quit
    """
    term = TerminalInterface()
    kb = KeyboardHandler(term)

    print("Keyboard test mode — press keys to see parsed events.")
    print("Quit with Ctrl-Q or ESC.")

    # Enter cbreak and disable flow control like the editor does
    with term.term.cbreak():
        old_settings: Optional[list[int]] = None
        try:
            old_settings = termios.tcgetattr(sys.stdin)
            new_settings = list(old_settings)
            new_settings[0] &= ~(termios.IXON | termios.IXOFF)
            termios.tcsetattr(sys.stdin, termios.TCSANOW, new_settings)
        except Exception:
            pass

        try:
            while True:
                ev: Optional[KeyEvent] = kb.get_key_event(timeout=None)
                if ev is None:
                    continue
                # Quit on Ctrl-Q or bare ESC
                if (ev.is_ctrl and ev.value == 'q') or (ev.key_type.name == 'SPECIAL' and ev.value == 'escape'):
                    print("Exiting keyboard test.")
                    break
                raw = _escape_bytes(ev.raw)
                # Compose a compact line
                parts = [
                    f"type={ev.key_type.value}",
                    f"value={ev.value}",
                    f"raw='{raw}'",
                ]
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
                print(" ".join(parts))
        finally:
            if old_settings is not None:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSANOW, old_settings)
                except Exception:
                    pass


def main() -> None:
    # Very small arg parsing to support keyboard test mode and optional filename
    args = sys.argv[1:]
    if args and args[0] in ('--keytest', '--keyboard-test'):
        run_keyboard_test()
        return

    editor = Editor()
    if args:
        editor.load_file(args[0])
    editor.run()


if __name__ == "__main__":  # pragma: no cover
    main()
