"""Find keeps its own feedback and gives the editor all space when closed."""
from types import SimpleNamespace

import pytest

A = pytest.importorskip("AppKit")
F = pytest.importorskip("Foundation")
objc = pytest.importorskip("objc")

from pagemark_app import application, native_find  # noqa: E402
from pagemark_app.codec import StyledText  # noqa: E402
from pagemark_app.session import Snapshot  # noqa: E402


class FindTestField(A.NSView):
    """Stand in for controls that require WindowServer."""
    def initWithFrame_(self, frame):
        self = objc.super(FindTestField, self).initWithFrame_(frame)
        if self is not None:
            self.text = ""
        return self

    @classmethod
    def labelWithString_(cls, text):
        field = cls.alloc().initWithFrame_(F.NSMakeRect(0, 0, 1, 1))
        field.setStringValue_(text)
        return field

    def setStringValue_(self, text):
        self.text = str(text)

    def stringValue(self):
        return self.text

    def setPlaceholderString_(self, text):
        pass

    def setTextColor_(self, color):
        pass

    def setDelegate_(self, delegate):
        self.delegate = delegate


@pytest.fixture
def search_document(monkeypatch, request):
    monkeypatch.setattr(A, "NSSearchField", FindTestField)
    monkeypatch.setattr(A, "NSTextField", FindTestField)
    beeps, focus, refreshes, unmarks = [], [], [], []
    monkeypatch.setattr(A, "NSBeep", lambda: beeps.append(True))
    document = application.PagemarkDocument.alloc().init()
    text = "one TWO one"
    document.session.restore(Snapshot(StyledText(text, (0,) * len(text)), 0, None, 0))
    width, height = getattr(request, "param", (840, 720))
    content = A.NSView.alloc().initWithFrame_(F.NSMakeRect(0, 0, width, height))
    scroll = A.NSView.alloc().initWithFrame_(content.bounds())
    scroll.setAutoresizingMask_(A.NSViewWidthSizable | A.NSViewHeightSizable)
    content.addSubview_(scroll)
    editor = SimpleNamespace(session=document.session, enclosingScrollView=lambda: scroll,
                             unmarkText=lambda: unmarks.append(True),
                             refresh=lambda: refreshes.append(True),
                             window=lambda: SimpleNamespace(makeFirstResponder_=focus.append))
    document.editor = editor
    document.find_bar = native_find.FindBar(editor, document)
    yield SimpleNamespace(document=document, bar=document.find_bar, content=content,
                          scroll=scroll, beeps=beeps, focus=focus, unmarks=unmarks)
    document.editor = document.find_bar = None


@pytest.mark.parametrize("search_document", [(840, 720), (480, 320), (1100, 900)], indirect=True)
def test_reopening_and_closing_find_does_not_accumulate_reserved_space(search_document):
    fixture = search_document
    document, bar = fixture.document, fixture.bar
    before = document.session.snapshot()
    assert bar.view.isHidden()
    assert fixture.scroll.frame() == fixture.content.bounds()
    width, height = fixture.content.bounds().size
    for _ in range(3):
        document.editor_action("find")
        document.editor_action("find")
        assert not bar.view.isHidden()
        assert fixture.focus[-1] == bar.field
        frame = fixture.scroll.frame()
        assert frame.origin.y == bar.HEIGHT
        assert frame.size == (width, height - bar.HEIGHT)
        assert F.NSMaxX(bar.field.frame()) < F.NSMinX(bar.feedback.frame())
        assert F.NSMaxX(bar.feedback.frame()) <= width
        for _ in range(2):
            assert document.control_textView_doCommandBySelector_(bar.field, None, "cancelOperation:")
            assert bar.view.isHidden()
            assert fixture.scroll.frame() == fixture.content.bounds()
            assert fixture.focus[-1] == document.editor
    assert document.session.snapshot() == before
    assert not document.isDocumentEdited()


def test_search_feedback_clears_after_a_match_or_empty_query_without_editing(search_document):
    fixture = search_document
    document, bar = fixture.document, fixture.bar
    before = document.session.value
    document.editor_action("find")
    bar.field.setStringValue_("missing")
    document.performSelector_withObject_("controlTextDidChange:", None)
    assert bar.feedback.stringValue() == "No matches"
    assert document.session.selection == (0, 0)
    assert not fixture.beeps
    bar.field.setStringValue_("two")
    document.controlTextDidChange_(None)
    assert bar.feedback.stringValue() == ""
    assert document.session.selection == (4, 7)
    bar.field.setStringValue_("missing")
    document.controlTextDidChange_(None)
    bar.field.setStringValue_("")
    document.controlTextDidChange_(None)
    assert bar.feedback.stringValue() == ""
    assert document.session.selection == (4, 7)
    assert document.session.value == before
    assert not document.undoManager().canUndo()
    assert not document.isDocumentEdited()


def test_find_next_previous_wrap_and_failure_keep_feedback_in_find_bar(search_document):
    fixture = search_document
    document, bar = fixture.document, fixture.bar
    document.editor_action("find")
    bar.field.setStringValue_("one")
    document.controlTextDidChange_(None)
    assert document.session.selection == (0, 3)
    for command, selection in ((b"insertNewline:", (8, 11)), ("insertNewline:", (0, 3)),
                               ("insertBacktab:", (8, 11))):
        assert document.control_textView_doCommandBySelector_(bar.field, None, command)
        assert document.session.selection == selection
    bar.field.setStringValue_("missing")
    assert document.control_textView_doCommandBySelector_(bar.field, None, "insertNewline:")
    assert fixture.beeps == [True]
    assert bar.feedback.stringValue() == "No matches"
    assert document.session.selection == (8, 11)
    assert not document.control_textView_doCommandBySelector_(bar.field, None, "moveLeft:")
