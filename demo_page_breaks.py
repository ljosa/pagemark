#!/usr/bin/env python3
"""Demo of page breaks in the editor."""

from pagemark.editor import Editor

def main():
    print("Page Break Demo")
    print("=" * 50)
    print()
    print("This demo shows page breaks every 54 lines.")
    print("Page breaks appear as horizontal lines (─────)")
    print()
    print("Press Enter to start the editor...")
    input()
    
    editor = Editor()
    
    # Create content that will show page breaks
    paragraphs = []
    
    # Add 110 lines to show 2 page breaks
    for i in range(1, 111):
        paragraphs.append(f"Line {i:3d}: This is content for line {i}")
    
    editor.model.paragraphs = paragraphs
    
    # Run the editor
    editor.run()
    
    print("\nEditor closed.")
    print("Page breaks appear after lines 54 and 108.")

if __name__ == "__main__":
    main()