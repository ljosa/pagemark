# Tickets

Numbering continues from `BUGS.md` (BUG-5 through BUG-7 are still open there;
BUG-4 was fixed together with BUG-14). BUG-8 and BUG-9 together explain the
reported "cursor refuses to move down / gets stuck" symptom; they share a
root cause and were fixed together.

All bugs below (BUG-8 through BUG-21) were fixed on 2026-07-09, each with a
regression test that fails on the pre-fix code. The ENH tickets at the end
remain open.

---

## BUG-8: Cursor placed exactly on a wrap boundary is treated as being on the next visual line, breaking up/down movement

**Severity:** High
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/view.py:65-79` (`line_for_char_index`), `pagemark/view.py:161-176` (`line_content_length`), `pagemark/view.py:846-847` and `pagemark/view.py:920-921` (desired-x clamping)

`VisualLineMapper.cumulative_counts` marks the end of each visual line, and
`line_for_char_index` deliberately treats a character index that equals a
boundary as the *start of the next line*. But `line_content_length()` returns
`line_end - line_start`, which **includes the invisible separator space** that
word wrap consumed. So when `_move_cursor_to_visual_line()` /
`_char_index_for_desired_x()` clamp `desired_x` to the target line's content
length, the cursor can land exactly on the boundary index — and is then
logically on the line *after* the one the user targeted.

Consequences (all reproduced with a brute-force harness):

1. **Up-arrow gets permanently stuck.** Moving up from a long line onto a
   shorter wrapped line lands on the boundary, which maps back to the line the
   cursor came from. Because `desired_x` is preserved across presses, every
   subsequent Up press repeats the same failed move. Repro (20-column view):

   ```python
   para = "aaa bbb cccccccccccccccccc ddd"
   # visual lines: ['aaa bbb', 'cccccccccccccccccc', 'ddd'], counts [8, 27, 30]
   # cursor at end of line 1, desired_x = 18; move_cursor_up() lands at
   # char 8 == counts[0]  ->  still on line 1, forever.
   ```

2. **Down-arrow skips a visual line.** Moving down from a long line onto a
   shorter wrapped line lands on the boundary and the cursor jumps to the
   start of the line *below* the target (2 lines at once).

3. It seeds BUG-9's dead Down press (see below), because ordinary Right-arrow
   movement across a wrap boundary also puts the cursor on a boundary index.

**Fix direction:** after computing `char_index` in
`_move_cursor_to_visual_line()` and `_char_index_for_desired_x()`, ensure the
result still maps to the requested line, e.g.:

```python
char_index = mapper.line_and_column_to_char(line_within_para, content_x)
if mapper.line_for_char_index(char_index) != line_within_para:
    char_index -= 1  # stepped onto the separator space; stay on this line
```

or make `line_content_length()` exclude the wrap separator (it must NOT be
excluded for the last line of a paragraph or for lines produced by breaking an
over-long word, which consume no separator). Add a regression test asserting
that repeated Up/Down presses move monotonically through every visual line of
a wrapped document for arbitrary `desired_x`.

---

## BUG-9: Down-arrow does nothing when the cursor sits on a wrap boundary at the bottom of the screen; cursor is also drawn on the wrong line

**Severity:** High — this is the reported "cursor refuses to move down" bug
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/view.py:632` (`end_position` off-by-one), `pagemark/view.py:727-733` (visual_cursor_y clamp), `pagemark/view.py:925-953` (`_move_cursor_down_in_document`)

`render()` computes `end_position = line_end(last_line) + 1` and treats
`cursor < end_position` as "in view". A cursor whose character index equals
`line_end(last_line)` (a wrap boundary — reachable by pressing Right across
the boundary, by paste, or via BUG-8) is logically on the **first visual line
below the view**, yet render considers it visible. `_set_visual_cursor_position`
then computes a `visual_cursor_y` one past the bottom row and clamps it back
to the bottom row.

Deterministic repro (4-row, 20-column view, 6-line paragraph, view showing
lines 0–3):

```
cursor at last char of bottom row (line 3), press Right twice:
  char=80 == counts[3]  -> logically line 4 (below view),
  but drawn at visual_y=3, visual_x=0   <- cursor visibly jumps to the START
                                           of the bottom line (wrong place)
press Down:  doc_line 4 -> 4, char unchanged   <- DEAD PRESS
press Down again: works (view recentered on the failed press)
```

