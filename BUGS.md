# Bugs

BUG-4 (RTF control-word prefix matching) was fixed on 2026-07-09 by the
tokenizer rewrite of `rtf_parser.py`; see TICKETS.md BUG-14.


## BUG-5: Undo always marks document as modified

**Status:** Fixed (2026-11-03). The editor tracks the last saved document
content and styles and compares them after edits and undo/redo.

**Severity:** Low
**Files:** `pagemark/editor.py:334`

`_apply_snapshot()` unconditionally sets `self.modified = True`. After undoing all changes back to the saved state, the document is still marked as modified. This causes a spurious "Save file?" prompt when quitting, even though the document matches the file on disk.

**Fix:** Track the saved state (e.g., snapshot at save time or undo stack depth) and compare against it when applying snapshots, or mark `modified = False` when the snapshot matches the last saved state.

---

## BUG-6: Word wrap is one character too aggressive

**Status:** Fixed (2026-11-03). Exactly fitting words stay on the line; an
empty continuation preserves the established full-width cursor behavior.

**Severity:** Low
**Files:** `pagemark/view.py:361`

In `render_paragraph`, the word-fit check uses strict less-than:
```python
if visual_width(current_line) + 1 + visual_width(word) < width:
```

A word whose characters plus the separator space exactly fill the line (`== width`) will wrap to the next line unnecessarily. This means lines can be one character shorter than the available width.

**Fix:** Change `<` to `<=`:
```python
if visual_width(current_line) + 1 + visual_width(word) <= width:
```

---

## BUG-7: Dead SIGINT handler and unused `_ctrl_c_pressed` flag

**Severity:** Low (dead code)
**Files:** `pagemark/editor.py:76-82, 147`

`_handle_sigint` is defined and sets `self._ctrl_c_pressed`, but:
1. It is never installed as a signal handler — line 147 only **reads** the existing handler (`signal.getsignal`), it doesn't call `signal.signal` to install `_handle_sigint`
2. `_ctrl_c_pressed` is never initialized in `__init__` and never read anywhere

**Fix:** Remove the dead handler method and flag, or install it if Ctrl-C-as-copy behavior is desired.

---
