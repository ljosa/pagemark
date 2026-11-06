"""AppKit text input and drawing over Pagemark's source/layout mappings."""
from __future__ import annotations

from bisect import bisect_left

import AppKit as A
import Foundation as F
import objc

from pagemark_core.clipboard import ClipboardManager
from pagemark_core.coordinates import DocumentPosition
from pagemark_core.text_layout import display_width

from .codec import utf16_offsets
from .display_preferences import DraftFont, ViewMode
from .geometry import EditorGeometry
from .key_bindings import command_for_key
from .native_painter import TextPainter
from .native_preferences import display_preferences
from .zoom import DEFAULT_ZOOM, ZOOM_COMMANDS, ZoomAnchor, bounded_zoom, command_zoom, pinch_zoom


def composed_boundaries(text):
    if text.isascii() and text.isprintable():
        return range(len(text) + 1)
    string = F.NSString.alloc().initWithString_(text)
    offsets = utf16_offsets(text)
    result = [0]
    index = 0
    while index < offsets[-1]:
        location, length = string.rangeOfComposedCharacterSequenceAtIndex_(index)
        index = location + length
        result.append(bisect_left(offsets, index))
    return result


MOVEMENTS = {"left", "right", "up", "down", "home", "end", "page_up", "page_down",
             "word_left", "word_right", "paragraph_up", "paragraph_down", "line_home", "line_end"}
SPECIAL = {
    ord(A.NSLeftArrowFunctionKey): "left", ord(A.NSRightArrowFunctionKey): "right",
    ord(A.NSUpArrowFunctionKey): "up", ord(A.NSDownArrowFunctionKey): "down",
    ord(A.NSHomeFunctionKey): "home", ord(A.NSEndFunctionKey): "end",
    ord(A.NSPageUpFunctionKey): "page_up", ord(A.NSPageDownFunctionKey): "page_down",
    ord(A.NSDeleteFunctionKey): "delete", ord(A.NSF1FunctionKey): "help",
    127: "backspace", 8: "backspace", 13: "newline", 3: "newline", 9: "tab", 27: "cancel",
}


def event_key(event):
    text = str(event.charactersIgnoringModifiers() or "").lower()
    if len(text) == 1:
        if event.modifierFlags() & A.NSEventModifierFlagControl and 1 <= ord(text) <= 26:
            return chr(ord(text) + 96)
        return SPECIAL.get(ord(text), text)
    return text


