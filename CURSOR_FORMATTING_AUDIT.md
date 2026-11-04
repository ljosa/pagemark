# Cursor movement and formatting audit

Reviewed on 2026-11-03 at commit
`dffa61c5550183f4c75450514c598f87aee44056`, after the fixes in
[BUG_AUDIT.md](BUG_AUDIT.md). **Nine additional confirmed findings: BUG-31
through BUG-39.** Application code was not changed during the original review.

**Status, 2026-11-04:** All nine findings are fixed. Layout now owns source,
style, and caret mappings; typed viewport rows own scrolling; navigation owns
preferred-column and insertion-style transitions; styled range replacement
owns document edits. The original reproductions now run in the default suite.
See [ARCHITECTURE.md](ARCHITECTURE.md) for contracts and validation. The evidence
and source line numbers below describe the original audited revision.

The most serious finding is a crash when deleting selected paragraphs after
scrolling, or undoing a multiline paste. BUG-32 is a cursor regression exposed
by the recent BUG-6 exact-width wrapping fix; the earlier tests missed the
separator between a full line and the next wrapped word.

## Reproduction results

Run from the repository root:

```sh
.venv/bin/python -m pytest tests/test_cursor_formatting_regressions.py -q --tb=short
```

Originally observed: **26 failed, 2 passed in 5.89 seconds** on Python 3.12.2/macOS.
The original failures asserted the expected behavior, grouped under
nine root causes. The passing controls are ordinary Down preserving the
column (BUG-34) and backward selection followed by Tab (BUG-39).

The [regression file](tests/test_cursor_formatting_regressions.py) now participates
in normal test discovery. Its 28 original cases pass, with four additional
transaction and range-replacement checks. Most cases use
real keyboard parsing, editor commands, model, and view with a stub terminal.
Clipboard access is stubbed and settings persistence disabled. Two tests
launch the actual application in a pseudo-terminal: the deletion crash and
ineffective Page Up. Those tests use temporary files and clean up their
processes. The exact-width cursor collision was also verified interactively
through the terminal harness, with screen coordinates recorded below.

Unless stated otherwise, positions are zero-based, paragraphs contain plain
text, and the text width is the default 65 columns.

| ID | Severity | Confirmed behavior |
| --- | --- | --- |
| BUG-31 | High | Deleting a scrolled selection or undoing a multiline paste crashes the editor. |
| BUG-32 | Medium | A full-width wrapped line places its separator cursor on the next row; Right stalls visually and Down skips content. |
| BUG-33 | Medium | Page Up can leave the viewport unchanged at a page boundary. |
| BUG-34 | Medium | Shift+Up/Down loses the desired column after crossing a short line. |
| BUG-35 | Medium | Up/Down after search, undo, or redo uses an obsolete column. |
| BUG-36 | Medium | Vertical navigation retains the source text's insertion formatting. |
| BUG-37 | Medium | Ordinary document text containing `─` and `Page` is treated as a page marker. |
| BUG-38 | Medium | Centering uses character count instead of display width. |
| BUG-39 | Low | Tab uses the selection endpoint's column rather than the replacement position. |

## BUG-31: Shrinking a scrolled document crashes before the view can recenter

**Source:** [pagemark/view.py](pagemark/view.py), `render`, lines 622–625;
[pagemark/model.py](pagemark/model.py), `delete_selection`, line 1000;
[pagemark/editor.py](pagemark/editor.py), `_apply_snapshot`, line 397.

**Reproduce:** Open a file consisting of 40 paragraphs of `abc`. Starting at
the document beginning in an 80×24 terminal, press Shift+Down 39 times, then
Backspace. The selection starts at paragraph 0, but the viewport has scrolled
to later paragraphs. Reproduced with typing `X`, Enter, and Ctrl-X as well.

A second trigger: in an empty document, paste the same 40 paragraphs and
immediately undo.

**Expected:** The edit/undo succeeds and the viewport recenters on the
remaining document.

**Actual:** `IndexError: list index out of range` at:

```python
para = self.model.paragraphs[paragraph_index]
```

The actual terminal process exited with status **1** and printed this
traceback. In the component deletion reproduction, the document had already
shrunk to one paragraph, but `start_paragraph_index` was still 24. In the
paste/undo reproduction, the stale viewport index was 27.

**Cause:** `render()` reads `start_paragraph_index` before validating it against
the new paragraph count. It clamps the wrapped-line offset later, but never
clamps this paragraph index before dereferencing it. Its eventual cursor
visibility/recentering logic is therefore unreachable.

**Impact:** Ordinary editing exits the application. The deletion throws before
`EditCommand.execute` pushes its undo entry or the event loop records the edit
for autosave. Work since the last save/autosave can be lost.

**Fix direction:** Reconcile the viewport anchor with the current model before
any paragraph lookup, including after snapshot restoration. Cover both edits
and undo with the real renderer; a mocked `view.render()` hides this failure.

## BUG-32: A separator after an exactly full line has inconsistent cursor coordinates

