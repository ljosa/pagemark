"""Pagemark CLI entry point.

Allows running via `python -m pagemark` and provides the console script
defined in `pyproject.toml`.
"""

from __future__ import annotations

import sys
from .version import get_version_string


def _escape_bytes(s: str) -> str:
    """Return a printable representation of raw key string."""
    # Represent control/escape characters visibly
    return s.encode('unicode_escape').decode('ascii')


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

    # Lazy import to avoid importing UI deps for --version
    from .editor import Editor
    editor = Editor()
    if args:
        editor.load_file(args[0])
    editor.run()


if __name__ == "__main__":  # pragma: no cover
    main()
