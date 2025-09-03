#!/usr/bin/env python3
"""Demo of page numbers in page breaks."""

from pagemark.editor import Editor

def main():
    print("Page Numbers Demo")
    print("=" * 50)
    print()
    print("This demo shows centered page numbers in page breaks.")
    print("Page breaks appear as '──── Page N ────' every 54 lines.")
    print()
    print("Press Enter to start the editor...")
    input()
    
    editor = Editor()
    
    # Create content that will show multiple page breaks
    paragraphs = []
    
    # Create a document with 165 lines (3 pages worth)
    for page in range(1, 4):
        start_line = (page - 1) * 54 + 1
        end_line = page * 54
        
        paragraphs.append(f"")
        paragraphs.append(f"PAGE {page} CONTENT")
        paragraphs.append(f"================")
        paragraphs.append(f"")
        
        for i in range(start_line, min(end_line - 3, end_line)):
            paragraphs.append(f"Line {i:3d}: This is content for page {page}, line {i}")
    
    editor.model.paragraphs = paragraphs
    
    # Run the editor
    editor.run()
    
    print("\nEditor closed.")
    print("Page breaks with centered page numbers appeared:")
    print("  - After line 54: '──── Page 2 ────'")
    print("  - After line 108: '──── Page 3 ────'")
    print("  - After line 162: '──── Page 4 ────'")

if __name__ == "__main__":
    main()