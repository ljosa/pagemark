"""Native bridge checks without launching windows or submitting print jobs."""
from __future__ import annotations

import sys

import pytest

if sys.platform != "darwin":
    pytest.skip("Requires macOS AppKit", allow_module_level=True)
F = pytest.importorskip("Foundation")

from pagemark_app.application import PDFPrintView, PagemarkDocument, attributed, pdf_for, styled  # noqa: E402
from pagemark_app.codec import StyledText  # noqa: E402


def test_native_document_read_write_keeps_exact_file_bytes():
    original = "A\bA _\bÉ\r\n😀\r\n".encode()
    data = F.NSData.dataWithBytes_length_(original, len(original))
    document = PagemarkDocument.alloc().init()
    ok, error = document.readFromData_ofType_error_(data, "public.plain-text", None)
    assert ok and error is None
    saved, error = document.dataOfType_error_("public.plain-text", None)
    assert error is None
    assert bytes(saved) == original
    assert not PagemarkDocument.autosavesInPlace()


def test_native_document_invalid_utf8_reports_error_without_replacing_contents():
    document = PagemarkDocument.alloc().init()
    document.content = StyledText("safe", (0,) * 4)
    data = F.NSData.dataWithBytes_length_(b"\xff", 1)
    ok, error = document.readFromData_ofType_error_(data, "public.plain-text", None)
    assert not ok and error is not None
    assert document.content.text == "safe"


def test_native_attributed_string_roundtrips_unicode_style_positions():
    value = StyledText("é😀\nB_", (1, 2, 0, 3, 0))
    assert styled(attributed(value)) == value


def test_native_print_view_uses_shared_pdf_pagination():
    text = "\n".join(f"Line {number}" for number in range(60))
    pdf = pdf_for(StyledText(text, (0,) * len(text)))
    view = PDFPrintView.alloc().initWithFrame_(F.NSMakeRect(0, 0, 1, 1))
    view.configure(pdf)
    knows, pages = view.knowsPageRange_(None)
    assert knows and tuple(pages) == (1, 2)
    assert view.rectForPage_(1).size == (612, 792)
    assert view.rectForPage_(2).origin == (0, 792)

