# Source-code bug audit

Audited on 2026-11-03 at commit `10c4fff1698d2d5046b3cc7c9bbaa1dfd678f82f`
using Python 3.12.2 on macOS. No application code was changed.

**Results: eight confirmed new bugs, two reproduced existing bugs, and one behavioral question (BUG-27).**
New IDs continue after BUG-21 in [TICKETS.md](TICKETS.md). This review focused
on editing, selection, Unicode, wrapping, serialization, saving, autosave,
settings, and the shared screen/print rendering path. It is not an exhaustive
audit of every platform or printer.

## Reproducing the findings

The executable reproductions are in
[tests/repro_source_audit.py](tests/repro_source_audit.py):

```sh
.venv/bin/python -m pytest tests/repro_source_audit.py -q --tb=short
```

**Observed result: 18 failed in 2.63 seconds.** Each test asserts the intended
behavior, so failure demonstrates the bug. Parameterized cases cover multiple
triggers for the same bug. For one finding, append `-k bug22`, replacing the ID
as needed. The two existing findings use `-k existing_bug5` and
`-k existing_bug6`.

The reproduction file deliberately does not match default pytest discovery;
it must be selected explicitly. It uses real editor/model/view code with a
stub terminal, temporary document/settings files, and controlled clipboard
results. It closes editor pipes and bounds the renderer hangs in subprocesses
that are killed and reaped on timeout. It does not access the system clipboard
or submit print jobs.

| ID | Severity | Confirmed behavior |
| --- | --- | --- |
| BUG-22 | High | Deeply indented bullets make rendering loop indefinitely. |
| BUG-23 | High | Saving through a symlink replaces the link and leaves its target unchanged. |
| BUG-24 | Medium | Saving an existing file silently resets its permissions to `0600`. |
| BUG-25 | Medium | Unicode case expansion corrupts style alignment and cursor placement. |
| BUG-26 | Medium | Unicode case-insensitive search returns offsets in the transformed string. |
| BUG-27 | Unconfirmed | Pasting empty or fully filtered clipboard text deletes the selection. |
| BUG-28 | Medium | Enter, Backspace, and Ctrl-D ignore the selected range and leave stale selection state. |
| BUG-29 | Medium | Settings do not persist for a document first named through Save. |
| BUG-30 | Medium | Wide and combining characters put the cursor in the wrong terminal column. |

## BUG-22: Deeply indented bullets hang the renderer

**Status:** Fixed; continuation indentation reserves space for content and
long-word splitting always consumes a character. Regression tests are in
`tests/test_audit_fixes.py`.

**Source:** [pagemark/view.py](pagemark/view.py), `render_paragraph`, especially
`slice_to_visual_width` (line 267), `available_width_for_line` (line 291), and
the long-word loops (lines 313, 345, 381).

**Reproduce:** At the default width of 65, render either:

```python
render_paragraph(' ' * 63 + '- x', 65)
render_paragraph(' ' * 62 + '- —', 65)
```

These are also reachable by opening a text file containing such a paragraph
or typing/pasting the paragraph in the editor. The second case has a positive
remaining width but an em dash needs two display columns.

**Expected:** Rendering terminates, with a sensible fallback when the hanging
indent leaves insufficient room for content.

**Actual:** Both subprocesses reached the renderer and exceeded the one-second
deadline. In the first case, continuation width is zero. In the second it is
one, so no part of the two-column em dash fits. `slice_to_visual_width` returns
`''`; removing that slice leaves `word` unchanged, and the loop keeps appending
lines. Source inspection establishes that the loop cannot make progress.

**Impact:** Opening or editing an ordinary text file can freeze the editor and
grow memory indefinitely. Printing uses this same wrapping function.

**Fix direction:** Guarantee that every wrapping iteration consumes input;
handle unusable hanging widths and characters wider than the remaining width
explicitly. Merely clamping width to one does not fix the em-dash case.

## BUG-23: Saving a symlink replaces it instead of updating the opened file

**Status:** Fixed; atomic saves resolve the destination while preserving the
user-facing path and symlink.

**Source:** [pagemark/editor.py](pagemark/editor.py), `load_file` (line 688) and
`save_file` (lines 747–762).

**Reproduce:** Create `original.txt` containing `old` and `link.txt` pointing to
it. Open `link.txt`, insert `new ` at the beginning, and save.

**Expected:** `link.txt` remains a symlink and `original.txt` contains `new old`.

**Actual:** Save returns `True`, `link.txt` becomes a regular file containing
the edit, and `original.txt` still contains `old`. The reproduction observed
`(link.is_symlink(), target_text) == (False, 'old')`.

**Cause:** Loading follows the symlink, but `os.replace(temp_filename,
filename)` replaces the symlink directory entry. The read and write refer to
different filesystem objects.

**Impact:** The apparent successful save does not update the intended document
and destroys the link relationship.

**Fix direction:** Define symlink handling explicitly and perform the atomic
save against the resolved destination when editing through a link.

