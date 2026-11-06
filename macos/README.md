# Pagemark for macOS

A sandboxed Mac front end for [terminal Pagemark](../README.md). Product scope
and implementation milestones are in [PLAN.md](PLAN.md).

## Current build: editor preview 0.2.12

The Mac app now lives alongside the terminal app. Both import `pagemark_core`
directly; OS access lives in `pagemark_platform`. See the repository
[architecture](../ARCHITECTURE.md) for package boundaries and test commands.

The editor fills the window without a status bar. **Command-F** opens a
temporary Find row, with “No matches” beside the search field when needed;
**Escape** closes it and restores the full editing area. Filenames and save
state use the native document window and file dialogs. Recovery failures use
the native error dialog, suppressing repeats until recovery succeeds again.

**View > Fit Width** adjusts zoom to fit the existing window: the page area
in Continuous/Pages, or the writing column in Draft. **View > Resize Window
to Fit** adjusts window width at the current zoom, preserving height and
staying within the screen's usable width. It is unavailable in full screen.
Both commands act when selected; ordinary pinch/keyboard zoom keeps the
window size unchanged.

Pinch or use **Command-+ / Command-−** to zoom in any editor view;
**Command-0** resets to 100%. Command-= also zooms in. The View menu offers
Zoom In, Zoom Out and Actual Size.
Zoom is remembered separately for Draft and Continuous/Pages. It replaces the
Draft font-size preference; existing saved sizes migrate to equivalent zoom.
The font-family choice remains in Preferences. Printing keeps its physical size.

**View > Draft** adds a continuous writing view with a configurable monospaced
screen font. Choose its font family in **Pagemark > Preferences…** (Command-,).
The default is JetBrains Mono NL when installed, with Menlo as a fallback.
The View menu now also offers **Light Mode**, **Dark Mode**, **System Default**,
and **Enter Full Screen** (Control-Command-F), grouped with separators.
The view mode, Draft font, and appearance choice are remembered between launches.

**File > Print Booklet…** generates booklet output for that print job through
the native print dialog. Ordinary Print and Export PDF produce reading-order
pages. The previous Format > Booklet Output toggle has been removed.

Version 0.2.7 improves typing and navigation with batched native text drawing,
paragraph-local Unicode indices, and shared layout reuse in both front ends.
Offscreen viewport drawing dropped from about 200 ms to 8 ms in the measured
fixture. Module boundaries, measurements and remaining work are documented in
[PERFORMANCE.md](PERFORMANCE.md). Both signed-app probe phases passed in 0.2.8;
the user has not yet reported the live typing comparison.

**View > Continuous**, **Pages**, and **Draft** are editable and use the
terminal app's shared layout and editing model. Command-S/Q/F/P/X/C/V/B/U/Z/Y
provide Save, Quit, Find, Print, Cut, Copy, Paste, Bold, Underline, Undo and Redo.
Their Control aliases also work in the editor. Command-arrow navigation and
the remaining Emacs commands are retained; Edit > Transform offers word casing.
Mouse selection, trackpad scrolling, native text composition, styled clipboard,
search, explicit Save/Save As, Open Recent and private crash recovery are wired
up. **Help > Pagemark Controls** lists the bindings.

Continuous, Pages and output currently use Courier, with single/double spacing,
shared PDF export, booklet imposition and the native print panel. Choose
**File > Print Booklet…** for booklet printing, or use that dialog's PDF menu
to save the booklet as a PDF. Choose short-edge duplex when printing a booklet. The shared
Courier generator reports unsupported characters before output.

**This is an editor preview.** Basic typing, scrolling and drag-selection have
been confirmed on this Mac. Further interaction and document-workflow checks
are in [EDITOR_CHECK.md](EDITOR_CHECK.md). Prestige Elite font import,
print-panel accessories, explicit external-change handling, VoiceOver
validation, large-document performance and distribution signing remain open.
Both front ends now live in this repository and share the layout improvement.

## Build on this Mac

The build uses the existing Pagemark Python 3.12 environment. It does not
install packages, modify that checkout, or use the network:

```sh
../.venv/bin/python -B tools/build_app.py
../.venv/bin/python -B tools/audit_bundle.py
open dist/Pagemark.app
```

The builder copies the runtime, an explicit set of versioned dependencies,
and the shared core/platform packages into the app. Its generated manifest records the
repository revision, dirty-state flag, and exact shared-package source hashes. All non-system dynamic libraries are relocated
inside the bundle. The native launcher links AppKit and initializes the Cocoa
application before starting Python. It uses isolated Python configuration with
environment/user-site imports and bytecode writes disabled. The installed
source environment is needed to build, not to run the resulting app. The repository includes the shared layout-reuse API described in [PERFORMANCE.md](PERFORMANCE.md).

