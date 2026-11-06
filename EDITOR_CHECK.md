# Editor preview checks on the Mac

The current build is **0.2.10**, which adds **View > Fit Width** and
**Resize Window to Fit**. It includes pinch and Command-+/−/0 zoom with
remembered scales in place of the Draft font-size preference, plus Draft,
appearance preferences, Full Screen and **File > Print Booklet…** from 0.2.8.
It also includes shared paragraph-layout reuse,
batched native drawing and paragraph-local Unicode indices. After the probe passes,
compare typing, arrow movement, selection, formatting and undo in all three views,
using a short document and a longer one. The remaining edit cost grows with
full-document snapshots; see [PERFORMANCE.md](PERFORMANCE.md).

Version **0.2.8** passed both probe phases on the user's Mac on 2026-11-05,
including Command navigation/shortcuts, Control aliases, native Recent-menu
routing, the document-open callback, all three views and native Preferences
controls/appearance checks. Reports are retained in `.build/check.xzz5Dg`.
Manual font changes, appearance interaction, full-screen transitions and the
Print Booklet dialog remain to be checked in the preview.
The user also confirmed normal typing, mouse scrolling, drag-selection and
File > Open. Version 0.2.4's native Recent menu displays the file when opened,
but selecting it does nothing. Version **0.2.5** corrects the Cocoa bridge's
open-document callback signature, and the user confirmed the signed callback
probe passes. Version **0.2.6** corrects a false failure in the menu diagnostic:
Clear Menu's native handler must be resolved through the responder chain;
the signed probe confirmed it resolves to `NSDocumentController`.
The user confirmed that File > Open Recent opens the listed file correctly in
the launched 0.2.6 preview, before using File > Open. The next document check
is saving styled edits and verifying interchange with terminal Pagemark
(step 5 below).

After rebuilding, quit the earlier preview and run `tools/check_sandbox.command`.
Both reports should identify version **0.2.10**. Phase 1 checks the runtime and
sandbox; phase 2's eleven native editor checks, including `command_shortcuts`,
`command_navigation`, `native_recent_menu`, `native_document_open_callback`,
`native_display_preferences`, `native_zoom_controls`, and `native_fit_actions`,
should all be true. The probe uses a
disposable hidden window and a missing app-private fixture for the callback,
never the contents of an existing document. If
either phase fails, its stderr shows the last completed startup step and the
runner collects macOS diagnostics automatically.
Recent-menu diagnostics report registration and the resolved native Clear Menu
handler without file names or invoking the action. File entries are populated
when the user opens the menu and are not required at rest.
The zoom check uses real key events, a native clip view and synthetic pinch
deltas; physical trackpad event delivery still needs the interaction check.
The fit check changes a disposable window's width at normal and large zoom,
checks screen limits, and verifies Fit Width keeps the window frame unchanged.

## Short interaction check

1. In the opened window, type two paragraphs and a long `- ` bullet paragraph.
   Try an accented character through Option and a composed input method if
   available. Use Control-B and Control-U while typing and on a selection.
2. Drag-select across wrapped lines; Shift-click to extend. Drag below the
   window to autoscroll. Scroll away with the trackpad and confirm that the
   selection stays put. Move the caret to reveal it again.
3. Switch **View > Pages**, **Draft**, then **Continuous**. Selection, caret,
   text and undo should survive. In **Pagemark > Preferences…**, change Draft's
   font family, then check mouse selection, bold and underline. The default
   should use JetBrains Mono NL if available, otherwise Menlo. Continuous,
   Pages and output should retain Courier. Check Light Mode, Dark Mode, System
   Default, and Control-Command-F for entering/exiting full screen. Relaunch
   to confirm the view, font and appearance preferences persist. Paper gaps
   and markers should never become text.
   In each view, scroll away from the caret, then pinch and try Command-+/−/0
   (also Command-=). Zoom should stay anchored at the pointer for pinch and
   the visible center for keys, without jumping to the caret. Check selection
   after zooming. Draft remembers its own zoom; Continuous and Pages share
   another. Relaunch to confirm those scales persist. Reset should show 100%.
   Select **Fit Width** in each view: the content should fit without resizing
   the window. Then choose a different zoom and select **Resize Window to Fit**:
   the window width should change while height and zoom stay fixed. Near a
   screen edge it may move sideways; at a very large zoom it should stop at
   the usable screen width. Check that only the resize action is disabled in
   full screen, and that ordinary pinch/keyboard zoom keeps the window fixed.
4. Check Command-Left/Right for word movement, Command-B/U for formatting,
   Command-M for centering a short paragraph, Command-C/V for styled copy/paste,
   Command-Z/Y (also Shift-Command-Z) for undo/redo, and Command-F for search.
   The common editing actions also retain their Control aliases. Edit > Transform
   provides Capitalize/Uppercase/Lowercase Word. In search, Return finds
   the next occurrence; Shift-Tab finds the previous one; Escape closes search.
5. Add bold and underlined text to a disposable document and save it with
   Control-S. Quit and relaunch the app, then use **File > Open Recent**.
   Confirm the text and formatting survive. Reopen the same file in terminal
   Pagemark to check interchange. In native file dialogs, Command-A/C/V should
   retain their usual behavior.
6. Export PDF and inspect **File > Print…**, then **File > Print Booklet…**;
   cancel both dialogs without printing. Compare single/double spacing and
   page counts. The booklet preview should show landscape sheet sides in
   imposed order. A later ordinary Print or Export PDF should still show
   portrait reading-order pages. The native dialog controls duplex and printer
   settings; its PDF menu can save booklet output.

## Recovery check

Use a disposable document with no valuable changes in other Pagemark windows.
Edit, wait at least one second, then force-quit Pagemark using macOS. Relaunch
and choose Recover. The recovered content should open as an unsaved private
copy, and Save should request a destination. No source file is changed by
recovery. Ordinary Save or Discard removes that document's recovery copy.

Recovery files live inside the app container under
`Library/Application Support/Pagemark/Recovery`. The app offers pending copies
at launch; **File > Recover Unsaved Documents** offers them again later.
No source paths or security-scoped bookmarks are stored in these copies.

## Remaining acceptance work

Verify real VoiceOver navigation/editing, Japanese/Chinese input, drag behavior
at page edges, long-document responsiveness, Recent authorization after
relaunch, selected-file write scope, external file conflicts, and physical
printing. Font import and print-panel accessories are subsequent work. The
current build is ad-hoc signed and has not been notarized.
