"""Behavior at the shared-model / Cocoa boundary, without launching windows."""
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

pytest.importorskip("pagemark_core")
F = pytest.importorskip("Foundation")
A = pytest.importorskip("AppKit")

from pagemark_core.print_formatter import PrintFormatter  # noqa: E402
from pagemark_app.application import PagemarkDocument, pdf_for, PDFPrintView  # noqa: E402
from pagemark_app.codec import StyledText  # noqa: E402
from pagemark_app.geometry import EditorGeometry  # noqa: E402
from pagemark_app.native_editor import PagemarkEditorView, composed_boundaries  # noqa: E402
from pagemark_app.recovery import RecoveryStore  # noqa: E402
from pagemark_app.session import EditorSession, Snapshot  # noqa: E402


def plain(text):
    return StyledText(text, (0,) * len(text))


def test_editing_and_printing_share_wraps_indents_dashes_and_page_boundaries():
    value = plain("- " + "one—two three " * 300 + "\n" + "x" * 65 + "\n")
    session = EditorSession(value)
    formatter = PrintFormatter(*value.parts()[:1], styles=value.parts()[1])
    pages = formatter.format_pages()
    rows = [line[10:].rstrip() for page in pages for line in page[6:60]]
    assert rows[:session.layout.line_count] == [session.layout.line_at(i).text.rstrip()
                                                for i in range(session.layout.line_count)]
    assert len(pages) == EditorGeometry(session.layout.line_count, 800).page_count
    assert session.layout.line_at(1).text.startswith("  ")
    assert "--" in session.layout.line_at(0).text


@pytest.mark.parametrize("pages", [False, True])
@pytest.mark.parametrize("double", [False, True])
def test_mouse_hit_testing_has_no_positions_in_paper_or_marker_gaps(pages, double):
    session = EditorSession(plain("\n".join("a" * 10 for _ in range(125))))
    geometry = EditorGeometry(session.layout.line_count, 850, pages, double)
    for line in range(session.layout.line_count):
        x, y = geometry.point(line, 6)
        point = geometry.hit(session.layout, x, y + geometry.line_height / 2)
        assert (point.paragraph_index, point.character_index) == (line, 6)
    for y in range(0, int(geometry.height), 13):
        point = geometry.hit(session.layout, geometry.text_x - 100, y)
        assert 0 <= point.paragraph_index < 125
        assert point.character_index == 0


def test_selection_replacement_undo_snapshot_preserves_styles_and_anchor():
    value = StyledText("bold\nunder", (1, 1, 1, 1, 0, 2, 2, 2, 2, 2))
    changes = []
    session = EditorSession(value, on_change=lambda before, after: changes.append((before, after)))
    session.select(2, 8)
    original = session.snapshot()
    session.insert("new\ntext")
    assert session.value.text == "bonew\ntexter"
    assert len(changes) == 1
    session.restore(changes[0][0])
    assert session.snapshot() == original
    assert session.selection == (2, 8)


def test_grapheme_navigation_delete_and_transpose_keep_native_composed_characters():
    text = "a🇳🇴é👩‍💻b"
    assert composed_boundaries(text) == [0, 1, 3, 5, 8, 9]
    session = EditorSession(plain(text), boundaries=composed_boundaries)
    session.move("right")
    session.move("right")
    assert session.cursor == 3
    session.delete(backward=True)
    assert session.value.text == "aé👩‍💻b"
    session.select(3, 3)
    session.transpose_characters()
    assert session.value.text == "a👩‍💻éb"


def test_meta_word_movement_does_not_get_stuck_inside_combining_characters():
    session = EditorSession(plain("é word"), boundaries=composed_boundaries)
    session.move("word_right")
    assert session.cursor >= 2
    assert session.cursor in composed_boundaries(session.value.text)
    session.move("word_left")
    assert session.cursor == 0


def test_tab_preferred_column_and_word_case_use_the_shared_editor():
    session = EditorSession(plain("abc\nx\nabcdefgh\nstraße"))
    session.select(3, 3)
    session.move("down")
    assert session.cursor == 5
    session.move("down")
    assert session.cursor == 9
    session.tab()
    assert session.model.paragraphs[2] == "abc  defgh"
    session.select(len(session.value.text) - 6, len(session.value.text) - 6)
    session.edit(session.model.upcase_word)
    assert session.model.paragraphs[-1] == "STRASSE"
    assert len(session.model.styles[-1]) == 7