Version 0.2.2 fixes the shutdown crash introduced in 0.2.1 by releasing bridged
Cocoa objects before the interpreter is destroyed. The native host's cleanup
is covered by a compiled regression test. Both phases of the signed-app check
passed on the user's Mac on 2026-11-05, confirming startup and clean probe exits.

Version 0.2.5 corrects the bundled Cocoa bridge's document-open callback
signature, which prevented the Recent/Finder open-event handler from calling
the native API. Real Cocoa regression tests reproduce and verify the fix.
The user confirmed that callback check passes in the signed 0.2.5 app. Version
0.2.6 fixes a false failure in the Recent-menu diagnostic: AppKit's Clear Menu
item uses responder-chain routing, so the probe now resolves its native handler
instead of requiring an explicit target. Both phases of the signed 0.2.6 check
passed on the user's Mac, including the native Recent-menu and callback checks.
The user then confirmed File > Open Recent opens the listed file correctly,
before using File > Open in that preview. The bridge correction, probe
regression and private menu-registration hook are documented in
[BUILD_STATUS.md](BUILD_STATUS.md).

`py2app` was unavailable and package downloads were blocked in the build
environment, so this prototype uses an explicit local bundler. Reevaluate
the packaging tool after the sandbox gate; a second runtime is not required.

Local builds use ad-hoc signing with App Sandbox enabled. They **do not enable
hardened runtime and are not notarized**: no Developer ID identity was available.
For release, `--identity 'Developer ID Application: …'` enables hardened runtime
and timestamped signing without a library-validation exception. A release
also needs notarization and a fresh runtime test; those are not yet complete.

## Verify the signed app's sandbox

Do this from a normal Terminal session on the Mac, outside another process
sandbox. The agent's execution environment aborts even a minimal signed
sandbox control before `main`, and cannot reach LaunchServices. Live GUI
interaction cannot be verified there. Version 0.2.8 passed both phases on the
user's Mac on 2026-11-05: isolated Python, Cocoa/PDF/native print setup, private
storage, denied loopback connect/listen and unselected-file read, and a hidden
native editor window exercising Command/Control events, undo/redo and view
switching through all three views, plus native Recent-menu routing, the
document-open callback and the new Preferences controls/appearance checks.
Reports are retained in `.build/check.xzz5Dg`.
The user also confirmed basic typing, scrolling and drag-selection in 0.2.2.
Extended interaction and permission lifetime remain to be checked.

Double-click `tools/check_sandbox.command`, or run it from Terminal. It creates
a fresh dummy fixture and runs two phases: bundled runtime/sandbox checks,
then native editor checks in a hidden window. Both must pass before it opens
the app. The editor checks native Recent-menu registration, the document-open
callback, Command/Control events, formatting, undo/redo, switching views, and
native Preferences controls and appearance handling. The probe also checks
zoom shortcuts, synthetic pinch input and native scroll anchors, plus both
fit actions in a real hidden window, plus Find feedback and restoration of the
full editing area after closing Find. The 0.2.12 signed probe run and physical
trackpad interaction are pending.
Each run retains its reports
in `.build/check.*`; the latest
reports are also copied to `.build/runtime-probe.{json,stderr}` and
`.build/editor-probe.{json,stderr}`. On failure it collects the relevant macOS
log in `.build/launch-diagnostics.log`. Quit the
earlier preview before running it, so opening the app starts the new version.
It does not submit a print job.

Create a disposable file, then execute the probe:

```sh
mkdir -p .build/fixtures
printf '%s\n' 'pagemark-disposable-sandbox-fixture' > .build/fixtures/unselected.txt
dist/Pagemark.app/Contents/MacOS/Pagemark --probe-runtime \
  --denied-file "$PWD/.build/fixtures/unselected.txt"
dist/Pagemark.app/Contents/MacOS/Pagemark --probe-editor
```

The JSON report should show isolated Python, working Cocoa/PDF integration,
and `denied: true` for loopback connect/listen and the unselected fixture.
A connection-refused error is **not** treated as a sandbox denial. The probe
uses no external host and inspects only the explicitly supplied dummy file.
Static entitlements and a denied direct socket do not prove absence of all
OS-mediated data-leakage routes; see the threat model in the plan.

Then launch the app normally and use **Open** to select a disposable `.txt`
file. Verify Save As, reopening the copy, Export PDF, and the Print preview.
Cancel Print to test the dialog without submitting a physical job. Repeat with
an unselected sibling file in the probe to check file-grant scope.

Never remove the app's sandbox entitlement to get this test to pass. Recent
authorization lifetime, selected-file scope, and native dialogs still need
verification on the Mac.

## Tests

From `macos/`, without building first:

```sh
../.venv/bin/python -B -m pytest -q
../.venv/bin/ruff check src tools tests
```

Codec tests compare the GUI reader against the terminal implementation,
exercise Unicode/style round trips, and verify exact unchanged-file saves.
Unrepresentable edits (notably the legacy bold-underscore ambiguity) return an
error and retain edits instead of silently changing their styling.

