"""Main entry point for the pagemark word processor."""

import sys

def main():
    """Main entry point."""
    from pagemark.editor_wrapper import TextualEditor
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    app = TextualEditor(filename=filename)
    app.run()

if __name__ == '__main__':
    main()