def test_style_toggles_without_selection_only_change_insertion_style():
    changes = []
    session = EditorSession(on_change=lambda *args: changes.append(args))
    session.toggle_style(1)
    assert not changes
    session.insert("B")
    assert session.value == StyledText("B", (1,))
    session.select(0, 1)
    session.toggle_style(2)
    assert session.value == StyledText("B", (3,))


def test_vertical_movement_after_typing_uses_new_column_and_history_restores_it():
    session = EditorSession(plain("\nx\nabcdef"))
    session.insert("abc")
    session.move("down")
    assert session.cursor == 5
    before = session.snapshot()
    session.insert("!")
    session.restore(before)
    session.move("down")
    assert session.cursor == 9


def test_document_undo_manager_tracks_dirty_state_and_restores_full_snapshot():
    document = PagemarkDocument.alloc().init()
    manager = document.undoManager()
    manager.setGroupsByEvent_(False)
    before = document.session.snapshot()
    assert not document.isDocumentEdited()
    manager.beginUndoGrouping()
    document.session.insert("A😀")
    manager.endUndoGrouping()
    assert document.isDocumentEdited()
    manager.undo()
    assert document.session.snapshot() == before
    assert not document.isDocumentEdited()
    manager.redo()
    assert document.session.value.text == "A😀"
    document.clear_recovery()


def test_native_composition_uses_utf16_and_creates_one_change():
    changes = []
    session = EditorSession(plain("a😀b"), on_change=lambda *args: changes.append(args))
    session.select(1, 2)
    view = PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 800, 600))
    view.session = session
    assert tuple(view.selectedRange()) == (1, 2)
    missing = F.NSMakeRange(F.NSNotFound, 0)
    view.setMarkedText_selectedRange_replacementRange_("e", F.NSMakeRange(1, 0), missing)
    view.setMarkedText_selectedRange_replacementRange_("é", F.NSMakeRange(2, 0), missing)
    assert session.value.text == "aéb"
    assert not changes
    view.insertText_replacementRange_("é", missing)
    assert session.value.text == "aéb"
    assert len(changes) == 1
    assert changes[0][0].value.text == "a😀b"
    session.restore(changes[0][0])
    assert tuple(view.selectedRange()) == (1, 2)


def test_native_spacing_matches_pdf_page_count_and_view_switch_preserves_session():
    session = EditorSession(plain("line\n" * 56))
    session.select(5, 100)
    snapshot = session.snapshot()
    for double in (False, True):
        pdf = pdf_for(session.value, double)
        print_view = PDFPrintView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 1, 1))
        print_view.configure(pdf)
        for pages in (True, False):
            geometry = EditorGeometry(session.layout.line_count, 800, pages, double)
            assert geometry.page_count == print_view.pdf_rep.pageCount()
            assert session.snapshot() == snapshot


def test_recovery_is_atomic_private_and_does_not_open_source_paths(tmp_path, monkeypatch):
    store = RecoveryStore(tmp_path / "recovery")
    identifier = str(uuid.uuid4())
    session = EditorSession(plain("unsaved😀"))
    session.select(1, 6)
    snapshot = session.snapshot()
    title = str(tmp_path / "this-source-does-not-exist.txt")
    store.write(identifier, snapshot, title, b"saved\r\n")
    assert store.read(identifier) == (snapshot, title, b"saved\r\n")
    assert store.path(identifier).stat().st_mode & 0o777 == 0o600
    assert not Path(title).exists()
    def fail_replace(*args):
        raise OSError("disk error")
    monkeypatch.setattr("pagemark_app.recovery.os.replace", fail_replace)
    session.insert("new")
    with pytest.raises(OSError, match="disk error"):
        store.write(identifier, session.snapshot(), title)
    assert store.read(identifier)[0] == snapshot
    assert list(store.directory.glob(".recovery-*")) == []
    store.remove(identifier)
    assert store.identifiers() == []


