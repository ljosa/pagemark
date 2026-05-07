"""Tests for booklet PDF generation."""

import base64
import re
import zlib

from pagemark.pdf_generator import PDFGenerator


def _make_pages(n: int):
    """Make ``n`` minimally-populated source pages (66 lines x 85 chars)."""
    pages = []
    for i in range(n):
        page = [f"Page-{i+1}".ljust(85)]
        page.extend([" " * 85 for _ in range(65)])
        pages.append(page)
    return pages


def _extract_mediaboxes(pdf_bytes: bytes):
    """Return all /MediaBox arrays found in the PDF as lists of floats."""
    boxes = []
    for m in re.finditer(rb"/MediaBox\s*\[\s*([^\]]+)\]", pdf_bytes):
        nums = [float(t) for t in m.group(1).split() if t]
        if len(nums) == 4:
            boxes.append(nums)
    return boxes


def test_booklet_pdf_uses_landscape_pages():
    pdf = PDFGenerator().generate_pdf(_make_pages(4), booklet=True)
    assert pdf.startswith(b"%PDF")
    boxes = _extract_mediaboxes(pdf)
    assert boxes, "expected at least one /MediaBox"
    for box in boxes:
        # llx, lly, urx, ury -- expect landscape letter (792x612)
        assert box[2] - box[0] == 792.0
        assert box[3] - box[1] == 612.0


def test_booklet_pdf_page_count_matches_imposition():
    """For N source pages padded to a multiple of 4, PDF has padded_n / 2 pages."""
    cases = {
        1: 2,    # padded 4 -> 2 sheet sides
        4: 2,
        5: 4,    # padded 8 -> 4 sheet sides
        8: 4,
        9: 6,    # padded 12 -> 6 sheet sides
        12: 6,
    }
    for n, expected_pdf_pages in cases.items():
        pdf = PDFGenerator().generate_pdf(_make_pages(n), booklet=True)
        match = re.search(rb"/Count\s+(\d+)", pdf)
        assert match, f"no /Count in PDF for n={n}"
        assert int(match.group(1)) == expected_pdf_pages, (
            f"n={n}: expected {expected_pdf_pages} PDF pages, got {match.group(1).decode()}"
        )


def test_booklet_pdf_empty_input_yields_empty_pdf():
    pdf = PDFGenerator().generate_pdf([], booklet=True)
    assert pdf.startswith(b"%PDF")
    # No /Type /Page entries (just the Pages catalog -- /Count 0)
    match = re.search(rb"/Count\s+(\d+)", pdf)
    if match:
        assert int(match.group(1)) == 0


def test_booklet_pdf_portrait_path_unchanged_when_disabled():
    """Booklet=False still yields portrait letter pages."""
    pdf = PDFGenerator().generate_pdf(_make_pages(2), booklet=False)
    boxes = _extract_mediaboxes(pdf)
    assert boxes
    for box in boxes:
        assert box[2] - box[0] == 612.0
        assert box[3] - box[1] == 792.0


def _decode_page_streams(pdf_bytes: bytes):
    """Yield decoded text content of each page's content stream, in PDF page order."""
    streams = []
    i = 0
    while True:
        s = pdf_bytes.find(b"\nstream\n", i)
        if s < 0:
            break
        s += 1  # skip leading newline
        e = pdf_bytes.find(b"endstream", s)
        if e < 0:
            break
        payload = pdf_bytes[s + len(b"stream\n"):e].rstrip()
        i = e + len(b"endstream")
        # ReportLab uses ASCII85 + Flate by default.
        if not payload.startswith(b"<~"):
            payload = b"<~" + payload
        if not payload.endswith(b"~>"):
            payload = payload + b"~>"
        try:
            raw = base64.a85decode(payload, adobe=True, ignorechars=b" \t\n\r\v")
            text = zlib.decompress(raw)
        except Exception:
            text = b""
        streams.append(text)
    return streams


def test_booklet_pdf_imposition_order_matches_spec():
    """Decode each PDF page and verify the source-page markers appear in
    saddle-stitch order: front_1=(8,1), back_1=(2,7), front_2=(6,3), back_2=(4,5).
    """
    pages = []
    for i in range(1, 9):
        page = [f"PAGE_{i}".ljust(85)]
        page.extend([" " * 85 for _ in range(65)])
        pages.append(page)

    pdf = PDFGenerator().generate_pdf(pages, booklet=True)
    streams = _decode_page_streams(pdf)
    assert len(streams) == 4, f"expected 4 sheet sides, got {len(streams)}"

    expected = [
        ["PAGE_8", "PAGE_1"],
        ["PAGE_2", "PAGE_7"],
        ["PAGE_6", "PAGE_3"],
        ["PAGE_4", "PAGE_5"],
    ]
    for sheet_side, want in enumerate(expected):
        markers = [m.decode() for m in re.findall(rb"PAGE_\d+", streams[sheet_side])]
        assert markers == want, (
            f"sheet side {sheet_side + 1}: expected {want}, got {markers}"
        )


def test_booklet_pdf_padding_blank_slots_have_no_marker():
    """A 5-page document pads to 8; padded slots (6,7,8) must be blank."""
    pages = []
    for i in range(1, 6):
        page = [f"PAGE_{i}".ljust(85)]
        page.extend([" " * 85 for _ in range(65)])
        pages.append(page)

    pdf = PDFGenerator().generate_pdf(pages, booklet=True)
    streams = _decode_page_streams(pdf)
    # Imposition for n=8: [(7,0),(1,6),(5,2),(3,4)] (0-indexed); pages 5..7 are padding.
    # Front of sheet 1 has padded slots (7=blank, 0=PAGE_1).
    front1_markers = [m.decode() for m in re.findall(rb"PAGE_\d+", streams[0])]
    assert front1_markers == ["PAGE_1"], f"got {front1_markers}"
    # Back of sheet 1: (1=PAGE_2, 6=blank)
    back1_markers = [m.decode() for m in re.findall(rb"PAGE_\d+", streams[1])]
    assert back1_markers == ["PAGE_2"], f"got {back1_markers}"


def test_booklet_pdf_with_styles():
    """Styled runs should still render through the booklet path."""
    pages = _make_pages(2)
    # Add a bold run on the first line of page 0
    page_styles = [
        [[(10, "Page-1", 1)]] + [[] for _ in range(65)],  # page 0
        [[]] * 66,  # page 1
    ]
    pdf = PDFGenerator().generate_pdf(pages, page_styles=page_styles, booklet=True)
    assert pdf.startswith(b"%PDF")
    assert b"Courier-Bold" in pdf