**Source:** [pagemark/view.py](pagemark/view.py),
`_set_visual_cursor_position`, especially line 801; `move_cursor_down` and
`_visual_y_to_document_line`.

**Reproduce:** Use these paragraphs:

```python
['a ' + 'b' * 63 + ' next', 'last']
```

The first paragraph displays as a full 65-column line followed by `next`.
From the beginning, press Right 65 times. This reaches the separator space
between the full line and `next`. Then try Right, or independently try Down.

**Expected:** Character-to-row mapping and vertical movement agree about which
line contains the cursor. Moving between adjacent ordinary ASCII positions
should not collapse both positions onto the same drawn cursor location.

**Actual:**

- At character 65, the line mapper says line 0, but the view draws row 1,
  column 0.
- Right advances to character 66, the actual `n` of `next`, but the cursor
  remains at row 1, column 0.
- Down from character 65 goes directly to paragraph 1 (`last`), skipping
  the logical wrapped line containing `next`.

Actual screen positions in an 80-column terminal, whose text margin is 7:

| Character index | Screen `(row, column)` |
| --- | --- |
| 64 | `(0, 71)` |
| 65 | `(1, 7)` |
| 66 | `(1, 7)` |

**Cause:** The mapper consumes the separator with the preceding line and sets
its boundary at index 66. The cursor painter nevertheless wraps the index-65
cursor visually because its column equals the text width. Vertical navigation
then trusts the painted row rather than the mapper's logical line.

**Relation to the previous fixes:** The BUG-6 change allows this ordinary word
sequence to fill the line exactly. Its regression tests covered paragraph-end
continuations and wrapping output, but not cursor positions on a consumed
separator before more text. A randomized navigation probe found the same
mismatch with em dashes and wide characters; the example above reduces it to
ASCII at the normal width.

**Fix direction:** Give full-line separator positions a consistent representation
across wrapping, cursor painting, and vertical navigation. Test every position
around the boundary, including Right/Left and Up/Down, while retaining the
correctly fitting word.

## BUG-33: Page Up's cursor clamp can undo its own scrolling

**Source:** [pagemark/view.py](pagemark/view.py), `scroll_page_up`, lines
1127–1160, especially `approx_bottom` at line 1154.

**Reproduce:** Open 100 one-line paragraphs named `row000` through `row099`.
In a five-row terminal (four content rows plus status), press Down 57 times.
The viewport now starts at `row054`, with the cursor at `row057`. Press Page Up.

**Expected:** The viewport moves upward. With the two-row overlap and the
intervening page marker, the target top is `row053`.

**Actual:** The top row remains **`row054`**. This is reproduced in the actual
terminal application, not just by assigning an internal scroll position.

The same calculation error occurs with a larger viewport. With 24 content
rows, top paragraph 54, and cursor paragraph 77, Page Up targets top 33 but
ends at top **44** instead.

**Cause:** The scrolling calculation accounts for page-marker rows, but the
subsequent cursor clamp uses `new_top + num_rows - 1` as if all rows contained
document text. It places the cursor below the actual visible content. The
ensuing `render()` recenters again, moving away from the requested scroll
position; in the small-window case, it restores the original viewport.

**Fix direction:** Clamp the cursor against the actual visible document lines
at the target viewport, including marker rows, before rendering. Cover both
single- and double-spacing boundaries.

## BUG-34: Vertical selection forgets its desired column on a short line

**Source:** [pagemark/commands.py](pagemark/commands.py),
`SelectionMovementCommand.execute`, lines 297–310.

**Reproduce:** Use paragraphs `abcdefghij`, `x`, `abcdefghij`. Move to column
8 of the first paragraph and press Shift+Down twice.

**Expected:** The middle line clamps the cursor temporarily to column 1, then
the third line restores column 8, extending the selection to that point.

**Actual:** The final cursor is at paragraph 2, column **1**. A passing control
using ordinary Down twice reaches column **8**.

**Cause:** The selection movement base class always calls
`view.update_desired_x()`. It overwrites the desired column with the short
line's clamped column after the first vertical move. Ordinary Up/Down
explicitly avoid that update.

**Fix direction:** Preserve desired X during vertical selection movement;
refresh it for horizontal selection movement. Cover both directions and
wrapped/hanging-indented paragraphs.

## BUG-35: Search and undo/redo restore the cursor but not the desired column

**Source:** [pagemark/editor.py](pagemark/editor.py), `_move_cursor_to`
(line 656) and `_apply_snapshot` (line 371).

**Reproduce:** Use paragraphs `abcdefghij` and `0123456789`.

| Action before Down | Restored/current column | Column after Down |
| --- | --- | --- |
| From Home, Ctrl-F, `h`, Enter | 7 | **0** |
| At column 3, type `X`, then undo | 3 | **4** |
| At column 3, type `X`, undo, Home, redo | 4 | **0** |

**Expected:** Down preserves the column established by the search or history
operation, rather than an unrelated older column.