Two user-visible symptoms:

1. After crossing a wrap boundary at the bottom of the screen, the cursor is
   drawn at column 0 of the *previous* line — it appears to jump backward.
2. The next Down press does nothing: `_move_cursor_down_in_document()` targets
   "the line below the view", which is the line the cursor is already
   logically on, so the cursor doesn't advance (with a large `desired_x` it
   moves *sideways* within the same line). Only the second press moves.

With BUG-8 feeding boundary landings during normal up/down navigation, users
intermittently experience Down presses that do nothing — matching the report.
(A fuzz harness over random documents/geometry found dozens of such states,
including with double-spacing and page breaks.)

**Fix direction:** make render's visibility test consistent with
`line_for_char_index` semantics — a cursor at `line_end(last_visible_line)` of
a wrapped line is *outside* the view (drop the `+1`, or compare using the
mapper's line index instead of raw character comparisons). Then a boundary
cursor at the bottom of the screen triggers recentering during render, and
Down moves normally. Fixing BUG-8's clamping removes most sources of boundary
landings, but Right-arrow across a boundary still creates them, so both ends
need the fix.

---

## BUG-10: Alt-M (center line) shifts bold/underline off the text and onto the inserted spaces

**Severity:** Medium
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/model.py:530-572` (`center_line`)

`center_line()` rewrites the paragraph text (`spaces + stripped`) but never
touches `self.styles[para_idx]`. The style mask stays aligned to the *old*
character positions, so the formatting visually slides left/right by the
change in leading whitespace.

Repro: type `BOLD`, select it, Ctrl-B, then Alt-M in a 20-column view:

```
paragraph: '        BOLD'
styles:    [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]   # the 4 leading spaces are
                                                   # "bold"; BOLD is plain
```

The corruption persists in the saved overstrike file. Undo restores it, but
re-centering re-corrupts.

**Fix:** rebuild the style mask alongside the text:
`self.styles[para_idx] = [0]*spaces_needed + old_styles[lead:lead+len(stripped)]`
(where `lead` is the old leading-space count), mirroring what the text
transformation does. Same review should be applied to any other method that
rewrites paragraph text — `downcase_word`/`upcase_word`/`capitalize_word` keep
length so they are safe, but they'd silently misalign if that ever changes.

---

## BUG-11: Paste does not sanitize clipboard text — `\r`, tabs, and control characters enter the document

**Severity:** Medium
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/model.py:1068-1081` (`paste`), `pagemark/clipboard.py:104-115`

`paste()` splits clipboard text on `'\n'` only. Clipboard content with CRLF
line endings (common when copying from web pages, Windows files, some email
clients) leaves a trailing `\r` on every paragraph; tabs and other control
characters also pass straight through. Typed input is filtered
(`InsertTextCommand` rejects `ord(char) < 32`), but paste bypasses that
filter.

Consequences: the terminal renders these characters with a different width
than the editor's width math assumes (a tab occupies several columns, `\r` is
invisible), so the drawn cursor position drifts from the logical position for
the rest of the line — which users experience as the cursor being "in the
wrong place" — and the characters are written into saved files.

**Fix:** normalize in `paste()` before insertion: `\r\n`/`\r` → `\n`, expand
or replace tabs, strip remaining control characters (and apply the same
normalization to both the styled and plain-text paths, keeping the style
arrays in sync when characters are dropped).

---

## BUG-12: `insert_text()` ignores its `position` parameter

**Severity:** Low (latent API bug)
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/model.py:200-212`

`insert_text(text, position=...)` computes the view-adjustment flags
(`before_view`, `in_view`) from `position`, but performs the actual insertion
at `self.cursor_position` regardless. No current caller passes an explicit
position, so this is latent — but the first caller that does will corrupt the
document/view state. Either implement it properly or drop the parameter.

---

## BUG-13: Answering "y" to "Save file?" on quit discards the document if the save fails

**Severity:** High
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/editor.py:843-851` (`_handle_quit_confirm`)

