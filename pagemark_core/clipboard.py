"""Clipboard capability supplied explicitly by a front end."""
from __future__ import annotations

from typing import Protocol


class Clipboard(Protocol):
    def copy_text(self, text: str, styles: list[list[int]] | None = None) -> None: ...

    def paste_text(self) -> tuple[str, list[list[int]] | None]: ...