**Cause:** Both paths change the model cursor and rerender, but leave
`view.desired_x` unchanged. The next vertical command uses that stale cache.
This differs from BUG-34: here the cache needs refreshing after a nonvertical
relocation; there it must survive temporary clamping during a vertical move.

**Fix direction:** Define how desired X is restored on search acceptance,
search cancellation, and history restoration, and update it consistently.

## BUG-36: Vertical navigation leaves typing in the source paragraph's style

**Source:** [pagemark/view.py](pagemark/view.py),
`_move_cursor_to_visual_line` (line 885), the off-screen movement helpers
(lines 939 and 992), and `_set_cursor_to_doc_line_desired_x` (line 1073).
The intended inheritance rule is documented in
[pagemark/model.py](pagemark/model.py), `_update_caret_style_from_position`
(line 115).

**Reproduce:** Start with a bold paragraph `abcd` followed by a plain paragraph
`abcd`. Move Right once in the bold paragraph, Down once into the plain
paragraph, then type `Q`.

**Expected:** `aQbcd` in the plain paragraph remains plain: insertion inherits
the style at its new position, just as horizontal movement does.

**Actual:** Only `Q` is bold. Its stored flag is `1` rather than `0`, so the
unexpected formatting appears on screen and survives saving. The reverse
case, plain source to underlined target, produces a plain `Q` instead of
underlined. Both cases were also reproduced with Page Down moving the cursor.

**Cause:** The view movement helpers assign cursor coordinates directly and
render, bypassing `_update_caret_style_from_position()`. Horizontal/word
movement methods in the model do refresh the insertion style.

**Fix direction:** Route cursor changes through a consistent model-level path
or explicitly refresh caret formatting in every navigation path that relocates
the cursor. Avoid changing the desired-column preservation rules while doing so.

## BUG-37: Document content is mistaken for a synthetic page marker

**Source:** [pagemark/view.py](pagemark/view.py), `_is_page_break_line`
(line 481) and its callers in cursor mapping and selection rendering.

**Reproduce:** Use these three paragraphs:

```python
['abc', '─ Page 2 ─', 'xyz']
```

From the beginning, press Down. Separately, use End and Shift+Left three times
to select `xyz`.

**Expected:** Down positions the cursor on the middle content row. Selecting
`xyz` highlights that text on the last row.

**Actual:** After Down, the model cursor is at paragraph 1, column 0, but the
screen cursor is on **row 2**, over `xyz`. The `xyz` selection exists in the
model, yet its rendered selection ranges are `[None, None, None]`.

**Cause:** `_is_page_break_line()` identifies markers by the substring test
`'─' in line and 'Page' in line`. It cannot distinguish a synthetic row from
ordinary document content. Navigation skips the content row, while selection
mapping fails to advance its paragraph index for it.

**Fix direction:** Track row metadata separately from rendered text, or keep
an explicit set of synthetic marker row indices. Tightening the string match
alone would still collide with a document containing the exact marker text.

## BUG-38: Centering disagrees with the renderer about text width

**Source:** [pagemark/model.py](pagemark/model.py), `center_line`, lines
533–579, particularly the two uses of `len(stripped)`.

**Reproduce:** At width 65, independently try centering:

| Paragraph | Actual display width | Expected | Actual |
| --- | --- | --- | --- |
| 40 em dashes | 80 (`—` displays as `--`) | Reject as too wide | Accepts, adds 12 spaces, expands the rendered paragraph from 2 lines to 3 |
| 40 `界` characters | 80 | Reject as too wide | Same incorrect acceptance and padding |
| 40 decomposed `e\u0301` sequences | 40 | Accept, add 12 spaces | Rejects because the string has 80 codepoints |

**Cause:** Centering checks and calculates padding using codepoint count.
Wrapping and cursor layout now use display-cell width. This is a remaining
width inconsistency in the centering operation, separate from the cursor
mapping fixed in BUG-30.

**Fix direction:** Use the shared document display width for the fit check and
padding, while retaining character indices for style masks and cursor offsets.

## BUG-39: Replacing a selection with Tab uses the wrong starting column

**Source:** [pagemark/commands.py](pagemark/commands.py), `TabCommand._edit`,
lines 178–190.

**Reproduce:** With `abcdef` and the cursor at the beginning, press Shift+Right
three times to select `abc`, then Tab. Compare selecting the same range
backward from column 3 and then pressing Tab.

**Expected:** Both operations replace the selection at column 0 and advance
to the next five-column tab stop: `'     def'`, cursor column 5.

**Actual:** Forward selection yields **`'  def'`, column 2**. Backward selection
correctly yields five spaces and column 5; this is the passing control case.

**Cause:** Tab calculates `spaces_to_insert` from the current cursor column
before deleting the selection. Deletion moves the insertion point to the
selection start, but the command retains the old space count.

**Fix direction:** Delete the selected range first, then measure the insertion
column and calculate the next tab stop. Cover both selection directions and
ranges crossing wrapped lines.
