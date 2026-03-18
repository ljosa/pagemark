"""Terminal test harness for pagemark.

Runs pagemark in a real PTY and provides screen reading and keystroke
injection via the pyte terminal emulator library.  Useful for integration
tests and for LLM-driven interaction with the running editor.

Usage::

    with TerminalHarness(rows=24, cols=80) as term:
        term.start("myfile.txt")
        term.wait_ready()

        term.send_key("down")
        term.wait_stable()

        display = term.get_display()       # list of strings
        row, col = term.get_cursor_position()
        bold = term.is_bold(row, col)
"""

from __future__ import annotations

import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import threading
import time
from dataclasses import dataclass
from typing import Optional

import pyte


# ---------------------------------------------------------------------------
# Key-sequence table (xterm-256color)
# ---------------------------------------------------------------------------

KEY_SEQUENCES: dict[str, bytes] = {
    # Arrow keys
    "up": b"\x1b[A",
    "down": b"\x1b[B",
    "right": b"\x1b[C",
    "left": b"\x1b[D",
    # Navigation
    "home": b"\x1b[H",
    "end": b"\x1b[F",
    "page_up": b"\x1b[5~",
    "page_down": b"\x1b[6~",
    "insert": b"\x1b[2~",
    "delete": b"\x1b[3~",
    # Function keys
    "f1": b"\x1bOP",
    "f2": b"\x1bOQ",
    "f3": b"\x1bOR",
    "f4": b"\x1bOS",
    # Whitespace / editing
    "enter": b"\r",
    "backspace": b"\x7f",
    "tab": b"\t",
    "escape": b"\x1b",
    # Shift + arrow
    "shift-up": b"\x1b[1;2A",
    "shift-down": b"\x1b[1;2B",
    "shift-left": b"\x1b[1;2C",
    "shift-right": b"\x1b[1;2D",
    # Alt + arrow
    "alt-up": b"\x1b[1;3A",
    "alt-down": b"\x1b[1;3B",
    "alt-left": b"\x1b[1;3C",
    "alt-right": b"\x1b[1;3D",
}


def _key_bytes(name: str) -> bytes:
    """Convert a human-readable key name to the raw bytes to send.

    Supports:
      - Named keys from KEY_SEQUENCES  (e.g. ``"down"``, ``"page_up"``)
      - ``"ctrl-<letter>"``             (e.g. ``"ctrl-q"``)
      - ``"alt-<letter>"``              (e.g. ``"alt-b"``)
      - Single characters               (e.g. ``"a"``, ``"Y"``)
    """
    low = name.lower()

    # Exact match in the table
    if low in KEY_SEQUENCES:
        return KEY_SEQUENCES[low]

    # Ctrl-<letter>  →  0x01 .. 0x1a
    if low.startswith("ctrl-") and len(low) == 6:
        ch = low[5]
        if "a" <= ch <= "z":
            return bytes([ord(ch) - ord("a") + 1])

    # Alt-<letter>   →  ESC + char  (the "meta-sends-escape" convention)
    if low.startswith("alt-") and len(low) == 5:
        return b"\x1b" + name[4].encode("utf-8")

    # Alt-backspace
    if low == "alt-backspace":
        return b"\x1b\x7f"

    # Plain character (possibly multi-byte UTF-8)
    return name.encode("utf-8")


# ---------------------------------------------------------------------------
# Snapshot dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScreenSnapshot:
    """Immutable snapshot of the terminal screen."""

    lines: tuple[str, ...]
    cursor_row: int
    cursor_col: int

    def __str__(self) -> str:
        out = []
        for i, line in enumerate(self.lines):
            marker = " <" if i == self.cursor_row else ""
            out.append(f"  {i:3d} |{line}|{marker}")
        out.append(f"  cursor: ({self.cursor_row}, {self.cursor_col})")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# TerminalHarness
# ---------------------------------------------------------------------------