```python
if char == 'y':
    if self.filename:
        self.save_file(self.filename)
        self.running = False
```

`save_file()` returns `False` on failure (permission denied, disk full, …),
but the return value is ignored and the editor exits unconditionally — the
user's changes are lost and the error status message is never shown.

**Scenario:** file becomes read-only while editing → Ctrl-Q → "y" → save
fails silently, editor quits, work is gone.

**Fix:** gate the quit on success, as `_handle_filename_prompt` already does
(`editor.py:781`): `if self.save_file(self.filename): self.running = False`,
otherwise drop back to the editor so the status message is visible.

---

## BUG-14: RTF paste fidelity — five parser defects beyond BUG-4

**Severity:** Medium (each reproduced by executing `parse_rtf`)
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/rtf_parser.py`

1. **Hex escapes decoded as raw codepoints instead of cp1252**
   (`rtf_parser.py:142-152`). Word/TextEdit emit smart quotes and dashes as
   `\'93 \'94 \'96 \'85` under `\ansicpg1252`; `chr(0x93)` is an invisible C1
   control character, not `“`.
   Repro: `parse_rtf(r"{\rtf1\ansi\pard\plain he said \'93hi\'94\par}")` →
   `'he said \x93hi\x94\n'`. Fix: `bytes([code]).decode('cp1252')`.

2. **`\uN` fallback character not skipped when written as hex escape**
   (`rtf_parser.py:191-193`). Only a literal `?` is skipped, but Word emits
   the fallback as `\'3f`; `\ucN` is ignored entirely.
   Repro: `\u955\'3f` → `'λ?'` — every non-ASCII char pasted from Word gains
   a spurious `?`.

3. **Header-skip heuristic mangles a paragraph starting with an escaped
   character** (`rtf_parser.py:46-63`). The post-`\pard` skip loop treats any
   `\` as a control word and swallows the escape prefix.
   Repro: `\pard\f0\fs24 \'e9tude\par` → `"'e9tude"` instead of `étude`;
   `\u233?tude` → `'?tude'`.

4. **RTF without `\pard` leaks header text into the paste**
   (`rtf_parser.py:39-46`). If no `\pard`/`\pardeftab` is found, parsing
   starts at position 0 and font-table content is emitted.
   Repro: `{\rtf1\ansi{\fonttbl{\f0\fswiss Arial;}}Hello world}` →
   `'Arial;Hello world'`.

5. **`\tab`, `\line`, `\emdash`, `\lquote`, … silently dropped**
   (`rtf_parser.py:196-211`). `parse_rtf(r"...a\tab b\par...")` → `'ab'` —
   words fuse together.

Consider replacing the hand-rolled skip heuristics with a proper tokenizer
(control word + optional numeric parameter + optional delimiter), which would
fix BUG-4 and items 3-5 in one structure.

---

## BUG-15: Bold/underline runs shift after an em-dash (screen, print, and PDF)

**Severity:** Medium
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/print_formatter.py:102-131`, `pagemark/view.py:391, 611-617`

`render_paragraph` displays `—` as `--` (2 columns for 1 character), but both
the view's style slicing and the print formatter's column→style-index mapping
assume 1 display column per character. Every style run to the right of an
em-dash on the same line is shifted one column left per preceding em-dash.

Repro: paragraph `"a—bold"` with styles `[0,0,1,1,1,1]` produces the print
run `(12, '-bol', 1)` against display text `'a--bold'` — the second hyphen
prints bold and the final `d` prints plain.

**Fix:** expand the style array in step with the text expansion (duplicate
the em-dash's style flag for the second hyphen) in both `view.render()` and
`PrintFormatter`.

---

## BUG-16: Ctrl-B / Ctrl-U style toggle doesn't re-render — styling appears only after the next keystroke

**Severity:** Medium
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/commands.py:496-523` (`ToggleStyleCommand`), `pagemark/commands.py:115-131` (`EditCommand.execute`)

The toggle mutates `model.styles` in place, but nothing calls
`view.render()`; `Editor._draw` paints from `view.line_styles`, which is a
copy sliced at the previous render (`view.py:614`). Selecting a word and
pressing Ctrl-B leaves the screen unchanged until some later action triggers
a render.

