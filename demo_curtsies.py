"""Minimal curtsies key event demo.

Usage:
    uv run python demo_curtsies.py

Press ESC to quit. Prints curtsies-reported tokens verbatim so you can
verify how Shift + Arrow and other combinations are reported by your
terminal. This script deliberately avoids the app's input stack to show
raw curtsies behavior.
"""

from __future__ import annotations

from curtsies import Input  # type: ignore


def main() -> None:
    print("curtsies demo — press keys to see tokens; ESC to quit.")
    with Input(keynames="curtsies") as inp:
        for e in inp:
            token = str(e)
            # Quit on ESC
            if token in ("<ESC>", "\x1b"):
                print("Exiting.")
                break
            # Print a compact line for easy scanning
            if len(token) == 1 and token not in ("<", ">"):
                # Single character; show codepoint too
                print(f"char='{token}' code=0x{ord(token):02x}")
            else:
                print(f"event={token}")


if __name__ == "__main__":
    main()