## BUG-24: Atomic save resets existing file permissions

**Status:** Fixed; the existing destination mode is applied to the temporary
file before replacement. New files retain restrictive permissions.

**Source:** [pagemark/editor.py](pagemark/editor.py), `save_file` (lines 750–760).

**Reproduce:** Create an existing document with mode `0640`, open it, edit it,
and save.

**Expected:** The existing `0640` mode is preserved.

**Actual:** Save succeeds but the file mode becomes `0600` (decimal `384`,
versus expected `416`).

**Cause:** The replacement inode inherits `NamedTemporaryFile`'s restrictive
permissions. No existing metadata is copied before replacement.

**Impact:** Other users or processes that previously had group read access
lose access after a routine save. Executable bits would likewise be lost.

**Coverage gap:** `test_atomic_save_preserves_permissions` in
[tests/test_atomic_saving.py](tests/test_atomic_saving.py) reads the old and new
stat values but never asserts that their modes match; it only checks content.

**Fix direction:** Preserve appropriate metadata for an existing destination
before replacing it, while retaining a deliberate permissions policy for new
files. Keep this distinct from the symlink destination bug.

## BUG-25: Unicode case conversion misaligns formatting and the cursor

**Status:** Fixed; case conversion remaps style spans and cursor positions
while retaining whole-word contextual casing.

**Source:** [pagemark/model.py](pagemark/model.py), `downcase_word` (line 700),
`upcase_word` (line 736), and `capitalize_word` (line 772).

**Reproduce:** Use `ß X` with styles `[1, 0, 2]` (bold `ß`, plain space,
underlined `X`), put the cursor at the beginning, and press Alt-U or Alt-C.
Also reproduced with `İ X` and Alt-L.

**Expected:** `SS X` or `i\u0307 X`, styles `[1, 1, 0, 2]`, and cursor index 2
after the converted word.

**Actual:** Text expands correctly, but styles stay `[1, 0, 2]` and the cursor
stays at index 1. The second converted codepoint loses bold, the space gains
underline, and the original `X` loses its underline when serialized/displayed.

**Cause:** The methods replace text using Unicode case conversion but retain
the old style array and pre-conversion word-end index. Unicode case conversion
can change string length.

**Fix direction:** Transform text and associated style spans together and
compute the cursor position from the replacement length. Test all three case
commands with expanding conversions.

## BUG-26: Unicode search positions the cursor after the match

**Status:** Fixed; search maps both the starting offset and match back to
original document coordinates.

**Source:** [pagemark/editor.py](pagemark/editor.py), `_find_forward`
(lines 644–661).

**Reproduce:** Type `İx`, move to the beginning, press Ctrl-F, then type `x`.

**Expected:** Cursor index 1, at the original `x`.

**Actual:** Cursor index 2, after `x`.

**Cause:** `'İx'.lower()` is `'i\u0307x'`. Searching it returns index 2, which
the editor applies directly to the original two-character paragraph. The
search start offset is also passed into the transformed string without a
mapping.

**Impact:** Search jumps to the wrong character; subsequent editing can affect
the wrong location. More expanding characters before a match increase the
offset error.

**Fix direction:** Map transformed search offsets back to original character
boundaries, including the starting position and repeated-search path.

## BUG-27: Empty clipboard paste deletes selected text (behavioral question)

**Disposition:** Excluded from fixes at the user’s request. Empty replacement
may be intentional; the original assertion encoded an unestablished UX
expectation. This is not counted as a confirmed defect.

**Source:** [pagemark/model.py](pagemark/model.py), `paste` (lines 1078–1093).

**Reproduce:** Select `keep me` and press Ctrl-V while the clipboard returns
`('', None)`. Repeat with `('\x00', None)`, which becomes empty after
sanitization. The reproduction substitutes only the clipboard read.

**Expected:** Nothing is inserted or deleted when there is no insertable
clipboard content.

**Actual:** The document becomes empty. The operation is recorded as an edit.

**Cause:** `delete_selection()` runs before reading and sanitizing clipboard
content; `if text:` only guards the subsequent insertion.

**Impact:** An empty clipboard or clipboard without usable text unexpectedly
deletes the selection. The demonstrated successful command can be undone.

**Fix direction:** Obtain and validate clipboard content before mutating the
document, then replace the selection only when there is content to insert.

## BUG-28: Several edit commands ignore the selection

**Status:** Fixed; Enter replaces a selected range, deletion removes it, and
empty selections fall back to normal cursor-based editing.

**Source:** [pagemark/commands.py](pagemark/commands.py), `BackspaceCommand`
(line 145), `DeleteCharCommand` (line 150), and `InsertNewlineCommand`
(line 170).

**Reproduce:** Type `abc`, select all three characters with the cursor at the
end, then independently try each command:

| Command | Expected paragraphs | Actual paragraphs |
| --- | --- | --- |
| Enter | `['', '']` | `['abc', '']` |
| Backspace | `['']` | `['ab']` |
| Ctrl-D | `['']` | `['abc']` |