class TerminalHarness:
    """Run pagemark in a PTY and interact with it programmatically.

    The harness creates a pseudo-terminal, launches pagemark as a child
    process, and feeds the terminal output through *pyte* so the test can
    inspect screen contents, cursor position, and character attributes at
    any time.
    """

    def __init__(self, rows: int = 24, cols: int = 80):
        self.rows = rows
        self.cols = cols
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.Stream(self.screen)

        self._master_fd: Optional[int] = None
        self._process: Optional[subprocess.Popen] = None

        # Background reader thread drains the master fd into a byte buffer.
        # The main thread flushes the buffer into pyte when it needs to
        # inspect the screen — this avoids thread-safety issues with pyte.
        self._raw_buffer = bytearray()
        self._buffer_lock = threading.Lock()
        self._reader_running = False
        self._reader_thread: Optional[threading.Thread] = None

    # -- lifecycle -----------------------------------------------------------

    def start(self, filename: Optional[str] = None, *, extra_args: Optional[list[str]] = None) -> None:
        """Start pagemark in a fresh PTY.

        Args:
            filename: File to open (resolved relative to the project root).
            extra_args: Additional CLI arguments.
        """
        master_fd, slave_fd = pty.openpty()

        # Set the window size *before* the child starts so that blessed
        # picks up the right dimensions.
        winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        # Prevent locale issues in CI
        env.setdefault("LANG", "en_US.UTF-8")

        cmd = [sys.executable, "-m", "pagemark"]
        if extra_args:
            cmd.extend(extra_args)
        if filename:
            cmd.append(filename)

        self._process = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            start_new_session=True,
            env=env,
        )
        os.close(slave_fd)
        self._master_fd = master_fd

        # Start the background reader
        self._reader_running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True,
        )
        self._reader_thread.start()

    def stop(self) -> None:
        """Quit the editor and tear down the PTY."""
        # Stop the reader first so it doesn't interfere with cleanup
        self._reader_running = False

        if self._process is not None and self._process.poll() is None:
            # Try a graceful quit via Ctrl-Q
            try:
                self._write_raw(b"\x11")  # Ctrl-Q
                time.sleep(0.3)
                self._flush_to_pyte()
                # If quit confirmation is showing, press 'n' (don't save)
                if self._process.poll() is None:
                    self._write_raw(b"n")
                    time.sleep(0.3)
            except OSError:
                pass

            # Wait for exit
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=2)

        if self._reader_thread is not None:
            self._reader_thread.join(timeout=3)
            self._reader_thread = None

        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

    def __enter__(self) -> "TerminalHarness":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    # -- sending keys --------------------------------------------------------

    # Default inter-key delay.  The editor reads one key event per
    # select() loop iteration; if bytes arrive faster than the loop runs
    # they can be consumed by curtsies' internal buffer and become
    # invisible to the outer select().  30 ms is enough for the editor to
    # complete a draw-select cycle between keys.
    DEFAULT_INTER_KEY_DELAY: float = 0.03

    def send_key(self, key_name: str) -> None:
        """Send a single named key to the editor (raw, no delay).

        See :func:`_key_bytes` for the accepted formats.

        .. note::

           Prefer :meth:`press` when sending a sequence of keys — it adds
           the inter-key delay needed by the editor's event loop.
        """
        self._write_raw(_key_bytes(key_name))

    def press(self, key_name: str, *, count: int = 1) -> None:
        """Send a key *count* times with inter-key delays.

        This is the recommended way to simulate user key presses because
        it ensures each key is processed by the editor before the next
        one is sent.
        """
        data = _key_bytes(key_name)
        for _ in range(count):
            self._write_raw(data)
            time.sleep(self.DEFAULT_INTER_KEY_DELAY)

    def send_keys(self, *key_names: str) -> None:
        """Send several named keys with inter-key delays."""
        for name in key_names:
            self._write_raw(_key_bytes(name))
            time.sleep(self.DEFAULT_INTER_KEY_DELAY)

    def send_text(self, text: str) -> None:
        """Type literal text characters (with inter-key delays)."""
        for ch in text:
            self._write_raw(ch.encode("utf-8"))
            time.sleep(self.DEFAULT_INTER_KEY_DELAY)

    # -- waiting / synchronisation -------------------------------------------

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Wait until the editor has rendered its first frame.

        Returns True if the screen has visible content before *timeout*.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.05)
            self._flush_to_pyte()
            # Check if any line has non-whitespace content
            for line in self.screen.display:
                if line.strip():
                    # Give it a tiny bit more time to finish the frame
                    time.sleep(0.05)
                    self._flush_to_pyte()
                    return True
        return False

    def wait_stable(
        self, timeout: float = 2.0, settle_time: float = 0.08,
    ) -> bool:
        """Wait until the screen stops changing.

        Returns True if the screen was stable for *settle_time* seconds
        within *timeout*.  Returns False on timeout.
        """
        deadline = time.monotonic() + timeout
        last_snapshot: Optional[tuple] = None
        stable_since: Optional[float] = None

        while time.monotonic() < deadline:
            time.sleep(0.02)
            self._flush_to_pyte()
            snap = self._quick_snapshot()
            if snap == last_snapshot:
                if stable_since is None:
                    stable_since = time.monotonic()
                elif time.monotonic() - stable_since >= settle_time:
                    return True
            else:
                last_snapshot = snap
                stable_since = None
        return False

    # -- reading the screen --------------------------------------------------

    def get_display(self) -> list[str]:
        """Return the current screen as a list of strings (one per row)."""
        self._flush_to_pyte()
        return list(self.screen.display)

    def get_cursor_position(self) -> tuple[int, int]:
        """Return ``(row, col)`` of the cursor."""
        self._flush_to_pyte()
        return (self.screen.cursor.y, self.screen.cursor.x)

    def snapshot(self) -> ScreenSnapshot:
        """Capture a complete screen snapshot."""
        self._flush_to_pyte()
        return ScreenSnapshot(
            lines=tuple(self.screen.display),
            cursor_row=self.screen.cursor.y,
            cursor_col=self.screen.cursor.x,
        )

    def get_line(self, row: int) -> str:
        """Return a single screen line."""
        self._flush_to_pyte()
        return self.screen.display[row]

    def is_bold(self, row: int, col: int) -> bool:
        """Check whether the character at *(row, col)* is bold."""
        self._flush_to_pyte()
        char = self.screen.buffer[row][col]
        return bool(char.bold)

    def is_underline(self, row: int, col: int) -> bool:
        """Check whether the character at *(row, col)* is underlined."""
        self._flush_to_pyte()
        char = self.screen.buffer[row][col]
        return bool(char.underscore)

    def is_reverse(self, row: int, col: int) -> bool:
        """Check whether the character at *(row, col)* has reverse video."""
        self._flush_to_pyte()
        char = self.screen.buffer[row][col]
        return bool(char.reverse)

    def screen_text(self) -> str:
        """Return the full screen as a single string (lines joined, stripped)."""
        return "\n".join(line.rstrip() for line in self.get_display())

    # -- internals -----------------------------------------------------------

    def _write_raw(self, data: bytes) -> None:
        if self._master_fd is None:
            raise RuntimeError("Harness not started")
        os.write(self._master_fd, data)

    def _flush_to_pyte(self) -> None:
        """Feed any buffered bytes into pyte (main thread only)."""
        with self._buffer_lock:
            if not self._raw_buffer:
                return
            data = bytes(self._raw_buffer)
            self._raw_buffer.clear()
        self.stream.feed(data.decode("utf-8", errors="replace"))

    def _quick_snapshot(self) -> tuple:
        """Lightweight snapshot for change detection."""
        return (
            tuple(self.screen.display),
            self.screen.cursor.y,
            self.screen.cursor.x,
        )

    def _reader_loop(self) -> None:
        """Background thread: drain the master fd into the byte buffer."""
        fd = self._master_fd
        if fd is None:
            return
        while self._reader_running:
            try:
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    data = os.read(fd, 65536)
                    if not data:
                        break  # EOF — child exited
                    with self._buffer_lock:
                        self._raw_buffer.extend(data)
            except OSError:
                break
