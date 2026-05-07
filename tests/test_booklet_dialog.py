"""Tests for the booklet checkbox in the print dialog."""

import re
from unittest.mock import Mock, MagicMock, patch

from pagemark.print_dialog import PrintDialog, PrintAction
from pagemark.model import TextModel
from pagemark.session import get_session, SessionKeys
from pagemark.terminal import TerminalInterface


def _capture_placements(dialog):
    """Render the dialog and return [(row, col, text), ...] for every drawn chunk.

    Replaces ``term.move(row, col)`` with a sentinel so we can recover the
    on-screen position of every printed chunk. Use this to verify that no
    rendered text spills past ``term.width`` -- a real layout check that the
    plain ``move=Mock(return_value="")`` mock cannot perform.
    """
    bt = dialog.terminal.term
    bt.move = Mock(side_effect=lambda r, c: f"\x00MV:{r}:{c}\x00")
    chunks = []
    with patch("builtins.print",
               side_effect=lambda *a, **k: chunks.append("".join(str(x) for x in a))):
        dialog._render()
    full = "".join(chunks)
    # Split by the sentinel; pairs of (row, col) followed by text up to next sentinel.
    parts = re.split(r"\x00MV:(\d+):(\d+)\x00", full)
    placements = []
    for i in range(1, len(parts), 3):
        row = int(parts[i])
        col = int(parts[i + 1])
        text = parts[i + 2]
        placements.append((row, col, text))
    return placements


def _make_terminal(width: int = 140, height: int = 50):
    mock_term = Mock(spec=TerminalInterface)
    bt = MagicMock()
    bt.width = width
    bt.height = height
    bt.hide_cursor = ""
    bt.normal_cursor = ""
    bt.home = ""
    bt.clear = ""
    bt.move = Mock(return_value="")
    bt.bold = ""
    bt.normal = ""
    bt.hidden_cursor = False
    mock_term.term = bt
    return mock_term


def _make_model(num_paragraphs=2):
    mock_view = Mock()
    mock_view.num_columns = 65
    mock_view.num_rows = 54
    paragraphs = [f"Para {i}" for i in range(num_paragraphs)]
    return TextModel(mock_view, paragraphs=paragraphs)


def _clean_session():
    session = get_session()
    for key in (SessionKeys.BOOKLET, SessionKeys.DUPLEX_PRINTING,
                SessionKeys.DOUBLE_SPACING, SessionKeys.PRINTER_NAME,
                SessionKeys.FONT_NAME, SessionKeys.LINE_LENGTH):
        session.clear_key(key)


def setup_function(_fn):
    _clean_session()


def test_booklet_default_off():
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(_make_model(), _make_terminal())
        assert dialog.booklet is False
        assert dialog.imposed_sides == []


def test_toggle_booklet_computes_imposed_sides():
    with patch("pagemark.print_dialog.PrinterManager"):
        # Need enough paragraphs to produce >1 source page
        dialog = PrintDialog(_make_model(num_paragraphs=120), _make_terminal())
        assert dialog.booklet is False
        assert dialog.imposed_sides == []

        # Simulate pressing 'B'
        dialog.booklet = True
        dialog._compute_imposed_sides()
        # Pages padded to multiple of 4; sides = padded/2
        n_pages = len(dialog.pages)
        from pagemark.booklet import pad_to_multiple_of_4
        assert len(dialog.imposed_sides) == pad_to_multiple_of_4(n_pages) // 2
        # Imposition is correct (front of sheet 1: last padded -> first)
        padded_n = pad_to_multiple_of_4(n_pages)
        assert dialog.imposed_sides[0] == (padded_n - 1, 0)


def test_booklet_state_restored_from_session():
    session = get_session()
    session.set(SessionKeys.BOOKLET, True)
    try:
        with patch("pagemark.print_dialog.PrinterManager"):
            dialog = PrintDialog(_make_model(num_paragraphs=10), _make_terminal())
            assert dialog.booklet is True
            assert dialog.imposed_sides  # non-empty
    finally:
        _clean_session()


def test_print_options_carries_booklet_flag():
    with patch("pagemark.print_dialog.PrinterManager") as mgr:
        mgr.return_value.get_available_printers.return_value = ["P1"]
        mgr.return_value.get_default_printer.return_value = "P1"
        dialog = PrintDialog(_make_model(), _make_terminal())
        dialog.booklet = True
        dialog.selected_output = 0  # printer
        opts = dialog._get_print_options()
        assert opts.booklet is True
        # Booklet implies duplex
        assert opts.double_sided is True


def test_pdf_print_options_carries_booklet_flag():
    with patch("pagemark.print_dialog.PrinterManager") as mgr:
        mgr.return_value.get_available_printers.return_value = []
        dialog = PrintDialog(_make_model(), _make_terminal())
        dialog.booklet = True
        # PDF File is the only option
        opts = dialog._get_print_options()
        assert opts.action == PrintAction.SAVE_PDF
        assert opts.booklet is True


def test_navigation_count_uses_sides_when_booklet():
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(_make_model(num_paragraphs=120), _make_terminal())
        single_count = dialog._navigation_count()
        assert single_count == len(dialog.pages)

        dialog.booklet = True
        dialog._compute_imposed_sides()
        booklet_count = dialog._navigation_count()
        assert booklet_count == len(dialog.imposed_sides)
        assert booklet_count != single_count


