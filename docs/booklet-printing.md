# Booklet Printing

## Overview

Booklet printing produces a saddle-stitched booklet from the document: PDF
output uses landscape letter sheets, two source pages per side, in imposition
order so a duplex-printed stack folded along the vertical center reads in
natural page order. The result is a half-letter (digest) booklet that works
on any printer that supports duplex.

The feature is exposed as a `[B]ooklet: ON/OFF` toggle in the print dialog
and is persisted per-document via `SessionManager`.

## User-facing behavior

- In the print dialog (`Ctrl-P`), press `B` to toggle booklet mode.
- When ON:
  - The preview shows one landscape sheet at a time, with two source pages
    side by side and a vertical fold-line down the middle.
  - PgUp / PgDn navigates sheet sides (front, back, front, back, …) rather
    than source pages.
  - The bottom-of-preview label reads, e.g., `Sheet 1/2 front: pp. 8, 1`.
    Pages added to pad the document to a multiple of 4 are shown as `blank`.
  - The `[D]ouble-sided` toggle is hidden because booklet printing is
    inherently duplex (and uses short-edge binding, not long-edge).
  - Output goes to the chosen destination (printer or PDF) in imposition
    order on landscape sheets.
- When the terminal is too narrow to fit the wider booklet preview, the
  preview area is replaced with a message indicating the required column
  count; the rest of the dialog remains operable so the user can press `B`
  to disable booklet mode.

## Design decisions

### Saddle-stitch imposition (not simple 2-up)

For an N-page document padded to a multiple of 4, sheet *i* (1-indexed)
holds:

```
front: (left=N - 2i + 2, right=2i - 1)
back:  (left=2i,         right=N - 2i + 1)
```

The sheets are emitted to the PDF in print order — front_1, back_1,
front_2, back_2, … — so that a duplex printer with short-edge binding,
followed by stacking and folding the stack along the vertical center,
yields pages in reading order 1, 2, 3, …, N.

The blank pages required to reach a multiple of 4 are not emitted as
content pages; they are simply *absent* halves on the imposed sheet,
which renders as whitespace.

### Half-letter scaling, not 1/√2 (no DIN paper sizes)

Pagemark sources are 8.5"×11" (letter portrait). Two of those would need
17"×11" (tabloid landscape) to fit at full size. To preserve "any printer
works", we scale each source page proportionally to fit the half-sheet
width of letter landscape:

```
scale  = 5.5"  / 8.5"  ≈ 0.647
height = 11.0" × 0.647 ≈ 7.12"
```

