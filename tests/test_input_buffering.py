"""Regression tests for buffered-input delivery (BUG-18).

curtsies decodes whole OS reads at once: a paste of several characters is
one read() that becomes many queued events. Gating delivery on select(stdin)
stalled everything after the first event, because the kernel buffer was
already empty while the events sat inside curtsies.
"""

from pagemark.terminal import TerminalInterface


class FakeCurtsiesInput:
    """Mimics curtsies.Input state after one read decoded several keys."""

    def __init__(self, queued):
        self.queued_events = list(queued)
        self.unprocessed_bytes = []
        self.queued_interrupting_events = []
        self.sigints = []

    def send(self, timeout=None):
        if self.queued_events:
            return self.queued_events.pop(0)
        return None  # nothing buffered and (in tests) nothing on stdin


def make_terminal(queued):
    ti = TerminalInterface.__new__(TerminalInterface)
    ti._curtsies_input = FakeCurtsiesInput(queued)
    ti._curtsies_active = True
    return ti


def test_get_key_drains_buffered_events_without_stdin_activity():
    """Events already decoded by curtsies must be delivered even though
    nothing is readable on stdin (the old select() gate returned None)."""
    ti = make_terminal(['a', 'b', 'c'])

    assert ti.get_key(timeout=0) == 'a'
    assert ti.get_key(timeout=0) == 'b'
    assert ti.get_key(timeout=0) == 'c'
    assert ti.get_key(timeout=0) is None


def test_has_pending_input_reflects_curtsies_buffers():
    ti = make_terminal(['x'])
    assert ti.has_pending_input() is True

    ti.get_key(timeout=0)
    assert ti.has_pending_input() is False

    ti._curtsies_input.unprocessed_bytes.append(b'\x1b')
    assert ti.has_pending_input() is True


def test_has_pending_input_without_curtsies():
    ti = TerminalInterface.__new__(TerminalInterface)
    ti._curtsies_input = None
    assert ti.has_pending_input() is False


def test_curtsies_still_has_the_buffers_we_probe():
    """has_pending_input() reads curtsies internals via getattr with a False
    fallback; if a curtsies upgrade renames them, BUG-18 would regress
    silently. Fail loudly here instead."""
    import pytest
    curtsies = pytest.importorskip("curtsies")
    inp = curtsies.Input()  # attributes are set in __init__, no context needed
    for attr in ("queued_events", "unprocessed_bytes",
                 "queued_interrupting_events", "sigints"):
        assert hasattr(inp, attr), f"curtsies.Input no longer has {attr}"