def test_required_dialog_width_grows_in_booklet_mode():
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(_make_model(), _make_terminal())
        single_required = dialog._required_dialog_width()
        dialog.booklet = True
        booklet_required = dialog._required_dialog_width()
        assert booklet_required > single_required
        # Roughly twice as wide a preview
        assert booklet_required - single_required >= 30


def test_render_handles_narrow_terminal_in_booklet_mode():
    """At 80 cols, booklet preview must not crash and must show a fallback."""
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(_make_model(num_paragraphs=8), _make_terminal(width=80))
        dialog.booklet = True
        dialog._compute_imposed_sides()

        placements = _capture_placements(dialog)
        all_text = " ".join(t for _, _, t in placements)
        # Fallback message visible
        assert "disable booklet" in all_text.lower() or "press b" in all_text.lower()
        # Booklet option still visible so user can toggle off
        assert "[B]ooklet" in all_text


def test_render_at_80_cols_booklet_fits_within_terminal_width():
    """Every chunk drawn at (row, col) must end at or before col 80."""
    width = 80
    with patch("pagemark.print_dialog.PrinterManager") as mgr:
        mgr.return_value.get_available_printers.return_value = ["P1"]
        mgr.return_value.get_default_printer.return_value = "P1"
        dialog = PrintDialog(_make_model(num_paragraphs=8), _make_terminal(width=width))
        dialog.booklet = True
        dialog._compute_imposed_sides()

        placements = _capture_placements(dialog)

        # Filter out chunks emitted as part of the title (which uses bold/normal
        # control sequences); for our purposes we only care about content lines.
        for row, col, text in placements:
            # Strip ANSI-ish content; in this test the only escape-like content
            # comes from term.bold/normal which are MagicMock("") -> "".
            # text length here is the number of visible characters.
            assert col + len(text) <= width, (
                f"Chunk at row {row} col {col} runs past terminal width "
                f"({col + len(text)} > {width}): {text!r}"
            )


def test_render_at_80_cols_single_page_fits_within_terminal_width():
    """Sanity check: pre-existing single-page layout also fits at 80 cols."""
    width = 80
    with patch("pagemark.print_dialog.PrinterManager") as mgr:
        mgr.return_value.get_available_printers.return_value = ["P1"]
        mgr.return_value.get_default_printer.return_value = "P1"
        dialog = PrintDialog(_make_model(num_paragraphs=8), _make_terminal(width=width))
        # Booklet off (default)
        placements = _capture_placements(dialog)
        for row, col, text in placements:
            assert col + len(text) <= width, (
                f"Chunk at row {row} col {col} runs past terminal width: {text!r}"
            )


def test_render_in_booklet_mode_wide_terminal():
    """At 140 cols, booklet preview should render the sheet preview lines."""
    with patch("pagemark.print_dialog.PrinterManager"):
        dialog = PrintDialog(_make_model(num_paragraphs=8), _make_terminal(width=140))
        dialog.booklet = True
        dialog._compute_imposed_sides()

        rendered = []
        with patch("builtins.print",
                   side_effect=lambda *a, **k: rendered.append("".join(str(x) for x in a))):
            dialog._render()

        joined = "\n".join(rendered)
        # Sheet label appears at bottom of preview
        assert "Sheet 1/" in joined
        # Booklet ON visible
        assert "[B]ooklet: ON" in joined
        # Double-sided is hidden when booklet is on
        assert "[D]ouble-sided" not in joined


def test_double_sided_visible_when_booklet_off():
    with patch("pagemark.print_dialog.PrinterManager") as mgr:
        mgr.return_value.get_available_printers.return_value = ["P1"]
        mgr.return_value.get_default_printer.return_value = "P1"
        dialog = PrintDialog(_make_model(), _make_terminal(width=140))
        dialog.booklet = False
        dialog.selected_output = 0  # a printer

        rendered = []
        with patch("builtins.print", side_effect=lambda *a, **k: rendered.append("".join(str(x) for x in a))):
            dialog._render()
        joined = "\n".join(rendered)
        assert "[D]ouble-sided" in joined
        assert "[B]ooklet: OFF" in joined


def test_empty_document_renders_no_content_label():
    """An empty document should not show 'Page 1/0'."""
    with patch("pagemark.print_dialog.PrinterManager"):
        # Empty paragraphs list -> zero formatted pages
        dialog = PrintDialog(_make_model(num_paragraphs=0), _make_terminal(width=140))
        assert dialog.pages == []
        placements = _capture_placements(dialog)
        all_text = " ".join(t for _, _, t in placements)
        assert "No content" in all_text
        assert "Page 1/0" not in all_text


def test_sheet_label_blank_padding():
    """When source page count isn't a multiple of 4, padded slots show 'blank'."""
    with patch("pagemark.print_dialog.PrinterManager"):
        # 5 paragraphs each producing one source page... actually need to force
        # an odd page count. Use a model that yields 1 page, then booklet pads to 4.
        dialog = PrintDialog(_make_model(num_paragraphs=1), _make_terminal())
        # Confirm 1 source page
        assert len(dialog.pages) == 1
        dialog.booklet = True
        dialog._compute_imposed_sides()
        # Padded to 4 -> 2 sheet sides: front (3,0) back (1,2) (0-indexed)
        assert dialog.imposed_sides == [(3, 0), (1, 2)]
        # Sheet 1 front: left=padded slot 3 (blank), right=page 1
        label = dialog._sheet_label(0, 3, 0)
        assert "blank" in label
        assert "1" in label  # page 1 listed