**Fix:** call `editor.view.render()` after `_edit()` in
`ToggleStyleCommand._edit` (or generally in `EditCommand.execute`, since all
edits should refresh the frame).

---

## BUG-17: Autosave backstop can never fire — continuous typing disables autosave entirely

**Severity:** Medium
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/editor.py:84-113`, main loop at `editor.py:194-203`

`_maybe_autosave()` runs only when `select()` times out, and
`_calculate_autosave_timeout()` returns the debounce remainder (up to 10 s
after the last edit) without capping it by the 5-minute backstop. A user who
types steadily never lets the debounce expire, so `select()` always returns
input first and no swap file is ever written — exactly the session most at
risk in a crash.

**Fix:** return `min(debounce_remaining, backstop_remaining)` (treating
"never autosaved" as backstop due), or check `_maybe_autosave()` on every
loop iteration rather than only on timeout.

---

## BUG-18: Pasted/buffered keystrokes stall inside curtsies — input arrives in delayed bursts

**Severity:** Medium
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/terminal.py:298-309` (`get_key`), `pagemark/editor.py:199`

`get_key` gates `next(self._curtsies_input)` behind `select()` on stdin, but
curtsies buffers internally: one OS `read()` can consume many keystrokes and
queue them as events. After the first event is returned, the kernel buffer is
empty, so both this `select` and the editor main loop's `select` block while
decoded events sit in curtsies' queue.

**Scenario:** paste several characters into the terminal → only the first
appears; the rest arrive in a burst after the next keypress or timeout.

**Fix:** drain curtsies' queued events before falling back to `select` (e.g.
call `next(self._curtsies_input)` with a 0 timeout until exhausted, or track
whether the last read left queued events).

---

## BUG-19: No-op edits mark the document modified and pollute the undo stack

**Severity:** Low/Medium
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/commands.py:115-131` (`EditCommand.execute` always returns True)

Ctrl-X with no selection, a filtered control character, a failed Alt-M
center, transpose in a one-character paragraph, Ctrl-B with no selection —
all set `modified = True` and push an `UndoEntry` whose before/after are
identical.

**Scenario:** open a file, press Ctrl-X (no selection), Ctrl-Q → spurious
"Save file? (y, n)" prompt; Ctrl-Z reports "Undone" with no visible change.

**Fix:** have `EditCommand.execute` compare the before/after snapshots (they
are already both taken) and skip the undo push + modified flag when equal.

---

## BUG-20: M-t (transpose words) leaves the cursor mid-word

**Severity:** Low
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/model.py:474-475`

```python
self.cursor_position.character_index = word2.start() + len(word1.group())
```

The transposed region ends at `word2.end()` (total length is preserved), not
`word2.start() + len(word1)`. With `"cat elephant"` → `"elephant cat"`, the
cursor lands at index 7 (inside "elephant") instead of 12 (after "cat"), so
repeated M-t doesn't walk forward Emacs-style.

**Fix:** set `character_index = word2.end()`.

---

## BUG-21: Copying styled text containing characters above U+7FFF generates invalid RTF

**Severity:** Low
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/clipboard.py:204` (`_escape_rtf`)

RTF `\uN` takes a signed 16-bit value: codepoints above 32767 must be written
as negatives and codepoints above U+FFFF as surrogate pairs. Copying an emoji
(e.g. U+1F600, codepoint 128512) emits a `\uN` control word with N = 128512,
which receiving applications reject or misdecode (typically modulo 65536,
yielding the wrong character). The parser side
already handles negatives (`rtf_parser.py:182-183`); the generator side
doesn't produce them.

**Fix:** emit surrogate pairs for astral codepoints and two's-complement
negatives for 0x8000-0xFFFF.

---

## BUG-22: Cursor drawn one row too low when the view top sits exactly on a page boundary

**Severity:** Medium (found while fuzz-testing the BUG-8/9 fixes)
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/view.py` (`_set_visual_cursor_position`)

`_set_visual_cursor_position` counted a page break for every line number in
`[doc_line_start, cursor_doc_line)` that is a multiple of lines-per-page. The
break preceding the view's own top line is above the view and never rendered,
so when `doc_line_start % lines_per_page == 0` the computed cursor row was one
below the row where the cursor's line was actually drawn — making Up land on
the cursor's own line (stall) and drawing the cursor on the wrong row.
Fixed by starting the count at `doc_line_start + 1`.

