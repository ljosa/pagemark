"""Pagemark CLI entry point.

Allows running via `python -m pagemark` and provides the console script
defined in `pyproject.toml`.
"""

import sys
from .editor import Editor


def main() -> None:
    editor = Editor()
    if len(sys.argv) > 1:
        editor.load_file(sys.argv[1])
    editor.run()


if __name__ == "__main__":  # pragma: no cover
    main()

