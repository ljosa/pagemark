"""Reproduce BUG-2 and BUG-3: line-width-related bugs.

BUG-2: Per-document line length not restored when reopening a file.
    load_file() loads persisted settings into the session but never
    applies LINE_LENGTH to VIEW_WIDTH / view.num_columns.

BUG-3: center_line uses hardcoded width instead of current view width.
    center_line() uses EditorConstants.DOCUMENT_WIDTH (65) rather than
    self.view.num_columns, so centering is wrong at non-default widths.
"""

from __future__ import annotations

import json
import os

import platformdirs
import pytest

from pagemark.model import TextModel
from pagemark.view import TerminalTextView

pyte = pytest.importorskip("pyte")


# ── Settings persistence path (for BUG-2 harness test) ─────────────

_SETTINGS_FILE = os.path.join(
    platformdirs.user_config_dir("pagemark", "ljosa"),
    "settings.json",
)


# ── BUG-3: center_line uses hardcoded width ─────────────────────────

class TestCenterLineWidth:
    """center_line must use the view's num_columns, not hardcoded 65."""

    def _make_model(self, text: str, num_columns: int = 65) -> TextModel:
        v = TerminalTextView()
        v.num_rows = 20
        v.num_columns = num_columns
        m = TextModel(v, paragraphs=[text])
        v.render()
        return m

    def test_center_at_default_width(self):
        """Sanity: centering at width 65 puts 'Hi' at column 31."""
        m = self._make_model("Hi", num_columns=65)
        m.center_line()
        para = m.paragraphs[0]
        leading = len(para) - len(para.lstrip())
        assert leading == (65 - 2) // 2  # 31

    def test_center_at_72_width(self):
        """At width 72, 'Hi' should be centered with 35 leading spaces.

        The bug: center_line uses hardcoded 65, producing 31 spaces
        regardless of the view width.
        """
        m = self._make_model("Hi", num_columns=72)
        m.center_line()
        para = m.paragraphs[0]
        leading = len(para) - len(para.lstrip())
        expected = (72 - 2) // 2  # 35
        assert leading == expected, (
            f"At width 72, expected {expected} leading spaces but got {leading} "
            f"(center_line appears to use hardcoded width 65)"
        )

    def test_center_rejects_line_too_long_for_view(self):
        """A line longer than view width should not be centered.

        At width 72, a 68-char string fits and should be centerable.
        The bug: center_line checks against hardcoded 65 and rejects it.
        """
        text = "x" * 68  # fits in 72 columns, not in 65
        m = self._make_model(text, num_columns=72)
        result = m.center_line()
        assert result is True, (
            "center_line rejected a 68-char line at width 72 "
            "(it checks against hardcoded 65 instead of view width)"
        )


# ── BUG-2: per-document line length not restored ────────────────────

@pytest.fixture
def small_term():
    from terminal_harness import TerminalHarness

    harness = TerminalHarness(rows=12, cols=90)
    yield harness
    harness.stop()


@pytest.fixture
def persisted_line_length(tmp_path):
    """Write a temp file and pre-populate settings with line_length=72.

    Yields the path to the temp file.  Cleans up the settings entry
    afterwards so we don't pollute the user's real config.
    """
    test_file = tmp_path / "wide.txt"
    # 68 characters — fits on one line at width 72, wraps at width 65.
    text = "word " * 13 + "end"
    test_file.write_text(text)

    abs_path = str(test_file.resolve())

    # Snapshot existing settings to restore later
    old_settings = {}
    if os.path.exists(_SETTINGS_FILE):
        with open(_SETTINGS_FILE, "r") as f:
            old_settings = json.load(f)

    # Inject line_length=72 for our test document
    new_settings = dict(old_settings)
    new_settings[abs_path] = {
        "line_length": 72,
        "print_font_name": "Prestige Elite Std",
    }
    os.makedirs(os.path.dirname(_SETTINGS_FILE), exist_ok=True)
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(new_settings, f, indent=2)

    yield abs_path

    # Restore original settings
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(old_settings, f, indent=2)


def test_persisted_line_length_applied_on_open(small_term, persisted_line_length):
    """A document saved with line_length=72 must reopen at that width.

    The test file contains a 68-character line.  At width 72 it fits on
    one visual line.  At the default width 65 it wraps to two lines.
    """
    small_term.start(persisted_line_length)
    assert small_term.wait_ready(timeout=5), "Editor did not start"
    small_term.wait_stable()

    display = small_term.get_display()

    # Find which row contains "end"
    end_row = None
    for i, line in enumerate(display):
        if "end" in line:
            end_row = i
            break

    assert end_row == 0, (
        f"With line_length=72 the 68-char text should fit on one line, "
        f"but 'end' appears on row {end_row} (text wrapped at width 65).\n"
        f"Row 0: {display[0].rstrip()!r}\n"
        f"Row 1: {display[1].rstrip()!r}"
    )