**Cause:** These commands operate solely at the cursor, unlike text insertion,
Tab, and paste, which handle the selected range. They also leave the old
selection endpoints intact after editing.

**Impact:** Selection replacement/deletion behaves inconsistently. For
Backspace, the retained selection end is now beyond the paragraph length;
for Enter, selection still refers to the old paragraph while the cursor has
moved to a new one. Subsequent typing can replace that stale range.

**Fix direction:** Handle active, nonempty selections before these operations
and clear or correctly update selection state afterward. Cover forward and
reverse selections, including ranges across paragraphs.

## BUG-29: First Save never associates the session settings with the new path

**Status:** Fixed; successful saves associate and persist current preferences
without loading defaults over the user’s choices.

**Source:** [pagemark/editor.py](pagemark/editor.py), `save_file` (line 762),
and [pagemark/session.py](pagemark/session.py), `set` (line 48) and
`_save_to_disk` (line 104).

**Reproduce:** Start an unnamed document, type text, use Ctrl-S and enter a
filename. Then change double spacing (represented in the reproduction by
`session.set(SessionKeys.DOUBLE_SPACING, True)`), clear in-memory session
state to simulate restarting, and reopen the saved document.

**Expected:** Double spacing is restored from that document's saved settings.

**Actual:** Double spacing is `False` after reopening. The document text itself
was saved successfully.

**Cause:** `save_file` sets `editor.filename` but never associates the session
with it. `SessionManager._document_path` remains `None`, so subsequent settings
changes are never written. Association currently happens only on loading a
named document or recovered content.

**Impact:** Documents created without a command-line filename lose their
per-document preferences across restarts.

**Fix direction:** Associate the session with the successfully saved path and
persist the current preferences, without overwriting them with defaults.

## BUG-30: Cursor columns count codepoints instead of terminal cells

**Status:** Fixed; wrapping, cursor mapping, selection, and terminal painting
share cell-width measurements and keep combining sequences together. Style
arrays remain indexed by rendered characters, separately from cell positions.

**Source:** [pagemark/view.py](pagemark/view.py), `visual_column` (line 103),
`content_column_from_visual` (line 123), and `render_paragraph.visual_width`
(line 263).

**Reproduce:** Type either of these strings into an empty document:

| Text | Actual cursor column | Expected terminal column |
| --- | --- | --- |
| `界x` | 2 | 3 |
| `e\u0301x` (decomposed accented e, then x) | 3 | 2 |

Columns are zero-based and measured relative to the document margin. The
reproduction checks the editor view against `wcwidth.wcswidth`.

**Cause:** Width calculations count every codepoint as one cell, except for
the explicit em-dash expansion. Input sanitization accepts both wide
characters and combining marks, so these cases are reachable through typing
and paste.

**Impact:** The drawn cursor is displaced from the insertion position.
The shared width assumption also affects wrapping and vertical movement.

**Fix direction:** Use a consistent terminal-cell-width mapping throughout
wrapping and cursor conversion, retaining the deliberate `—` → `--` display
conversion and handling combining sequences coherently.

## Existing findings reproduced

These are already listed in [BUGS.md](BUGS.md), and are not counted among the
nine new findings.

- **BUG-5, Low:** Save `saved`, insert `x`, then undo. Serialized document
  content equals the saved file but `editor.modified` is still `True`.
  `_apply_snapshot` in [pagemark/editor.py](pagemark/editor.py), line 371,
  unconditionally sets it. The extra save-on-quit prompt remains reproducible.
- **BUG-6, Low:** `render_paragraph('a ' + 'b' * 63, 65)` returns two lines,
  `['a', 'b' * 63]`, although the complete text has exactly 65 characters.
  The strict `< width` check in [pagemark/view.py](pagemark/view.py), line 368,
  remains in place. No fix is claimed here; a fix should also retain the
  existing full-width cursor behavior.

BUG-7 concerns dead SIGINT code rather than a newly reproduced user-visible
failure and is not counted here.

## Existing test-suite results and limitations

Before adding the reproduction file, ran:

```sh
.venv/bin/python -m pytest -q
```

Result: **532 passed, 9 failed, 1 error in 23.49 seconds**.

The nine failures all involved the unavailable macOS system pasteboard in
this execution environment (`NSPasteboard.generalPasteboard()` returned
`None`). They occurred in `test_ctrl_c_handling.py` (2),
`test_cut_selection_bug.py` (3), and `test_selection.py` (4). These are not
counted as nine additional product bugs.

The error was setup for
`test_view_width_bugs.py::test_persisted_line_length_applied_on_open`: its
fixture tried writing the real user settings file under
`~/Library/Application Support/pagemark/`, which the sandbox denied. The
audit reproductions instead use isolated settings files in a temporary
directory and ran without setup errors.

No physical printer or interactive system clipboard behavior was validated.
The reported findings above are backed by executed component or editor-command
reproductions, rather than inferred solely from test-suite failures.
