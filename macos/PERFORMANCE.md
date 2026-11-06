# Typing performance and module boundaries

The 0.2.7 work follows a report that typing in the Mac preview felt sluggish.
The first measurements separated editing/layout CPU work from native drawing.
They use synthetic text and offscreen bitmaps on this Mac; they do not measure
end-to-end keyboard latency or the signed app's display pipeline.

## Shared and platform-specific costs

| Cost | Terminal Pagemark | Mac app | Status |
| --- | --- | --- | --- |
| Whole-document layout rebuild through a 256-entry paragraph LRU | Yes | Yes | Fixed in shared `DocumentLayout.build`, with both views supplying their previous layout |
| Formatting-array conversion during model edits | Yes | Yes, same model | Remains; belongs in the shared document-state contract |
| Full-document undo snapshots | Yes, terminal undo stack | Yes, NSUndoManager captures GUI snapshots | Remains; shared immutable document data should underpin both adapters |
| Synchronous recovery serialization and fsync | Yes, ten-second debounce/five-minute backstop | Yes, a 0.75-second timer during editing | Remains; requires ordered background writes and Save/Discard barriers |
| One native draw call per character or display cluster | No Cocoa drawing | Yes | Batched and cached in the Mac painter |
| Whole-document Cocoa grapheme scans and UTF-16 maps during navigation/input queries | No Cocoa mapping | Yes | Replaced with paragraph-local indices |

The terminal source also owns normal file saves and swap-file policy. The Mac
app owns sandbox-authorized NSDocument saves and private recovery. Those
platform responsibilities should not move into the pure layout module.

## Implemented boundaries

- **Shared `pagemark.layout`** remains the sole authority for wrapping, cell
  widths, paragraph source mappings and line positions. Its optional previous
  immutable layout retains unchanged paragraph layouts independently of the
  global LRU. Width changes rebuild the affected layouts. Terminal `view.py`
  and Mac `session.py` call that same API.
- **`rendering.py`** converts an existing layout row into pure text runs. It
  respects source styles, synthetic indentation, displayed em dashes and
  selection boundaries; it never wraps text or mutates the editing model.
- **`native_painter.py`** owns a bounded cache of Cocoa strings, fonts and
  attributes. ASCII runs batch when their grid matches the selected font's advance;
  Unicode clusters and other grid widths retain explicit cell positions.
- **`text_index.py`** owns source/UTF-16 prefix offsets and lazy paragraph
  grapheme indices. It reuses unchanged paragraph records and accepts a
  platform segmentation function without importing Cocoa. Selection and text
  mutation stay in the editing session. The status bar and its per-refresh
  document callback were removed in 0.2.11.

The shared layout-reuse change is committed in the unified repository.
Both front ends now import the same `pagemark_core` implementation directly.
The earlier cross-repository patch is retained in Git history; no manual patch
application or separate source checkout is required.

## Measurements

Medians from warmed offscreen/CPU samples using the same synthetic fixtures:

| Operation | 0.2.6 | New implementation |
| --- | ---: | ---: |
| Continuous viewport repaint, 840 × 692 | 205.4 ms | 8.4 ms |
| Pages viewport repaint, same size | 191.1 ms | 8.3 ms |
| Insert + layout, 260 paragraphs / about 75,000 characters | 117.3 ms | 19.4 ms |
| Insert + layout, 500 paragraphs / about 144,000 characters | 223.6 ms | 39.6 ms |
| Paragraph layout computations per edit at 260 paragraphs | 261 | 1 |

A separate 500-paragraph Unicode fixture (about 128,000 characters) takes
0.14 ms for a warmed left/right navigation pair, with 2.24 ms for the first
pair. Only the current paragraph is segmented. Calling the old whole-string
segmentation helper directly still costs time proportional to the entire
string; the editor no longer uses it that way.

A repeat with `tools/profile_editor.py` measured 8–12 ms drawing and 19–31 ms
for the 260-paragraph edit/layout case across the two runs. Timings vary with
system load; the consistent regression guard is one paragraph computation per
local edit. The repeat report is in `.build/editor-performance.json`.

The remaining edit time is largely full-document snapshot/validation work.
Full viewport invalidation remains conservative; batching already reduces its
cost substantially. Precise dirty-region updates can follow an explicit edit
change record rather than inferring mutations in the painter.

Repeat the current measurements after building:

```sh
PYTHONPATH=src:.. \
  ../.venv/bin/python -B tools/profile_editor.py \
  --output .build/editor-performance.json
```

## Regression coverage and next changes

The shared-layout tests cover more paragraphs than the global LRU can hold,
eviction between edits, split/join/reordering operations, width changes and
equivalence to fresh canonical layouts. The terminal integration test fails
against the old view and passes with reuse. In the copied terminal checkout,
647 tests pass; ten pre-existing clipboard/settings tests are unavailable in
this execution sandbox (nine clipboard failures and one settings-write error
were observed before the patch).

Mac tests check run source mappings, styles, selections, grapheme/UTF-16
boundaries, index reuse after edits/undo, and native pixels against the old
painter at several zooms and grid widths. Integer-grid drawing matches pixel
for pixel. Fractional-grid underlines allow narrowly bounded antialiasing
differences at cell joins. Existing composition, undo, codec and document
tests remain in the suite. Tests assert correctness and retained work rather
than unreliable wall-clock thresholds.

The next shared-state change should make immutable paragraph data the model's
authority and represent edits explicitly. Both undo adapters can then retain
unchanged paragraphs instead of deep-copying styles. Treat dirty-state/save
baselines, composition cancellation and cross-paragraph edits as acceptance
contracts for that change. Recovery threading is a separate module change:
serialize write/delete operations, coalesce pending snapshots, and prove a
stale write cannot recreate recovery data after Save or Discard. Neither
change should be hidden inside view refresh or drawing code.
