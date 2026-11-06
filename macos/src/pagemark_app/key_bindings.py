"""Editor shortcut policy, independent of native events and menu dispatch."""

CONTROL = {
    "a": "line_home", "e": "line_end", "d": "delete", "k": "kill_line",
    "b": "bold", "u": "underline", "t": "transpose_characters", "f": "find",
    "w": "word_count", "s": "save", "p": "print", "q": "quit",
    "c": "copy", "x": "cut", "v": "paste", "z": "undo", "y": "redo",
}
COMMAND = {key: CONTROL[key] for key in "sqfpxcvbuzy"}
COMMAND["e"] = "center_line"
SHIFT_COMMAND = {"c": "capitalize_word", "u": "upcase_word", "l": "downcase_word", "z": "redo"}
ZOOM_KEYS = {"+": "zoom_in", "=": "zoom_in", "-": "zoom_out", "0": "zoom_reset"}
META = {
    "left": "word_left", "right": "word_right",
    "up": "paragraph_up", "down": "paragraph_down",
    "d": "kill_word", "backspace": "backward_kill_word", "t": "transpose_words",
}


def command_for_key(key, *, command=False, control=False, option=False, shift=False):
    if option or command and control:
        return None
    if command:
        if key in ZOOM_KEYS and (not shift or key in ("+", "=")):
            return ZOOM_KEYS[key]
        if shift:
            if key in SHIFT_COMMAND:
                return SHIFT_COMMAND[key]
            if key not in ("left", "right", "up", "down"):
                return None  # Leave other Shift-Command equivalents to native menus.
        return COMMAND.get(key) or META.get(key)
    if control:
        return CONTROL.get(key)
    return None
