"""Booklet printing is one operation, independent of later print/export actions."""
from types import SimpleNamespace

import pytest

A = pytest.importorskip("AppKit")
F = pytest.importorskip("Foundation")
objc = pytest.importorskip("objc")

from pagemark_app import application  # noqa: E402
from pagemark_app.codec import StyledText  # noqa: E402
from pagemark_app.session import Snapshot  # noqa: E402


class BookletActionTestDocument(application.PagemarkDocument):
    @objc.python_method
    def report_error(self, error):
        raise AssertionError("A print action failed") from error


class PrintMenuTestApplication(F.NSObject):
    def setWindowsMenu_(self, menu):
        self.window_menu = menu

    def setMainMenu_(self, menu):
        self.main_menu = menu


def test_cancelled_booklet_job_leaves_regular_print_and_export_in_reading_order(monkeypatch):
    document = BookletActionTestDocument.alloc().init()
    text = "\n".join(f"Line {index}" for index in range(54 * 5))
    document.session.restore(Snapshot(StyledText(text, (0,) * len(text)), 0, None, 0))
    unmarks, jobs = [], []
    document.editor = SimpleNamespace(double_spacing=False, unmarkText=lambda: unmarks.append(True))
    before = document.session.snapshot()
    info = document.printInfo()
    original_paper = tuple(info.paperSize())
    original_margins = (info.topMargin(), info.bottomMargin(), info.leftMargin(), info.rightMargin())

    def create_operation(view, print_info):
        job = {"pages": view.pdf_rep.pageCount(), "page_size": tuple(view.page_size),
               "paper_size": tuple(print_info.paperSize())}
        jobs.append(job)

        def cancel():
            # Simulate changes made in the panel before cancellation. These
            # must affect only this operation's copy of the print settings.
            print_info.setPaperSize_((400, 400))
            print_info.setLeftMargin_(25)
            return False

        return SimpleNamespace(setJobTitle_=lambda title: job.update(title=str(title)),
                               runOperation=cancel)  # No native print job or dialog.

    monkeypatch.setattr(A, "NSPrintOperation", SimpleNamespace(
        printOperationWithView_printInfo_=create_operation))
    monkeypatch.setattr(A, "NSDocumentController", SimpleNamespace(
        sharedDocumentController=lambda: SimpleNamespace(currentDocument=lambda: document)))
    delegate = application.PagemarkDelegate.alloc().init()
    delegate.performSelector_withObject_("printBooklet:", None)
    delegate.performSelector_withObject_("printDocument:", None)
    assert [job["pages"] for job in jobs] == [4, 5]
    assert [job["page_size"] for job in jobs] == [(792, 612), (612, 792)]
    for job, expected in zip(jobs, ((792, 612), (612, 792)), strict=True):
        # Native printer settings can round-trip points through metric units.
        assert job["paper_size"] == pytest.approx(expected, rel=0, abs=0.0001)
    assert len(unmarks) == 2
    assert document.session.snapshot() == before
    assert not document.isDocumentEdited()
    assert tuple(info.paperSize()) == original_paper
    assert (info.topMargin(), info.bottomMargin(), info.leftMargin(), info.rightMargin()) == original_margins
    # Export PDF uses this same default output path after either print action.
    exported = application.PDFPrintView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 1, 1))
    exported.configure(document.output_pdf())
    assert exported.pdf_rep.pageCount() == 5
    assert tuple(exported.page_size) == (612, 792)


def test_booklet_action_lives_in_file_menu_and_requires_a_document(monkeypatch):
    app = PrintMenuTestApplication.alloc().init()
    delegate = application.PagemarkDelegate.alloc().init()
    application.configure_menu(app, delegate)
    files = app.main_menu.itemWithTitle_("File").submenu()
    booklet = files.itemWithTitle_("Print Booklet…")
    assert booklet.action() == "printBooklet:"
    assert booklet.target() == delegate
    assert booklet.keyEquivalent() == ""
    assert files.indexOfItem_(booklet) == files.indexOfItem_(files.itemWithTitle_("Print…")) + 1
    assert files.itemWithTitle_("Print…").keyEquivalent() == "p"
    assert app.main_menu.itemWithTitle_("Format").submenu().itemWithTitle_("Booklet Output") is None
    current = [None]
    monkeypatch.setattr(A, "NSDocumentController", SimpleNamespace(
        sharedDocumentController=lambda: SimpleNamespace(currentDocument=lambda: current[0])))
    assert not delegate.validateMenuItem_(booklet)
    current[0] = SimpleNamespace(editor=object())
    assert delegate.validateMenuItem_(booklet)