---

## BUG-23: Page-break rows not accounted for in render's end-of-view position

**Severity:** Medium (found while fuzz-testing the BUG-8/9 fixes)
**Status:** Fixed (2026-07-09)
**Files:** `pagemark/view.py` (`render`)

When a page-break row consumed view space inside the first rendered
paragraph, `render()` still computed `end_position` from `lines_wanted` as if
all those content lines had been rendered. A cursor on the content line that
the page break displaced was wrongly treated as in-view, clamped to the
bottom row, and the next Down press was a no-op. Fixed by tracking the number
of content lines actually added.

---

# Improvements

## ENH-1: Every keypress does O(document) re-wrapping work

**Files:** `pagemark/view.py:490-501, 695-736, 960-964`

`_get_document_line_number`, `_set_visual_cursor_position`,
`_cursor_doc_line`, and `_total_document_lines` all loop over *every*
paragraph and re-run `render_paragraph` (word wrap) on each, on every render
and every cursor movement. On a large document each keystroke re-wraps the
whole document several times; this fuzzing session measured multi-second
sweeps on a ~40-paragraph document. Cache per-paragraph visual line counts
(and mappers) keyed on `(paragraph_text, num_columns)` and invalidate on
edit; wrap results are already deterministic.

## ENH-2: Undo snapshots copy the entire document on every keystroke

**Files:** `pagemark/editor.py:294-312`, `pagemark/commands.py:115-131`, `pagemark/undo.py`

Each `EditCommand` stores two full copies of all paragraphs *and* style
masks (before + after), with a 500-entry cap — up to ~1000 full document
copies held in memory, and one full copy built per keystroke. Consider
coalescing consecutive single-character insertions into one entry (Emacs
style) and/or storing per-paragraph deltas.

## ENH-3: Incremental search: no wrap-around, no reverse search, duplicated branch

**Files:** `pagemark/editor.py:578-593`

`_isearch_find_next` has two identical branches (the `from_current`
parameter is dead). Search stops at the end of the document instead of
wrapping, and there is no reverse search (Ctrl-R). Consider wrap-around with
an "Overwrapped" indicator.

## ENH-4: Quitting with "n" (discard changes) leaves the swap file behind

**Files:** `pagemark/commands.py:208-216`, `pagemark/editor.py:843-861`

`QuitCommand` deletes the swap file only on the clean-exit path. Answering
"n" to "Save file?" leaves `.<name>.swp` on disk, so the next open offers to
"recover" content the user explicitly discarded. (The repo root's
`.foo.txt.swp` is likely an instance.) Delete the swap on the explicit-
discard path too.

## ENH-5: Selection normalization is copy-pasted in four places

**Files:** `pagemark/model.py:939-1049`, `pagemark/commands.py:508-523`

`get_selected_text`, `_get_selected_styles`, `delete_selection`, and
`_toggle_selection_style` each re-implement "swap start/end if reversed"
with the same tuple comparisons. `CursorPosition` already defines `__lt__`;
add a `model._normalized_selection() -> tuple[CursorPosition, CursorPosition]`
helper and use it everywhere.

## ENH-6: Small robustness/cleanup items

- `pagemark/terminal.py:231-237` — status messages are `ljust`-ed but never
  truncated; a long filename in a prompt can wrap and corrupt the frame.
- `pagemark/view.py:293-393` — the long-word slicing loop appears three
  times inside `render_paragraph`; extract a helper.
- `pagemark/model.py:1003-1049` — `delete_selection` and `paste` don't call
  `_update_caret_style_from_position()`, so the typing style after deleting
  a selection reflects the pre-delete position.
- `pagemark/model.py:574-575` — stray blank lines with trailing whitespace;
  `DocumentModel` (model.py:1119) exists only for tests — consider moving it
  into the test package.
- Add a movement property test: for random documents, widths, and heights,
  repeated Down (Up) presses must visit every visual line exactly once and
  never stall before the last (first) line. The fuzz harness used to find
  BUG-8/9 can be adapted for this.

