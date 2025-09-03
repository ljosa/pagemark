#!/usr/bin/env python3
"""Demo script showing the fixed 65-column width editor."""

from pagemark.editor import Editor

def main():
    editor = Editor()
    
    # Add some demo text
    editor.model.paragraphs = [
        "Welcome to Pagemark - a fixed-width text editor!",
        "",
        "This editor always displays exactly 65 columns of text, regardless of your terminal width. If your terminal is wider than 65 columns, the editor view will be centered. If it's narrower, you'll see an error message.",
        "",
        "The editor automatically responds to terminal resize events without any polling! When you resize your terminal, the system sends a SIGWINCH signal which is handled by injecting a KEY_RESIZE event. Try resizing your terminal window while the editor is running - it will instantly re-center the view or show/hide the error message.",
        "",
        "Controls:",
        "- Arrow keys: Navigate",
        "- Backspace: Delete",  
        "- Enter: New paragraph",
        "- Ctrl-Q: Quit"
    ]
    
    # Start at the beginning
    editor.model.cursor_position.paragraph_index = 0
    editor.model.cursor_position.character_index = 0
    
    editor.run()
    print("\nThanks for trying Pagemark!")

if __name__ == "__main__":
    main()