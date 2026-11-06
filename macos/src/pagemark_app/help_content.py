"""Keyboard reference content, independent of native window presentation."""

HELP_SECTIONS = (
    ("Documents", (
        ("New / open", "⌘N / ⌘O"), ("Save / save as", "⌘S / ⇧⌘S"),
        ("Print", "⌘P"), ("Find", "⌘F"), ("Close window / quit", "⌘W / ⌘Q"),
    )),
    ("Formatting", (
        ("Bold / underline", "⌘B / ⌘U"), ("Center line", "⌘E"),
        ("Capitalize word", "⇧⌘C"), ("Uppercase word", "⇧⌘U"), ("Lowercase word", "⇧⌘L"),
    )),
    ("Editing", (
        ("Cut / copy / paste", "⌘X / ⌘C / ⌘V"), ("Undo / redo", "⌘Z / ⌘Y or ⇧⌘Z"),
        ("Delete next / previous word", "⌘D / ⌘Delete"), ("Delete to end of line", "⌃K"),
        ("Transpose words / characters", "⌘T / ⌃T"), ("Word count", "⌃W"),
    )),
    ("Moving and selecting", (
        ("Previous / next word", "⌘← / ⌘→"), ("Previous / next paragraph", "⌘↑ / ⌘↓"),
        ("Start / end of line", "⌃A / ⌃E"), ("Extend selection", "Shift + movement"),
    )),
    ("View", (
        ("Zoom in / out", "Pinch or ⌘+ / ⌘−"), ("Actual size", "⌘0"),
        ("Full screen", "⌃⌘F"), ("Preferences", "⌘,"),
    )),
    ("While finding", (
        ("Next / previous match", "Return / Shift-Tab"), ("Close Find", "Escape"),
    )),
)

HELP_NOTE = ("⌘ Command    ⇧ Shift    ⌃ Control\n\n"
             "Save, Quit, Find, Print, Cut, Copy, Paste, Bold, Underline, Undo and Redo "
             "also accept Control shortcuts while editing.\n\n"
             "Option types characters using your Mac keyboard layout. "
             "Zoom changes reading size without changing the printed page.")