def test_recovery_rejects_traversal_and_oversized_style_runs(tmp_path):
    import json
    store = RecoveryStore(tmp_path)
    with pytest.raises(ValueError):
        store.read("../../document")
    identifier = str(uuid.uuid4())
    store.write(identifier, Snapshot(plain("x"), 0, None, 0), "test")
    record = json.loads(store.path(identifier).read_text())
    record["styles"] = [[10**12, 1]]
    store.path(identifier).write_text(json.dumps(record))
    with pytest.raises(ValueError, match="formatting"):
        store.read(identifier)


def test_safe_save_roundtrip_updates_baseline_and_clears_only_private_recovery(tmp_path, monkeypatch):
    store = RecoveryStore(tmp_path / "private")
    monkeypatch.setattr("pagemark_app.application.recovery_store", lambda: store)
    document = PagemarkDocument.alloc().init()
    original = b"A\bA\r\n"
    document.readFromData_ofType_error_(F.NSData.dataWithBytes_length_(original, len(original)), "public.plain-text", None)
    document.session.select(2, 2)
    document.session.insert("new\n")
    document.writeRecovery_(None)
    assert store.identifiers() == [document.recovery_id]
    destination = tmp_path / "selected.txt"
    url = F.NSURL.fileURLWithPath_(str(destination))
    ok, error = document.writeSafelyToURL_ofType_forSaveOperation_error_(url, "public.plain-text", A.NSSaveAsOperation, None)
    assert ok and error is None
    assert destination.read_bytes() == b"A\bA\r\nnew\r\n"
    assert document.original_bytes == destination.read_bytes()
    assert store.identifiers() == []


def test_failed_save_keeps_recovery_and_edits(tmp_path, monkeypatch):
    store = RecoveryStore(tmp_path / "private")
    monkeypatch.setattr("pagemark_app.application.recovery_store", lambda: store)
    document = PagemarkDocument.alloc().init()
    document.session.restore(Snapshot(StyledText("_", (1,)), 1, None, 1))
    document.writeRecovery_(None)
    url = F.NSURL.fileURLWithPath_(str(tmp_path / "selected.txt"))
    ok, error = document.writeSafelyToURL_ofType_forSaveOperation_error_(url, "public.plain-text", A.NSSaveAsOperation, None)
    assert not ok and error is not None
    assert document.session.value == StyledText("_", (1,))
    assert store.identifiers() == [document.recovery_id]


def test_cancel_composition_restores_selection_without_creating_an_edit():
    changes = []
    session = EditorSession(plain("replace"), on_change=lambda *args: changes.append(args))
    session.select(0, 7)
    before = session.snapshot()
    view = PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 800, 600))
    view.session = session
    view.setMarkedText_selectedRange_replacementRange_("候", F.NSMakeRange(1, 0), F.NSMakeRange(F.NSNotFound, 0))
    view.doCommandBySelector_("cancelOperation:")
    assert session.snapshot() == before
    assert not changes


def test_accessibility_uses_utf16_grapheme_and_shared_visual_line_ranges():
    view = PagemarkEditorView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 800, 600))
    # Use production attachment, which installs Cocoa's grapheme segmenter.
    view.configure(SimpleNamespace(session=EditorSession(plain("a😀\né🇳🇴"))))
    assert view.accessibilityNumberOfCharacters() == 10
    assert tuple(view.accessibilityRangeForIndex_(7)) == (6, 4)
    assert tuple(view.accessibilityRangeForLine_(0)) == (0, 4)
    assert view.accessibilityStringForRange_(F.NSMakeRange(1, 2)) == "😀"
    assert view.accessibilityLineForIndex_(6) == 1
    frame = view.accessibilityFrameForRange_(F.NSMakeRange(0, 10))
    assert frame.size.height > view.geometry.line_height


def test_booklet_uses_shared_imposition_and_warns_on_unprintable_characters():
    from pagemark_app.application import render_pdf
    value = plain("\n".join("😀" if i == 0 else str(i) for i in range(54 * 5)))
    pdf, warning = render_pdf(value, booklet=True)
    view = PDFPrintView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 1, 1))
    view.configure(pdf)
    assert view.pdf_rep.pageCount() == 4  # five reading pages padded to eight, two per side
    assert view.page_size == (792, 612)
    assert warning is not None