class PagemarkEditorView(A.NSView, protocols=[objc.protocolNamed("NSTextInputClient")]):
    def initWithFrame_(self, frame):
        self = objc.super(PagemarkEditorView, self).initWithFrame_(frame)
        if self is not None:
            self.document = None
            self.session = None
            self.view_mode = ViewMode.CONTINUOUS
            self.draft_font = DraftFont()
            self.double_spacing = False
            self._zoom_levels = {False: DEFAULT_ZOOM, True: DEFAULT_ZOOM}
            self.preferences = None
            self.marked = None
            self.composition_before = None
            self.drag_timer = None
            self.drag_event = None
            self.caret_timer = None
            self.caret_visible = True
            self.painter = TextPainter()
        return self

    @objc.python_method
    def configure(self, document):
        self.document = document
        self.session = document.session
        self.session.boundaries = composed_boundaries
        preferences = display_preferences()
        self.preferences = preferences
        self._zoom_levels = {False: preferences.zoom_for(ViewMode.CONTINUOUS),
                             True: preferences.zoom_for(ViewMode.DRAFT)}
        self.view_mode = preferences.view_mode
        self.draft_font = preferences.draft_font
        self.refresh(reveal=False)

    @property
    def screen_font(self):
        return self.draft_font if self.view_mode == ViewMode.DRAFT else None

    @property
    def zoom(self):
        return self._zoom_levels[self.view_mode == ViewMode.DRAFT]

    @zoom.setter
    def zoom(self, value):
        self._zoom_levels[self.view_mode == ViewMode.DRAFT] = bounded_zoom(value)

    @objc.python_method
    def remember_zoom(self):
        if self.preferences is not None:
            self.preferences.set_zoom(self.view_mode, self.zoom)

    @objc.python_method
    def set_zoom(self, value, *, anchor=None, persist=True):
        value = bounded_zoom(value, fallback=self.zoom)
        if self.session is None or value == self.zoom:
            if persist:
                self.remember_zoom()
            return
        visible = self.visibleRect()
        x, y = anchor if anchor is not None else (F.NSMidX(visible), F.NSMidY(visible))
        content_anchor = ZoomAnchor.capture(self.geometry, x, y)
        relative = x - visible.origin.x, y - visible.origin.y
        self.zoom = value
        self.refresh(reveal=False)
        scroll = self.enclosingScrollView()
        if scroll is not None:
            clip = scroll.contentView()
            x, y = content_anchor.point(self.geometry)
            bounds = clip.bounds()
            desired = F.NSMakeRect(x - relative[0], y - relative[1],
                                   bounds.size.width, bounds.size.height)
            clip.scrollToPoint_(clip.constrainBoundsRect_(desired).origin)
            scroll.reflectScrolledClipView_(clip)
        if persist:
            self.remember_zoom()

    def magnifyWithEvent_(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.set_zoom(pinch_zoom(self.zoom, event.magnification()), anchor=(point.x, point.y),
                      persist=False)
        # Keep preference writes out of the continuous gesture update path.
        phase = event.phase()
        if phase == A.NSEventPhaseNone or phase & (A.NSEventPhaseEnded | A.NSEventPhaseCancelled):
            self.remember_zoom()

    def viewDidChangeEffectiveAppearance(self):
        objc.super(PagemarkEditorView, self).viewDidChangeEffectiveAppearance()
        self.setNeedsDisplay_(True)

    def isFlipped(self):
        return True

    def acceptsFirstResponder(self):
        return True

    def becomeFirstResponder(self):
        self.caret_visible = True
        if self.caret_timer:
            self.caret_timer.invalidate()
        self.caret_timer = F.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            0.55, self, "blink:", None, True)
        F.NSRunLoop.mainRunLoop().addTimer_forMode_(self.caret_timer, F.NSRunLoopCommonModes)
        self.setNeedsDisplay_(True)
        return True

    def resignFirstResponder(self):
        self.unmarkText()
        if self.caret_timer:
            self.caret_timer.invalidate()
            self.caret_timer = None
        self.setNeedsDisplay_(True)
        return True

    def viewWillMoveToWindow_(self, window):
        if window is None:
            for timer in (self.caret_timer, self.drag_timer):
                if timer:
                    timer.invalidate()
            self.caret_timer = self.drag_timer = None
        objc.super(PagemarkEditorView, self).viewWillMoveToWindow_(window)

    def blink_(self, timer):
        self.caret_visible = not self.caret_visible
        self.setNeedsDisplayInRect_(self.caret_rect())

    @objc.python_method
    def teardown(self):
        for timer in (self.caret_timer, self.drag_timer):
            if timer:
                timer.invalidate()
        F.NSNotificationCenter.defaultCenter().removeObserver_(self)
        self.caret_timer = self.drag_timer = None
        self.document = None

    def viewportChanged_(self, notification):
        self.refresh(reveal=False)

    @objc.python_method
    def refresh(self, reveal=True):
        if self.session is None:
            return
        scroll = self.enclosingScrollView()
        width = scroll.contentSize().width if scroll else self.frame().size.width
        self.painter.configure(self.zoom, self.screen_font)
        metrics = self.painter.metrics if self.view_mode == ViewMode.DRAFT else None
        self.geometry = EditorGeometry(self.session.layout.line_count, width,
                                       self.view_mode == ViewMode.PAGES, self.double_spacing,
                                       self.zoom, self.session.num_columns, metrics)
        height = max(self.geometry.height, scroll.contentSize().height if scroll else 0)
        self.setFrameSize_((self.geometry.width, height))
        self.caret_visible = True
        self.setNeedsDisplay_(True)
        if reveal:
            rect = self.caret_rect()
            self.scrollRectToVisible_(F.NSInsetRect(rect, -20, -20))
        context = self.inputContext()
        if context:
            context.invalidateCharacterCoordinates()
        if self.document:
            self.document.update_status()
        A.NSAccessibilityPostNotification(self, A.NSAccessibilityValueChangedNotification)
        A.NSAccessibilityPostNotification(self, A.NSAccessibilitySelectedTextChangedNotification)

    @objc.python_method
    def caret_rect(self, offset=None):
        point = self.session.position(self.session.cursor if offset is None else offset)
        line = self.session.layout.line_for_position(point)
        column = self.session.layout.column_for_position(point)
        x, y = self.geometry.point(line, column)
        return F.NSMakeRect(x, y + self.geometry.ink_top, 1.5, self.geometry.ink_height)

    def drawRect_(self, dirty):
        if self.session is None:
            return
        g, layout = self.geometry, self.session.layout
        self.painter.configure(g.zoom, self.screen_font)
        normal = self.painter.fonts[0]
        baselines = self.painter.baselines
        (A.NSColor.windowBackgroundColor() if g.pages else A.NSColor.textBackgroundColor()).set()
        A.NSRectFill(dirty)
        for page in range(g.page_count):
            if g.pages:
                rect = F.NSMakeRect(g.paper_x, 20 + page * g.page_stride, 612 * g.zoom, 792 * g.zoom)
                if F.NSIntersectsRect(rect, dirty):
                    A.NSColor.textBackgroundColor().set()
                    A.NSRectFill(rect)
                    A.NSColor.separatorColor().set()
                    A.NSFrameRect(rect)
                    if page:
                        number = str(page + 1)
                        full_columns = 85 if self.session.num_columns == 65 else 102
                        number_x = g.paper_x + ((full_columns - len(number)) // 2) * g.cell_width
                        F.NSString.stringWithString_(number).drawAtPoint_withAttributes_(
                            (number_x, rect.origin.y + 48 * g.zoom - baselines[False]),
                            {A.NSFontAttributeName: normal,
                             A.NSForegroundColorAttributeName: A.NSColor.textColor()})
            elif page:
                y = g.line_y(page * g.rows_per_page) - 14
                if dirty.origin.y - 20 <= y <= F.NSMaxY(dirty):
                    A.NSColor.separatorColor().set()
                    A.NSRectFill(F.NSMakeRect(g.text_x, y, self.session.num_columns * g.cell_width, 1))
                    self.draw_label(str(page + 1), g.text_x - 28, y - 6)
        start, end = self.session.selection
        first = max(0, g.line_at_y(dirty.origin.y) - 1)
        last = min(layout.line_count, g.line_at_y(F.NSMaxY(dirty)) + 2)
        focused = self.window() and self.window().firstResponder() == self
        for index in range(first, last):
            row = layout.line_at(index)
            paragraph, local = layout.locate_line(index)
            base = self.session.offset(DocumentPosition(paragraph, 0))
            x, y = g.point(index, 0)
            span = row.selection(start - base, end - base)
            selected_newline = (local == layout.paragraphs[paragraph].line_count - 1
                                and start <= base + row.end < end)
            if span or selected_newline:
                left, right = span or (layout.paragraphs[paragraph].visual_column(row.end),) * 2
                if selected_newline:
                    right += 1
                (A.NSColor.selectedTextBackgroundColor() if focused
                 else A.NSColor.unemphasizedSelectedTextBackgroundColor()).set()
                A.NSRectFill(F.NSMakeRect(x + left * g.cell_width, y + g.ink_top,
                                        max(1, right - left) * g.cell_width, g.ink_height))
            self.painter.draw(row, self.session.model.styles[paragraph], start - base, end - base,
                              focused, x, y, g, self.screen_font)
        if focused and self.caret_visible and start == end:
            A.NSColor.textColor().set()
            A.NSRectFill(self.caret_rect())
        if self.marked:
            a, b = self.marked
            for offset in range(a, b):
                rect = self.caret_rect(offset)
                A.NSColor.controlAccentColor().set()
                A.NSRectFill(F.NSMakeRect(rect.origin.x, F.NSMaxY(rect), g.cell_width, 1))

    @objc.python_method
    def draw_label(self, text, x, y):
        F.NSString.stringWithString_(text).drawAtPoint_withAttributes_(
            (x, y), {A.NSFontAttributeName: A.NSFont.systemFontOfSize_(10),
                     A.NSForegroundColorAttributeName: A.NSColor.secondaryLabelColor()})

    @objc.python_method
    def hit_offset(self, event):
        point = self.convertPoint_fromView_(event.locationInWindow(), None)
        target = self.geometry.hit(self.session.layout, point.x, point.y)
        offset = self.session.offset(target)
        return self.session.index.snap(offset, "ceil")

    def mouseDown_(self, event):
        self.unmarkText()
        self.window().makeFirstResponder_(self)
        offset = self.hit_offset(event)
        if event.modifierFlags() & A.NSEventModifierFlagShift:
            anchor = self.session.anchor
            self.drag_anchor = self.session.cursor if anchor is None else anchor
        else:
            self.drag_anchor = offset
        self.session.select(self.drag_anchor, offset)
        if event.clickCount() >= 3:
            point = self.session.position(offset)
            base = offset - point.character_index
            self.session.select(base, min(self.session.index.length,
                                         base + len(self.session.model.paragraphs[point.paragraph_index]) + 1))
        elif event.clickCount() == 2:
            import re
            for match in re.finditer(r"\w+|[^\w\s]+|\s+", self.session.value.text):
                if match.start() <= offset < match.end():
                    start = self.session.index.snap(match.start(), "floor")
                    end = self.session.index.snap(match.end(), "ceil")
                    self.session.select(start, end)
                    break
        self.drag_anchor = self.session.anchor
        if self.drag_anchor is None:
            self.drag_anchor = self.session.cursor
        self.refresh(reveal=False)

    def mouseDragged_(self, event):
        self.drag_event = event
        self.session.select(self.drag_anchor, self.hit_offset(event))
        self.autoscroll_(event)
        if self.drag_timer is None:
            self.drag_timer = F.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
                0.05, self, "continueDrag:", None, True)
            F.NSRunLoop.mainRunLoop().addTimer_forMode_(self.drag_timer, F.NSRunLoopCommonModes)
        self.refresh(reveal=False)

    def continueDrag_(self, timer):
        if self.drag_event and self.autoscroll_(self.drag_event):
            self.session.select(self.drag_anchor, self.hit_offset(self.drag_event))
            self.refresh(reveal=False)

    def mouseUp_(self, event):
        if self.drag_timer:
            self.drag_timer.invalidate()
        self.drag_timer = self.drag_event = None

    def resetCursorRects(self):
        self.addCursorRect_cursor_(self.visibleRect(), A.NSCursor.IBeamCursor())

    def performKeyEquivalent_(self, event):
        if self.window() is None or self.window().firstResponder() != self:
            return False
        modifiers = event.modifierFlags()
        command = command_for_key(
            event_key(event), command=bool(modifiers & A.NSEventModifierFlagCommand),
            control=bool(modifiers & A.NSEventModifierFlagControl),
            option=bool(modifiers & A.NSEventModifierFlagOption),
            shift=bool(modifiers & A.NSEventModifierFlagShift))
        if command is None:
            return False
        self.execute(command, bool(modifiers & A.NSEventModifierFlagShift))
        return True

    def keyDown_(self, event):
        if self.performKeyEquivalent_(event):
            return
        key, flags = event_key(event), event.modifierFlags()
        if not self.hasMarkedText() and not flags & (A.NSEventModifierFlagCommand |
                                                   A.NSEventModifierFlagControl |
                                                   A.NSEventModifierFlagOption):
            if key in MOVEMENTS | {"backspace", "delete", "newline", "tab", "cancel", "help"}:
                self.execute(key, bool(flags & A.NSEventModifierFlagShift))
                return
        self.interpretKeyEvents_([event])

    @objc.python_method
    def execute(self, command, extend=False):
        if command in ZOOM_COMMANDS:
            self.set_zoom(command_zoom(self.zoom, command))
            return  # A presentation change must not commit marked text or reveal the caret.
        self.unmarkText()
        try:
            session = self.session
            if command in MOVEMENTS:
                lines = max(1, int(self.visibleRect().size.height / self.geometry.line_height) - 2)
                session.move(command, extend, lines)
            elif command in ("backspace", "delete"):
                session.delete(command == "backspace")
            elif command in ("bold", "underline"):
                session.toggle_style(1 if command == "bold" else 2)
            elif command == "newline":
                session.insert("\n")
            elif command in ("tab", "transpose_characters"):
                getattr(session, command)()
            elif command in ("copy", "cut", "paste", "undo", "redo"):
                getattr(self, command + "_")(None)
            elif command in ("find", "word_count", "save", "print", "help"):
                self.document.editor_action(command)
            elif command == "quit":
                A.NSApp.terminate_(None)
            elif command == "cancel":
                session.select(session.cursor, session.cursor)
            else:
                session.edit(getattr(session.model, command))
            self.refresh()
        except Exception as error:
            self.document.report_error(error)

    def copy_(self, sender):
        self.session.model.copy_selection()

    def cut_(self, sender):
        self.session.edit(self.session.model.cut_selection)
        self.refresh()

    def paste_(self, sender):
        self.unmarkText()
        text, styles = ClipboardManager.paste_text()
        if text:
            self.session.insert(text, styles)
            self.refresh()

    def undo_(self, sender):
        self.unmarkText()
        self.document.undoManager().undo()

    def redo_(self, sender):
        self.unmarkText()
        self.document.undoManager().redo()

    def selectAll_(self, sender):
        self.unmarkText()
        self.session.select(0, self.session.index.length)
        self.refresh()

    def validateUserInterfaceItem_(self, item):
        action = item.action()
        if action in ("cut:", "copy:"):
            return self.session.selection[0] != self.session.selection[1]
        if action == "undo:":
            return self.document.undoManager().canUndo()
        if action == "redo:":
            return self.document.undoManager().canRedo()
        return True

    def doCommandBySelector_(self, selector):
        name = selector.decode() if isinstance(selector, bytes) else str(selector)
        if name == "cancelOperation:" and self.composition_before is not None:
            self.session.restore(self.composition_before)
            self.marked = self.composition_before = None
            self.refresh()
            return
        command = {"moveLeft:": "left", "moveRight:": "right", "moveUp:": "up",
                   "moveDown:": "down", "deleteBackward:": "backspace",
                   "deleteForward:": "delete", "insertNewline:": "newline",
                   "insertTab:": "tab", "cancelOperation:": "cancel"}.get(name)
        if command:
            self.execute(command)
        else:
            A.NSBeep()

    @objc.python_method
    def source_range(self, native_range):
        location, length = native_range
        start = self.session.index.source_offset(location)
        end = self.session.index.source_offset(location + length, round_up=True)
        return start, max(start, end)

    @objc.python_method
    def native_range(self, start, end):
        first = self.session.index.native_offset(start)
        return F.NSMakeRange(first, self.session.index.native_offset(end) - first)

    def selectedRange(self):
        return self.native_range(*self.session.selection)

    def markedRange(self):
        return self.native_range(*self.marked) if self.marked else F.NSMakeRange(F.NSNotFound, 0)

    def hasMarkedText(self):
        return self.marked is not None

    def validAttributesForMarkedText(self):
        return []

    def setMarkedText_selectedRange_replacementRange_(self, value, selected, replacement):
        text = str(value.string() if hasattr(value, "string") else value)
        if self.composition_before is None:
            self.composition_before = self.session.snapshot()
        start, end = (self.source_range(replacement) if replacement.location != F.NSNotFound
                      else self.marked or self.session.selection)
        self.session.select(start, end)
        # Marked text is transient and may contain characters the terminal input
        # policy filters at commit. Do not sanitize or create separate undo steps.
        self.session.model.replace_selection(text)
        self.marked = (start, start + len(text))
        offsets = utf16_offsets(text)
        a = min(bisect_left(offsets, selected.location), len(text))
        b = min(bisect_left(offsets, selected.location + selected.length), len(text))
        self.session.select(start + a, start + b)
        self.refresh()

    def insertText_replacementRange_(self, value, replacement):
        text = str(value.string() if hasattr(value, "string") else value)
        before = self.composition_before or self.session.snapshot()
        start, end = (self.source_range(replacement) if replacement.location != F.NSNotFound
                      else self.marked or self.session.selection)
        self.session.select(start, end)
        self.session.insert(text, notify=False)
        self.marked = self.composition_before = None
        self.session.notify_change(before)
        self.refresh()

    def unmarkText(self):
        if self.composition_before is not None:
            before = self.composition_before
            self.marked = self.composition_before = None
            self.session.notify_change(before)

    def attributedSubstringForProposedRange_actualRange_(self, proposed, ignored):
        if proposed.location == F.NSNotFound:
            return None, F.NSMakeRange(F.NSNotFound, 0)
        start, end = self.source_range(proposed)
        return (F.NSAttributedString.alloc().initWithString_(self.session.value.text[start:end]),
                self.native_range(start, end))

    def firstRectForCharacterRange_actualRange_(self, proposed, ignored):
        start, end = self.source_range(proposed)
        rect = self.caret_rect(start)
        line = self.session.layout.line_for_position(self.session.position(start))
        row = self.session.layout.line_at(line)
        base = start - self.session.position(start).character_index
        end = min(end, base + row.end)
        if end > start:
            right = (self.geometry.text_x + display_width(row.text) * self.geometry.cell_width
                     if end == base + row.end else self.caret_rect(end).origin.x)
            rect.size.width = max(1.5, right - rect.origin.x)
        else:
            rect.size.width = 0
        window_rect = self.convertRect_toView_(rect, None)
        screen = self.window().convertRectToScreen_(window_rect) if self.window() else window_rect
        return screen, self.native_range(start, end)

    def characterIndexForPoint_(self, point):
        if self.window():
            point = self.window().convertPointFromScreen_(point)
        point = self.convertPoint_fromView_(point, None)
        position = self.geometry.hit(self.session.layout, point.x, point.y)
        return self.session.index.native_offset(self.session.offset(position))

    def isAccessibilityElement(self):
        return True

    def accessibilityRole(self):
        return A.NSAccessibilityTextAreaRole

    def accessibilityLabel(self):
        return "Document text"

    def accessibilityValue(self):
        return self.session.value.text

    def accessibilitySelectedText(self):
        start, end = self.session.selection
        return self.session.value.text[start:end]

    def accessibilitySelectedTextRange(self):
        return self.selectedRange()

    def setAccessibilitySelectedTextRange_(self, value):
        self.session.select(*self.source_range(value))
        self.refresh()

    def accessibilityNumberOfCharacters(self):
        return self.session.index.native_length

    def accessibilityInsertionPointLineNumber(self):
        return self.session.layout.line_for_position(self.session.model.navigation_state.cursor)

    def accessibilityStringForRange_(self, native_range):
        start, end = self.source_range(native_range)
        return self.session.value.text[start:end]

    def accessibilityAttributedStringForRange_(self, native_range):
        from .application import attributed
        start, end = self.source_range(native_range)
        return attributed(self.session.value).attributedSubstringFromRange_(self.native_range(start, end))

    def accessibilityLineForIndex_(self, index):
        start, _ = self.source_range(F.NSMakeRange(index, 0))
        return self.session.layout.line_for_position(self.session.position(start))

    def accessibilityRangeForLine_(self, line):
        layout = self.session.layout
        if not 0 <= line < layout.line_count:
            return F.NSMakeRange(F.NSNotFound, 0)
        paragraph, local = layout.locate_line(line)
        row = layout.line_at(line)
        base = self.session.offset(DocumentPosition(paragraph, 0))
        end = base + row.end
        if local == layout.paragraphs[paragraph].line_count - 1 and paragraph < len(layout.paragraphs) - 1:
            end += 1
        return self.native_range(base + row.start, end)

    def accessibilityRangeForIndex_(self, index):
        start, _ = self.source_range(F.NSMakeRange(index, 0))
        start = self.session.index.snap(start, "floor")
        return self.native_range(start, self.session.index.next_boundary(start))

    def accessibilityRangeForPosition_(self, point):
        return self.accessibilityRangeForIndex_(self.characterIndexForPoint_(point))

    def accessibilityFrameForRange_(self, native_range):
        start, end = self.source_range(native_range)
        layout = self.session.layout
        first = layout.line_for_position(self.session.position(start))
        last = layout.line_for_position(self.session.position(end))
        rect = self.caret_rect(start)
        for line in range(first, last + 1):
            x, y = self.geometry.point(line, 0)
            left = rect.origin.x if line == first else x
            right = (self.caret_rect(end).origin.x if line == last
                     else x + self.session.num_columns * self.geometry.cell_width)
            piece = F.NSMakeRect(left, y + self.geometry.ink_top,
                                max(1.5, right - left), self.geometry.ink_height)
            rect = F.NSUnionRect(rect, piece)
        window_rect = self.convertRect_toView_(rect, None)
        return self.window().convertRectToScreen_(window_rect) if self.window() else window_rect

    def setAccessibilitySelectedText_(self, value):
        self.unmarkText()
        self.session.insert(str(value))
        self.refresh()

    def isAccessibilityFocused(self):
        return bool(self.window() and self.window().firstResponder() == self)

    def setAccessibilityFocused_(self, value):
        if value and self.window():
            self.window().makeFirstResponder_(self)

    def accessibilityVisibleCharacterRange(self):
        rect = self.visibleRect()
        first = self.geometry.line_at_y(rect.origin.y)
        last = self.geometry.line_at_y(F.NSMaxY(rect))
        layout = self.session.layout
        start = self.session.offset(layout.position_at(first, 0))
        paragraph, _ = layout.locate_line(last)
        end = self.session.offset(DocumentPosition(paragraph, layout.line_at(last).end))
        return self.native_range(start, end)
