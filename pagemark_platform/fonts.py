"""Terminal font discovery; sandboxed front ends pass user-selected files."""
from pathlib import Path


def prestige_font_paths():
    directories = (Path.home() / "Library/Fonts", Path("/Library/Fonts"),
                   Path("/System/Library/Fonts/Supplemental"))
    return tuple(next((str(path) for directory in directories
                       if (path := directory / filename).is_file()), None)
                 for filename in ("PrestigeEliteStd.ttf", "PrestigeEliteStd-Bd.ttf"))