Each source page therefore lands on a 5.5" × 7.12" area, vertically
centered on the half-sheet (≈0.69" of whitespace at top and bottom).
Aspect ratio is preserved; text becomes ~7.76 pt for Courier 12 and
~6.47 pt for Prestige Elite 10 — small but readable for digest output.

### Short-edge duplex, not long-edge

Pagemark already supports duplex printing via `sides=two-sided-long-edge`.
Booklet sheets are landscape, and the fold is the vertical center of the
landscape page — which is the short edge. For the back side to align
correctly with the front when folded, the printer must flip along the
short edge. The booklet path therefore overrides the duplex CUPS option
to `sides=two-sided-short-edge`. The `[D]ouble-sided` toggle is hidden in
booklet mode because the choice is no longer free — the code always
requests duplex with short-edge binding.

### Explicit `-o landscape` to lpr

The booklet PDF declares a landscape MediaBox (792×612). PDF viewers
read this directly and lay the page out landscape — so saving to PDF
"just works". CUPS/lpr, however, doesn't always honor MediaBox on its
own: some printer drivers fall back to a portrait page and clip the
content. The print-to-printer path therefore explicitly passes
`-o landscape` (i.e. `orientation-requested=4`) when booklet is on, so
the driver lays out the sheet in landscape regardless of its default.
This option is *not* passed for non-booklet output, which remains
portrait.

### Preview shows imposed sheets, not raw pages

`[B]ooklet` does not just widen the preview — it changes *what* is
previewed. Each preview corresponds exactly to one PDF page: a landscape
sheet with the two source pages that the imposition algorithm placed on
that sheet side. Navigation iterates sheet sides, and the page label
shows the source page numbers landing on the current sheet. This keeps
the preview true to the printer/PDF output.

### Narrow-terminal fallback: refuse with message

The booklet preview is approximately twice as wide as the single-page
preview. The exact requirement is computed from the font's full-page
width: roughly 124 columns for Courier (10-pitch, 85-col page) and 140
for Prestige Elite (12-pitch, 102-col page). On terminals narrower than
this we replace the preview with a wrapped message that names the
required column count and tells the user how to disable booklet mode
(press `B`). The rest of the dialog still renders, and the toggle keys
still work, so the user is never trapped — and the layout shrinks the
fallback box so the options column always fits within `term.width`.

We deliberately do *not* try to shrink the preview to fit — at quadrant
resolution, dropping below the natural 2-chars-per-cell density loses
information that defeats the purpose of a true preview.

## Architecture

### New modules

- `pagemark/booklet.py` — pure imposition logic, no rendering dependencies.
  - `pad_to_multiple_of_4(n)` rounds up to the nearest multiple of 4.
  - `imposition_order(n)` returns `[(left_idx, right_idx), …]` for each
    sheet side in print order. Indices are 0-based into the padded
    page list; out-of-range indices indicate padding (blank halves).

### Modified modules

- `print_preview.py` — adds `generate_sheet_preview` and
  `generate_sheet_preview_with_border` rendering two source page previews
  side by side with a fold line.
- `pdf_generator.py` — refactors per-line drawing into
  `_render_source_page` so both the portrait path and the new booklet
  path share a single implementation. The booklet path uses
  `landscape(letter)`, calls `imposition_order`, and translates+scales
  each source page onto its half-sheet via `c.saveState()` /
  `c.translate()` / `c.scale()`.
- `print_output.py` — both `print_to_printer` and `save_to_file` accept a
  `booklet` flag. The printer path requests
  `sides=two-sided-short-edge` when booklet is on, regardless of
  the `double_sided` argument.
- `print_dialog.py` — adds the `[B]ooklet` toggle, sheet-side navigation,
  preview swap, narrow-terminal message, and threading via the new
  `PrintOptions.booklet` field. `[D]ouble-sided` is hidden when booklet
  is on.
- `editor.py` — threads `result.booklet` from the dialog to
  `_print_to_printer` and `_save_to_pdf` (including the deferred PDF
  filename prompt).
- `session.py` and `settings_persistence.py` — adds the persistable
  `BOOKLET` boolean key.

## Testing strategy

- `tests/test_booklet_imposition.py` — pure-function tests for
  `pad_to_multiple_of_4` and `imposition_order` over 0, 1, 4, 5, 8, 12
  pages, including a property test that every padded index appears
  exactly once across all sides and a fold-order check that pages 1, 2,
  3, … land in reading order.
- `tests/test_booklet_preview.py` — sheet preview width is exactly
  2× single-page preview width; out-of-range indices produce blank
  halves; fold-line and border characters land in the right columns;
  contents from each of two distinct source pages appear in the
  corresponding half.
- `tests/test_booklet_pdf.py` — PDF MediaBoxes are landscape letter
  (792×612 pt) when booklet is on and portrait letter (612×792 pt) when
  off; PDF page count equals `pad_to_multiple_of_4(N) / 2`. The
  imposition is verified end-to-end by decoding each PDF page's content
  stream (ASCII85 + Flate) and asserting the expected `PAGE_n` markers
  appear in the order the algorithm specifies (e.g., for N=8:
  `[8,1], [2,7], [6,3], [4,5]`). Padding is verified by feeding 5
  source pages and confirming padded slots render as blank halves.
- `tests/test_booklet_dialog.py` — defaults, restoration from session,
  toggle effects on `imposed_sides`, sheet-vs-page navigation count,
  required dialog width grows in booklet mode, narrow-terminal fallback
  message renders at 80 cols, full preview renders at 140 cols,
  `[D]ouble-sided` is hidden when booklet is on, `PrintOptions.booklet`
  is propagated, and blank-slot labeling.
- `tests/test_print_output.py` — added cases verifying the printer
  command line uses `sides=two-sided-short-edge` whenever
  `booklet=True`, and that PDF saves produce landscape pages.

## Files

### New
- `pagemark/booklet.py`
- `docs/booklet-printing.md`
- `tests/test_booklet_imposition.py`
- `tests/test_booklet_preview.py`
- `tests/test_booklet_pdf.py`
- `tests/test_booklet_dialog.py`

### Modified
- `pagemark/pdf_generator.py`
- `pagemark/print_dialog.py`
- `pagemark/print_output.py`
- `pagemark/print_preview.py`
- `pagemark/editor.py`
- `pagemark/session.py`
- `pagemark/settings_persistence.py`
- `tests/test_print_output.py`
- `tests/test_print_integration.py`
- `README.md`
