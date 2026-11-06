# Build status — 2026-11-05

## Editor preview 0.2.10 — explicit content and window fitting

`dist/Pagemark.app` targets macOS 12/x86_64 and bundles its Python runtime and
dependencies. Unmodified Pagemark model, clipboard, layout and PDF modules are
copied into an isolated package with source hashes. The user applied the tested
layout-reuse patch to the sibling checkout, so both front ends use the same fix.

The editor uses one shared session, a custom AppKit text-input view, and three
presentations: Continuous, Pages and Draft. All are editable. Native text
input ranges use UTF-16; source offsets remain Python codepoints; Cocoa
composed-character boundaries protect cursor movement/deletion/transposition.
The document's NSUndoManager is the only undo history. It also drives native
dirty-state tracking, as described in Apple's
[document behavior guide](https://developer.apple.com/library/archive/documentation/DataManagement/Conceptual/DocBasedAppProgrammingGuideForOSX/StandardBehaviors/StandardBehaviors.html).

Implemented: mouse selection and autoscroll; standard Command shortcuts,
Control aliases and retained Emacs navigation; formatting; styled clipboard through shared adapters; incremental
search; native Open/Save/Save As and Recent; atomic private recovery copies;
Courier single/double spacing; shared portrait/booklet PDF output and native
printing. Native dialog clipboard/undo equivalents are retained. Recovery
opens a private unsaved copy requiring a user-chosen save destination.

## Verified

- **198 automated Mac tests pass**, covering codec compatibility, shared wrap/page
  layout, page-gap hit testing, grapheme edits, insertion-style/selection
  snapshots, preferred-column movement, native undo and dirty state, UTF-16
  composition and cancellation, accessibility ranges, atomic recovery,
  successful/failed native safe saves, PDF/booklet pagination, and errors.
  The runner also checks that either phase's failure stops the check, preserves
  completed reports, and never opens the app after a failed probe.
  Three native-host regression cases construct and release a real native print
  operation retaining a Python-backed view, covering success, a failed probe's
  exit status, and an exception. They use the production launcher/entry point
  with a minimal development probe, without a window or print job.
  Three document-open cases exercise Objective-C delegate dispatch, Unicode
  filenames, out-of-order completions, missing-file/permission errors, and
  replying to macOS only after all requested opens complete.
  A real NSMenu regression verifies its AppKit role is registered before
  application launch, with Clear Menu targeting the document controller.
  This regression fails against 0.2.3 and passes against 0.2.4.
  Two additional cases call the real Cocoa document-open API and verify all
  three callback arguments for an already-open document and an asynchronous
  error. Both reproduce `BadPrototypeError` without the bridge correction;
  both pass with it. Earlier mocked open-event tests missed this metadata bug.
  Four Recent-menu diagnostic cases use AppKit's own menu template, whose
  Clear Menu item has no explicit target. They verify resolving that action
  accepts both native handlers and rejects an application handler or no
  handler. Only NSApplication's responder-chain lookup is stubbed; the menu,
  registration and native handlers are real AppKit objects. All four reproduce
  the old probe's incorrect behavior and pass with the correction.
  New rendering tests cover batching, Unicode clusters, styles, selection and
  native pixel comparisons at several zooms. Unicode-index tests compare
  cached paragraph indices against whole-string reference mappings, including
  edits, undo and segmentation-provider changes. Tests guard against repeating
  document-wide segmentation during local navigation.
  Native key-event tests cover all eleven requested Command bindings, their
  Control aliases, Shift-Command-Z, native field-editor scope, menu equivalents
  and function-key decoding. They never invoke Quit/Print or touch the clipboard.
  Print-action tests exercise native delegate dispatch and real shared PDF
  output while replacing only the print-operation submission. Canceling a
  booklet job preserves the document, print defaults and subsequent regular
  print/export output. Menu tests cover placement and document validation.
  Display tests cover preference migration, font fallbacks, Draft hit testing
  and accessibility bounds at different sizes, unchanged document/undo/print
  state across view changes, native font pixels and cached light/dark colors.
  Menu validation captures checkmark assignments; actual AppKit checkmarks,
  popup controls and the preferences window require WindowServer. Those checks
  passed in the user's signed 0.2.8 run, retained in `.build/check.xzz5Dg`.
- **647 terminal tests pass** in the workspace copy containing the shared
  patch. Ten pre-existing tests need host clipboard/settings access unavailable
  here; they failed before the patch and were excluded from the post-change run.
- Ruff checks pass.
- The user confirmed normal typing, mouse scrolling and drag-selection in the
  opened 0.2.2 preview on 2026-11-05.
- Offscreen AppKit rendering was inspected for both views, hanging indents,
  em-dash display, selections and styled text. This is not a live window test.
- The bundle audit checks strict/deep signatures, bundled native dependencies
  and symlinks, and shared-source hashes. Signed entitlements remain App
  Sandbox, user-selected read/write, printing and PyObjC's JIT capability.
  No network or broad-folder entitlement was added.

## Fit actions in 0.2.10

View > Fit Width changes the content zoom while preserving the window frame.
It fits the page area in Continuous/Pages and the writing column in Draft,
including the existing presentation padding. It uses the same scale limits,
content anchoring and saved zoom as ordinary zoom. Native font rounding and
autohiding scrollbar changes are reconciled with a bounded adjustment loop.

View > Resize Window to Fit changes the window width at its current zoom.
It accounts for window borders and non-overlay scrollbars, preserves height
and vertical position, and keeps the original left edge when possible.
Width is constrained by the window limits and the current screen's usable
width; it moves horizontally only as needed to remain on that screen.
The action is disabled in full screen. Screen bounds come from Apple's
[visibleFrame API](https://developer.apple.com/documentation/appkit/nsscreen/visibleframe),
which excludes space occupied by the Dock and menu bar.

`geometry.py` exposes the presentation's natural width, `fitting.py` owns pure
fit calculations, and `native_fitting.py` applies them through the existing
zoom path or native window API. No document mutation or undo is involved.
Regression cases cover all three modes, native Draft font metrics, composition,
unchanged printing, negative screen origins, minimum/maximum widths, fullscreen
validation and scrollbar changes. The signed probe adds `native_fit_actions`
to check both operations against a real hidden window. Its 0.2.10 run remains
pending; 0.2.8 is the latest user-confirmed signed run.

## Zoom in 0.2.9

Pinch and Command-+/−/0 control screen zoom in all three views. Command-= is
an alias for Zoom In. View-menu actions show the shortcuts, and the status bar
shows the percentage. Scales are bounded to 50–500%; keyboard steps snap to
common percentages and Command-0 selects 100%. Initial scale remains 125%.
Draft remembers its own zoom; Continuous and Pages share a separate scale.
The removed Draft font-size preference migrates to equivalent zoom relative
to a 14-point base font, preserving the old 125% rendering scale. Preferences
now selects only the Draft family. Document layout and physical PDF/print
size do not change when the screen is zoomed.

`zoom.py` owns scale limits, stepping and logical content anchors. The native
view resizes its existing geometry, then adjusts the clip origin to retain
the anchor under the pointer or at the old visible center. It does not reveal
the caret, change the selection or commit marked text. Pinch preference writes
wait until the gesture ends or is cancelled. Gesture handling follows Apple's
[trackpad event guide](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/EventOverview/HandlingTouchEvents/HandlingTouchEvents.html).

Regression checks cover native key variants, migration/relaunch, independent
view scales, limits, content anchors across page boundaries, active composition,
undo and unchanged save bytes/print size. The signed editor probe adds
`native_zoom_controls`: real key events, native clip scrolling and synthetic
pinch deltas in all three views, without writing the user's preferences.
These checks continue in 0.2.10; its run and physical pinch interaction remain pending. The latest
user-confirmed signed run is 0.2.8, retained in `.build/check.xzz5Dg`.

## Display preferences in 0.2.8

The View menu contains Continuous, Pages, Draft; a separator; Light Mode,
Dark Mode, System Default; a separator; and Enter Full Screen. AppKit owns
full-screen transitions through its standard responder-chain action.
Application appearance follows the saved choice; System Default clears the
override so subsequent system changes apply. See Apple's
[application appearance API](https://developer.apple.com/documentation/AppKit/NSApplication/appearance)
and [full-screen action](https://developer.apple.com/documentation/appkit/nswindow/togglefullscreen(_:)).

Draft uses the same source/layout mappings with measured screen-font cells.
Pagemark > Preferences originally offered installed monospaced families and
font sizes; 0.2.9 retains the family choice and uses zoom for reading size.
JetBrains Mono NL is preferred by default; unavailable fonts fall back to
Menlo. Font changes refresh existing Draft windows. Continuous, Pages and
PDF generation retain their print font and geometry. Families without a bold
face receive a synthetic bold stroke in Draft.

`display_preferences.py` owns persistence/validation, `screen_fonts.py` resolves
native fonts/metrics, and `native_preferences.py` owns the native settings UI
and app appearance. The painter and geometry consume those metrics without
changing shared layout or document state. The prior PagesView preference is
read when no new view-mode choice exists. The signed probe confirms native
preferences-window/control creation, saved size selection, app appearance
overrides and appearance-menu checkmarks. Manual font selection, full-screen
transitions and live system appearance changes still need interaction checks.

## Print Booklet in 0.2.8

File > Print Booklet… replaces Format > Booklet Output. The command passes an
explicit booklet choice through the same print helper used by ordinary Print;
the document no longer carries a booklet-mode flag. Ordinary Print and Export
PDF produce reading-order output. Each job copies the document's native print
settings, so canceling the panel cannot leave a later job in booklet mode.
The print dialog's PDF workflow provides booklet PDF output.

The local tests generated a five-page portrait document and a four-side,
landscape booklet (padded to eight reading pages), then verified a later
ordinary print/export remained portrait. No print job was submitted. The live
0.2.8 native dialog still needs checking in the user's Mac session.

## Performance changes in 0.2.7

Shared `DocumentLayout.build` accepts the previous immutable layout and reuses
unchanged paragraphs. Both the terminal view and Mac session supply it. The Mac
view delegates pure run planning to `rendering.py`, native resource caching and
painting to `native_painter.py`, and source/UTF-16/grapheme mapping to
`text_index.py`. These components do not own document mutations or undo.

Measured viewport drawing fell from 191–205 ms to 8.3–8.4 ms. Insert-plus-layout
at 260 paragraphs fell from 117.3 ms to 19.4 ms, with one paragraph layout
computed per edit instead of 261. These are synthetic CPU/offscreen results.
The signed 0.2.7 probe passed in the user's session; a live typing comparison
has not yet been reported.
See [PERFORMANCE.md](PERFORMANCE.md) for reproduction, module boundaries and
the separately scoped shared snapshot/recovery work that remains.

The same build adopts the user's requested Command-S/Q/F/P/X/C/V/B/U/Z/Y
bindings, with Control aliases retained in the editor. Word movement uses
Command-arrows; Capitalize/Uppercase Word are available under Edit > Transform.
The pure `key_bindings.py` policy is separate from Cocoa event and menu code.
Tests also caught an existing function-key decoding mismatch: Cocoa constants
are strings, while the dispatch table indexes character codepoints. That path
now normalizes the constants and covers arrows, Home/End, Page Up/Down and Delete.
The signed editor probe checks Command navigation, Command formatting/search,
Control formatting aliases and undo/redo as separate results.

## User-verified runtime and editor result for 0.2.8

The user ran `tools/check_sandbox.command` in a normal Mac Terminal and
reported both phases passing on 2026-11-05. Both reports identify version
0.2.8, and both probe processes exited successfully. Reports and checkpoints
are retained in `.build/check.xzz5Dg`. Earlier successful runs are retained
in `.build/check.5YFUGf` (0.2.7), `.build/check.CZa5tk` (0.2.6) and
`.build/check.v8IjLf` (0.2.2).

Phase 1 demonstrated isolated bundled Python 3.12, PyObjC 12.1 callbacks,
shared PDF generation, native PDF parsing/print-operation construction,
app-private read/write, and EPERM for loopback connect, listen, and reading
the supplied unselected fixture.

Phase 2 initialized the native application, created a hidden editor window,
and passed Command navigation, the revised Command shortcuts, Control formatting
aliases, native undo/redo and state preservation across Continuous, Pages and
Draft. The native display-preferences check created the hidden Preferences
window and its font controls, applied Light/Dark/System appearances, and
validated appearance-menu checkmarks without writing user preferences.
The native Recent-menu and document-open callback checks also passed.
Clear Menu's declared target was nil and resolved
to `NSDocumentController` in `com.apple.AppKit`, confirming the diagnostic
correction. The disposable document closed normally. These results confirm
the startup, shutdown and callback repairs in the signed app.

The runner then requested a normal preview launch. In 0.2.6 the user confirmed that
File > Open Recent opens the listed file correctly, before using File > Open
in that preview. This confirms the repair in the live app. The user previously
confirmed typing, mouse scrolling and drag-selection in the 0.2.2 preview.
Extended interaction cases, user-selected-file grants, permission lifetime
and physical printing still need checking; the probes do not establish
absence of OS-mediated egress.

## Open Recent repair in 0.2.5 and diagnostic correction in 0.2.6

The user reported that File > Open works, but selecting a listed recent file
does nothing. Version 0.2.2 built its own menu from `recentDocumentURLs` and
opened the represented URL directly. It did not use AppKit's managed Recent
menu or the system's recent-document selection route.

Version 0.2.3 removed those custom entries but incorrectly assumed that AppKit
would insert a Recent menu from the standard Open action alone. The user's
check in `.build/check.iCszsO` passed the runtime/sandbox and five original
editor checks but reported `native_recent_menu: false`; the runner correctly
stopped without opening the preview.

Version 0.2.4 creates the menu explicitly and sets its AppKit name to
`NSRecentDocumentsMenu` before application launch finishes. The user's check
in `.build/check.8cE6yN` confirmed that registration but reported zero entries
before menu tracking, despite one known recent URL. The user then launched
the preview manually: the file appeared in the menu, but clicking still did
nothing. Thus the probe's expectation of eager population was wrong, and
registration alone did not repair the actual opening failure.

The installed PyObjC 12.1 metadata declares a one-argument completion block for
`openDocumentWithContentsOfURL:display:completionHandler:`. Apple's
[API signature](https://developer.apple.com/documentation/appkit/nsdocumentcontroller/opendocument%28withcontentsof%3Adisplay%3Acompletionhandler%3A%29?language=objc)
has three arguments: document, already-open Boolean and error. A local call
through the real bridge reproduces `BadPrototypeError: Objective-C expects 1
arguments, Python argument has 3 arguments` before the native open runs.

Version 0.2.5 registers the correct signature in `cocoa_compat.py` after AppKit
imports. The correction applies to the Recent/Finder open-event path and
leaves the installed dependency files untouched. No entitlement or app-managed
bookmark was added. The user confirmed actual opening from Recent in the
0.2.6 preview launched by the signed-app check, before using File > Open.

The user's 0.2.5 run in `.build/check.RDwcth` passed the runtime/sandbox,
original editor checks and `native_document_open_callback`. The only failure
was `native_recent_menu`: registration passed but the probe wrongly required
Clear Menu's explicit target to equal the shared document controller.
AppKit's own menu template reproduces this failure: its Clear Menu target is
nil, allowing the responder chain to resolve the action. Version 0.2.6 uses
the public
[`targetForAction:to:from:` API](https://developer.apple.com/documentation/appkit/nsapplication/target%28foraction%3Ato%3Afrom%3A%29)
and checks that the resolved object handles the selector and belongs to
AppKit. The diagnostic logs the declared and resolved target classes, without
filenames, and never invokes Clear Menu. This version changes the diagnostic;
the 0.2.5 document-opening fix remains in place. The user's signed 0.2.6 check
passed both phases in `.build/check.CZa5tk`, then the user confirmed a real
Recent click opens the listed file correctly.

The programmatic registration uses the private `_setMenuName:` selector,
guarded by a capability check. This is also how
[MacVim registers its Recent menu](https://github.com/macvim-dev/macvim/blob/master/src/MacVim/MMAppController.m).
Registration and menu population have been confirmed on the user's Mac. It is a
compatibility dependency to retest on other versions. A compiled menu nib
would replace this hook when Interface Builder tooling is available; this
Mac has Command Line Tools without `ibtool`.

The editor probe completes AppKit's launch sequence with a delegate that
suppresses the normal blank-document/recovery UI. `native_recent_menu` checks
registration and the resolved native Clear Menu handler, without requiring
file entries before menu tracking. The separate `native_document_open_callback`
check invokes the real Cocoa open API for a deliberately missing fixture in an app-private
temporary directory and verifies the three-argument error callback. It opens
no existing document and adds no recent item. All seven editor checks and the
separate live Recent-click acceptance check passed in 0.2.6. Version 0.2.7 has
eight checks after separating Command navigation from the revised shortcuts.

## Startup failure found in 0.2.0

The user's second check aborted with PID 70928. Its crash report and exported
macOS log show that App Sandbox initialized successfully, then macOS denied
`mach-lookup com.apple.coreservices.launchservicesd`. NSApplication initialization
aborted before editor creation. The earlier 0.1.0 GUI launch (PID 62890) has
the same crash stack; the original passing runtime probe did not test GUI
application registration.

Version 0.2.1 links AppKit directly into an Objective-C launcher and initializes
the native application before starting Python. The entitlements are unchanged.
The bundle audit now requires load-time AppKit linkage. The successful native
editor phase in 0.2.2 confirms this startup repair in the user's Mac session.

The check now runs `--probe-runtime` and `--probe-editor` separately. A GUI
failure keeps the runtime result. Both phases log progress immediately; the
runner retains per-run reports and collects a scoped macOS log on failure.
The editor phase creates a hidden window and checks Command/Control events,
formatting, undo/redo and view switching. No print job is submitted.

## Shutdown failure found in 0.2.1

The user's phase-1 check (PID 76383) printed successful runtime/sandbox results,
then exited with SIGSEGV. The crash report shows `NSConcretePrintOperation`
deallocation entering PyObjC's `object_method_dealloc`, `PyGILState_Ensure` and
`new_threadstate`. The launcher's new outer autorelease pool drained after
[`Py_RunMain`](https://docs.python.org/3.12/c-api/init_config.html#c.Py_RunMain)
had finalized Python, so a native object called into a destroyed interpreter.

A minimal compiled host reproduced SIGSEGV with the 0.2.1 launcher. Version
0.2.2 ends the native bootstrap pool before starting Python and scopes bridged
work inside a Python
[`objc.autorelease_pool`](https://pyobjc.readthedocs.io/en/latest/api/module-objc.html#objc.autorelease_pool).
The regression cases now exit with the correct status and confirm the view's
destruction callback runs. Successful and explicitly failed probes release it
before interpreter finalization; an exception can retain it in its traceback
until Python's own cleanup, while the interpreter is still available.

No sandbox entitlement changed. Phase 2 was never reached in 0.2.1; the user's
successful run of both phases in 0.2.2 now confirms both repairs in the signed
app, including clean probe exits.

## Environment and remaining gates

The agent environment aborts even a minimal sandboxed executable before main,
and a development Python process aborts at NSApplication creation. LaunchServices
is unavailable. The agent can run source-level Cocoa/PDF tests and render into
bitmap contexts, but cannot validate native windows or live interaction here.

Pending: extended shortcut/IME checks, selection at page edges and drag
autoscroll, VoiceOver, selected-file and Recent authorization scope/lifetime,
external-change handling, Prestige Elite font import, print-panel accessories,
performance on long documents, and physical print/duplex validation. See the
plan for the complete release contract.

## Signing and distribution

No Developer ID or Apple Development identity is available. This local build
is ad-hoc signed, sandboxed, without hardened runtime, and not notarized.
Developer ID builds enable hardened runtime and require another runtime test
and notarization. No library-validation bypass was added.
