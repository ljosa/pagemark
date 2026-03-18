"""Reproduce BUG-1: Style corruption on character deletion.

All character-deletion methods (backspace, delete_char, kill_word,
backward_kill_word, kill_line) follow this pattern:

  1. Modify self.paragraphs[idx]  (shorten the text)
  2. Call self._sync_styles_length()  — truncates styles from the END
  3. Manually splice self.styles[idx]  — removes ANOTHER entry

The double-deletion leaves the styles array one element shorter than
the paragraph.  On the next render the last character is padded with
style 0, losing its bold or underline formatting.
"""

from __future__ import annotations

import pytest
from pagemark.model import TextModel, StyleFlags
from pagemark.view import TerminalTextView


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_model(text: str, all_bold: bool = True) -> tuple[TextModel, TerminalTextView]:
    """Create a model with a single paragraph, optionally all-bold."""
    v = TerminalTextView()
    v.num_rows = 20
    v.num_columns = 65
    m = TextModel(v, paragraphs=[text])
    if all_bold:
        m.styles = [[int(StyleFlags.BOLD)] * len(text)]
    v.render()
    return m, v


# ------------------------------------------------------------------
# Unit tests — verify model-level style arrays directly
# ------------------------------------------------------------------

class TestDeleteCharStyles:
    """Ctrl-D (delete_char) at various positions."""

    def test_delete_first_char(self):
        m, v = _make_model("Hello")
        m.cursor_position.character_index = 0
        m.delete_char()

        assert m.paragraphs == ["ello"]
        assert len(m.styles[0]) == len(m.paragraphs[0]), (
            f"styles length {len(m.styles[0])} != paragraph length {len(m.paragraphs[0])}"
        )
        assert m.styles[0] == [1, 1, 1, 1], "All remaining chars should be bold"

    def test_delete_middle_char(self):
        m, v = _make_model("Hello")
        m.cursor_position.character_index = 2
        m.delete_char()

        assert m.paragraphs == ["Helo"]
        assert len(m.styles[0]) == 4
        assert m.styles[0] == [1, 1, 1, 1]

    def test_delete_penultimate_char(self):
        m, v = _make_model("Hello")
        m.cursor_position.character_index = 3
        m.delete_char()

        assert m.paragraphs == ["Helo"]
        assert len(m.styles[0]) == 4
        assert m.styles[0] == [1, 1, 1, 1]


class TestBackspaceStyles:
    """Backspace at various positions."""

    def test_backspace_from_end(self):
        m, v = _make_model("Hello")
        m.cursor_position.character_index = 5  # after 'o'
        m.backspace()

        assert m.paragraphs == ["Hell"]
        assert len(m.styles[0]) == 4
        assert m.styles[0] == [1, 1, 1, 1]

    def test_backspace_from_middle(self):
        m, v = _make_model("Hello")
        m.cursor_position.character_index = 3  # after second 'l'
        m.backspace()

        assert m.paragraphs == ["Helo"]
        assert len(m.styles[0]) == 4
        assert m.styles[0] == [1, 1, 1, 1]


class TestKillWordStyles:
    """Alt-D (kill_word) — deletes from cursor to end of word."""

    def test_kill_word_at_start(self):
        m, v = _make_model("Hello world")
        m.cursor_position.character_index = 0
        m.kill_word()

        # kill_word deletes "Hello " (word + trailing space)
        assert m.paragraphs == ["world"]
        assert len(m.styles[0]) == len(m.paragraphs[0])
        assert all(s == 1 for s in m.styles[0]), "All remaining chars should be bold"


class TestBackwardKillWordStyles:
    """Alt-Backspace (backward_kill_word)."""

    def test_backward_kill_word_at_end(self):
        m, v = _make_model("Hello world")
        m.cursor_position.character_index = 11  # end of "world"
        m.backward_kill_word()

        assert m.paragraphs == ["Hello "]
        assert len(m.styles[0]) == len(m.paragraphs[0])
        assert all(s == 1 for s in m.styles[0])


class TestKillLineStyles:
    """Ctrl-K (kill_line) — deletes from cursor to end of visual line."""

    def test_kill_line_from_middle(self):
        m, v = _make_model("Hello")
        m.cursor_position.character_index = 2
        m.kill_line()

        assert m.paragraphs == ["He"]
        assert len(m.styles[0]) == 2
        assert m.styles[0] == [1, 1]


# ------------------------------------------------------------------
# Integration test — verify bold is visible on screen via harness
# ------------------------------------------------------------------

pyte = pytest.importorskip("pyte")


@pytest.fixture
def small_term():
    from terminal_harness import TerminalHarness

    harness = TerminalHarness(rows=12, cols=80)
    yield harness
    harness.stop()


def test_bold_visible_after_delete_char(small_term, tmp_path):
    """Bold formatting must survive Ctrl-D on screen.

    Write an all-bold "Hello" using overstrike encoding, open it,
    delete the first character with Ctrl-D, and verify the remaining
    four characters are still rendered bold.
    """
    # Overstrike bold: each char X is encoded as X\\bX
    bold_hello = "H\x08He\x08el\x08ll\x08lo\x08o"
    test_file = tmp_path / "bold.txt"
    test_file.write_text(bold_hello)

    small_term.start(str(test_file))
    assert small_term.wait_ready(timeout=5), "Editor did not start"
    small_term.wait_stable()

    # Left margin = (80 - 65) // 2 = 7.  "Hello" at columns 7-11.
    left = 7
    for col in range(left, left + 5):
        assert small_term.is_bold(0, col), (
            f"Initial: column {col} should be bold"
        )

    # Ctrl-D deletes 'H' → "ello" at columns 7-10
    small_term.press("ctrl-d")
    small_term.wait_stable()

    remaining = small_term.get_display()[0][left:left + 4]
    assert remaining.rstrip() == "ello", f"Expected 'ello', got {remaining!r}"

    for col in range(left, left + 4):
        assert small_term.is_bold(0, col), (
            f"After Ctrl-D: column {col} ('{small_term.get_display()[0][col]}') "
            f"should still be bold"
        )
