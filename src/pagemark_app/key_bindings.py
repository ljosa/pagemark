"""Editor shortcut policy, independent of native events and menu dispatch."""

CONTROL = {
    "a": "line_home", "e": "line_end", "d": "delete", "k": "kill_line",
    "b": "bold", "u": "underline", "t": "transpose_characters", "f": "find",
    "w": "word_count", "s": "save", "p": "print", "q": "quit",
    "c": "copy", "x": "cut", "v": "paste", "z": "undo", "y": "redo",
}
COMMAND = {key: CONTROL[key] for key in "sqfpxcvbuzy"}
ZOOM_KEYS = {"+": "zoom_in", "=": "zoom_in", "-": "zoom_out", "0": "zoom_reset"}
META = {
    "left": "word_left", "right": "word_right",
    "up": "paragraph_up", "down": "paragraph_down",
    "l": "downcase_word", "d": "kill_word", "backspace": "backward_kill_word",
    "t": "transpose_words", "m": "center_line",
}


def command_for_key(key, *, command=False, control=False, option=False, shift=False):
    if option or command and control:
        return None
    if command:
        if key in ZOOM_KEYS and (not shift or key in ("+", "=")):
            return ZOOM_KEYS[key]
        if shift:
            if key == "z":
                return "redo"
            if key not in ("left", "right", "up", "down"):
                return None  # Leave other Shift-Command equivalents to native menus.
        return COMMAND.get(key) or META.get(key)
    if control:
        return CONTROL.get(key)
    return None


CONTROLS_HELP = (
    "⌘S: save · ⌘Q: quit · ⌘F: find · ⌘P: print\n"
    "⌘X / ⌘C / ⌘V: cut / copy / paste\n"
    "⌘B / ⌘U: bold / underline\n⌘Z: undo · ⌘Y or ⇧⌘Z: redo\n"
    "These commands also retain their Control shortcuts in the editor.\n\n"
    "Pinch or ⌘+ / ⌘−: zoom in / out · ⌘0: 100%\n"
    "Zoom changes the view, not the printed page.\n\n"
    "⌘← / ⌘→: previous / next word\n⌘↑ / ⌘↓: previous / next paragraph\n"
    "Add Shift to extend the selection.\n"
    "⌘D / ⌘Delete: delete next / previous word\n⌘M: center line\n"
    "⌘T: transpose words · ⌘L: lowercase word\n"
    "Edit > Transform: capitalize, uppercase or lowercase a word\n\n"
    "Control-A / E: line start / end\nControl-K: kill line\n"
    "Control-T: transpose characters · Control-W: word count\n\n"
    "Option uses the Mac keyboard layout. Native dialogs use normal Mac shortcuts."
)
